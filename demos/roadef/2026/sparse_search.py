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
from shiftopt import Model, MINIMIZE, quicksum


def propose(graph, jobs, scenario, loads, via, period, rng, change_limit=None):
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
    for edge in np.argsort(-load)[:8]:
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
        model.addConstr(over >= new_load - .75 * load.max())
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


def solve(folder, name, checker, output, rounds, period_only=False):
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

        current = check(via)
        if current is None:
            raise ValueError("Default routing is infeasible")
        output.write_bytes(candidate.read_bytes())
        for step in range(rounds):
            ranked = sorted(current, key=lambda row: -row["sat"])
            periods = list(dict.fromkeys(row["t"] for row in ranked))
            loads = {(r["t"], r["from"], r["to"]): r["sat"] for r in current}
            period = periods[step % (len(periods) if period_only else min(3, len(periods)))]
            limit = None
            if period_only:
                budgets = [x["value"] for x in scenario["budget"] if x["t"] in (period, period + 1)]
                limit = max(1, min(budgets, default=4) // 4)
            moves = propose(graph, jobs, scenario, loads, via[period], period, rng, limit)
            trial = via.copy()
            if period_only:
                trial[period] = moves
            else:
                trial[:] = moves
            if np.array_equal(via, trial):
                continue
            new = check(trial)
            if new is not None and sorted((x["sat"] for x in new), reverse=True) < [x["sat"] for x in ranked]:
                via, current = trial, new
                output.write_bytes(candidate.read_bytes())


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folder", type=Path)
    parser.add_argument("instance")
    parser.add_argument("checker", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--rounds", type=int, default=6)
    parser.add_argument("--period-only", action="store_true", help="optimize one period per iteration")
    args = parser.parse_args()
    solve(args.folder, args.instance, args.checker.resolve(), args.output, args.rounds, args.period_only)
