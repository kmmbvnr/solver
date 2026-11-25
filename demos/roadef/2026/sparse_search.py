"""Improve a static waypoint plan using the checker's most congested links."""
import argparse
import json
import subprocess
import tempfile
from collections import Counter
from functools import lru_cache
from pathlib import Path

import numpy as np
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import dijkstra
from shiftopt import bandit_policy, Model, MINIMIZE, quicksum, run_pipeline


def propose(graph, jobs, scenario, loads, via, period, rng, change_limit=None, offset=0):
    """Build a pool of detours and select a compatible subset for one period."""
    blocked = next((x["links"] for x in scenario["interventions"] if x["t"] == period), [])
    blocked = set(blocked)
    edges = [e for e in graph["links"] if e["id"] not in blocked]
    n = len(graph["nodes"])
    a, b, weight, capacity = (np.array([e[k] for e in edges]) for k in ("from", "to", "metric", "capacity"))
    dist = dijkstra(csr_matrix((weight, (a, b)), shape=(n, n)))
    adj = [[] for _ in range(n)]
    for i, u in enumerate(a):
        adj[u].append(i)
    load = np.array([loads.get((period, u, v), 0.) for u, v in zip(a, b)])

    @lru_cache(maxsize=16000)
    def flow(u, v):
        if u == v:
            return {}
        hops = [i for i in adj[u] if weight[i] + dist[b[i], v] == dist[u, v]]
        shares = Counter()
        for i in hops:
            shares[i] += 1
            shares.update(flow(b[i], v))
        return {i: x / len(hops) for i, x in shares.items()}

    s, t = (np.array([j[k] for j in jobs]) for k in ("s", "t"))
    volume = np.array([j["v"][period] for j in jobs])
    pool = []
    seen = set()
    target_edges = np.argsort(-load)[offset:offset + 8]
    if not len(target_edges):
        return via
    for edge in target_edges:
        u, v = a[edge], b[edge]
        for left, right in ((s, via), (via, t)):
            crosses = dist[left, u] + weight[edge] + dist[v, right] == dist[left, right]
            ids = np.flatnonzero(crosses & (volume > 0))
            for j in ids[np.argsort(-volume[ids])[:16]]:
                if j in seen:
                    continue
                seen.add(j)
                old = Counter(flow(s[j], via[j]))
                old.update(flow(via[j], t[j]))
                if not old[edge]:
                    continue
                for w in np.unique(np.r_[s[j], rng.choice(n, min(n, 24), replace=False)]):
                    if w in (via[j], t[j]) or not np.isfinite(dist[s[j], w] + dist[w, t[j]]):
                        continue
                    delta = Counter(flow(s[j], w))
                    delta.update(flow(w, t[j]))
                    delta.subtract(old)
                    if delta[edge] >= -1e-8:
                        continue
                    pool.append((j, w, {i: x * volume[j] / capacity[i] for i, x in delta.items() if abs(x) > 1e-10}))
    if not pool:
        return via
    model = Model(threads=1)
    variables = [model.addVar(vtype="B") for _ in pool]
    by_job, by_link = {}, {}
    for (j, _, delta), var in zip(pool, variables):
        by_job.setdefault(j, []).append(var)
        for i, x in delta.items():
            if abs(x) > 1e-9:
                by_link.setdefault(i, []).append(x * var)
    for group in by_job.values():
        model.addConstr(quicksum(group) <= 1)
    if change_limit is not None:
        model.addConstr(quicksum(variables) <= change_limit)
    peak = model.addVar(lb=0)
    excess = []
    for i in set(by_link).union(np.argsort(-load)[:8]):
        new_load = load[i].item() + quicksum(by_link.get(i, []))
        model.addConstr(peak >= new_load)
        over = model.addVar(lb=0)
        model.addConstr(over >= new_load - .75 * load[target_edges[0]])
        excess.append(over)
    model.setObjective(peak + .03 * quicksum(excess), MINIMIZE)
    model.setStart(zip(variables, np.zeros(len(pool))))
    result = model.optimize(time_limit=3)
    trial = via.copy()
    if result.has_solution:
        for (j, w, _), var in zip(pool, variables):
            if result.value(var) > .5:
                trial[j] = w
    return trial


def solve(folder, name, checker, output, rounds, period_only=False, policy="fixed"):
    paths = [folder / f"{name}-{k}.json" for k in ("net", "tm", "scenario")]
    graph, traffic, scenario = (json.loads(p.read_text()) for p in paths)
    jobs = traffic["demands"]
    source = np.array([j["s"] for j in jobs])
    periods_count = len(jobs[0]["v"])
    via = np.tile(source, (periods_count, 1))
    rng = np.random.default_rng(7)
    with tempfile.TemporaryDirectory() as scratch:
        candidate = Path(scratch) / "plan.json"

        def check(waypoints):
            routes = [{"d": int(j), "t": p, "w": [int(waypoints[p, j])]}
                      for j in np.flatnonzero(np.any(waypoints != source, axis=0))
                      for p in range(periods_count) if waypoints[p, j] != source[j]]
            candidate.write_text(json.dumps({"srpaths": routes}))
            run = subprocess.run([checker, "--net", paths[0], "--tm", paths[1], "--scenario", paths[2],
                                  "--srpaths", candidate, "--max-decimal-places", "6"], capture_output=True)
            report = json.loads(run.stdout)
            return report["saturations"] if report["valid"] else None

        def default_routes(plan, deadline):
            rows = check(via)
            if rows is None:
                raise ValueError("Default routing is infeasible")
            return via, rows, candidate.read_bytes()

        def waypoint_move(plan, deadline, step, single_period):
            via, current, _ = plan
            ranked = sorted(current, key=lambda row: -row["sat"])
            periods = list(dict.fromkeys(row["t"] for row in ranked))
            loads = {(r["t"], r["from"], r["to"]): r["sat"] for r in current}
            period = periods[step % (len(periods) if single_period else min(3, len(periods)))]
            limit = None
            if single_period:
                budgets = [x["value"] for x in scenario["budget"] if x["t"] in (period, period + 1)]
                limit = max(1, min(budgets, default=4) // 4)
            moves = propose(graph, jobs, scenario, loads, via[period], period, rng, limit,
                            8 * (step % 4) if single_period else 0)
            trial = via.copy()
            if single_period:
                trial[period] = moves
            else:
                trial[:] = moves
            if np.array_equal(via, trial):
                return None
            rows = check(trial)
            if rows is not None:
                return trial, rows, candidate.read_bytes()
            return None

        def load_vector(plan):
            return tuple(sorted((row["sat"] for row in plan[1]), reverse=True))

        if policy not in ("fixed", "alternate", "adaptive", "bandit") or (period_only and policy != "fixed"):
            raise ValueError("mixed policies require both shared and period moves")

        def operator(single_period):
            attempts = 0
            def move(plan, deadline):
                nonlocal attempts
                index = attempts
                attempts += 1
                return waypoint_move(plan, deadline, index, single_period)
            return move

        shared, period = operator(False), operator(True)
        moves = max(0, rounds)
        choose = None
        gain = None
        if policy == "bandit":
            steps = [default_routes, shared, period]
            choose = bandit_policy([shared, period], construct=default_routes, exploration=0.15)
            def gain(old, new):
                return next((a - b) / a for a, b in zip(old, new) if a != b)
        elif policy == "adaptive":
            steps = [default_routes, shared, period]

            def choose(best, history, remaining):
                if best is None:
                    return default_routes
                last = history[-1]
                if last.step is default_routes:
                    return shared
                if last.accepted:
                    return last.step
                return period if last.step is shared else shared
        elif policy == "alternate":
            steps = [default_routes, *((shared, period)[i % 2] for i in range(moves))]
        else:
            steps = [default_routes] + [period if period_only else shared] * moves
        run_pipeline(steps, load_vector, policy=choose, gain=gain, max_steps=moves + 1,
                     on_accept=lambda plan: output.write_bytes(plan[2]))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folder", type=Path)
    parser.add_argument("instance")
    parser.add_argument("checker", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--rounds", type=int, default=6)
    parser.add_argument("--period-only", action="store_true", help="optimize one period per iteration")
    parser.add_argument("--policy", choices=("fixed", "alternate", "adaptive", "bandit"), default="fixed")
    args = parser.parse_args()
    if args.period_only and args.policy != "fixed":
        parser.error("--period-only applies to the fixed policy")
    solve(args.folder, args.instance, args.checker.resolve(), args.output, args.rounds, args.period_only, args.policy)
