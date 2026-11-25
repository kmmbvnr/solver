"""Assign frequencies and polarizations with progressively tighter interference limits."""

import argparse
from collections import defaultdict
from functools import partial
from operator import itemgetter
from pathlib import Path
from time import monotonic

from ortools.sat.python import cp_model

from shiftopt import run_pipeline


def search(plan, deadline, data, level, budget):
    domains, links, hard, soft = data
    model = cp_model.CpModel()
    freq = {
        i: model.new_int_var_from_domain(
            cp_model.Domain.from_values(domains[d]), f"f{i}"
        )
        for i, (d, p) in links.items()
    }
    pol = {i: model.new_bool_var(f"p{i}") for i in links}
    for i, (_, p) in links.items():
        if p:
            model.add(pol[i] == int(p > 0))
    separation = {}
    equal = {}
    active_soft = soft if level < 11 else []
    for a, b in sorted({(min(a, b), max(a, b)) for a, b, *_ in [*hard, *active_soft]}):
        bound = max(max(domains[links[i][0]]) for i in (a, b))
        diff = model.new_int_var(0, bound, "distance")
        model.add_abs_equality(diff, freq[a] - freq[b])
        same = model.new_bool_var("same")
        model.add(pol[a] == pol[b]).only_enforce_if(same)
        model.add(pol[a] != pol[b]).only_enforce_if(~same)
        separation[a, b] = diff
        equal[a, b] = same
    for a, b, kind, op, value in hard:
        key = min(a, b), max(a, b)
        if kind == "F":
            model.add(
                separation[key] == value if op == "E" else separation[key] != value
            )
        else:
            model.add(equal[key] == int(op == "E"))
    penalties = []
    for a, b, kind, thresholds in active_soft:
        key = min(a, b), max(a, b)
        active = equal[key] if kind == "CE" else ~equal[key]
        if level < 11:
            model.add(separation[key] >= thresholds[level]).only_enforce_if(active)
        if level:
            bad = model.new_bool_var("violation")
            model.add(separation[key] >= thresholds[level - 1]).only_enforce_if(
                [active, ~bad]
            )
            penalties.append(bad)
    model.minimize(sum(penalties))
    if plan is not None:
        for i, (f, p) in plan[1].items():
            model.add_hint(freq[i], f)
            model.add_hint(pol[i], int(p > 0))
    solver = cp_model.CpSolver()
    solver.parameters.num_search_workers = 1
    solver.parameters.max_time_in_seconds = max(0, min(budget, deadline - monotonic()))
    if solver.solve(model) not in (cp_model.FEASIBLE, cp_model.OPTIMAL):
        return None
    values = {i: (solver.value(freq[i]), 2 * solver.value(pol[i]) - 1) for i in links}
    violations = [0] * 11
    for a, b, kind, thresholds in soft:
        fa, pa = values[a]
        fb, pb = values[b]
        if (pa == pb) == (kind == "CE"):
            for j, t in enumerate(thresholds):
                violations[j] += int(abs(fa - fb) < t)
    k = max((j + 1 for j, x in enumerate(violations) if x), default=0)
    return (k, violations[k - 1] if k else 0, sum(violations[: max(0, k - 1)])), values


def solve(path, seconds):
    domains = defaultdict(list)
    links = {}
    hard = []
    soft = []
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        tag, *fields = line.split()
        a, b = map(int, fields[:2])
        if tag == "DM":
            domains[a].append(b)
        elif tag == "TR":
            links[a] = (b, int(fields[2]))
        elif tag == "CI":
            hard.append((a, b, *fields[2:4], int(fields[4])))
        elif tag in ("CE", "CD"):
            soft.append((a, b, tag, list(map(int, fields[2:]))))
    data = domains, links, hard, soft
    steps = [
        partial(search, data=data, level=k, budget=seconds / 12)
        for k in range(11, -1, -1)
    ]
    started = monotonic()
    result = run_pipeline(steps, itemgetter(0), seconds=seconds)
    if result is None:
        raise TimeoutError("no feasible frequency plan")
    score, assignment = result
    elapsed = min(99999, int(monotonic() - started))
    k, n, total = score
    header = f"RP {k:2d} 0 {elapsed:5d} 99999 {n:9d} 0 {elapsed:5d} 99999 {total:9d} 0 {elapsed:5d} 99999 {elapsed:5d}\n"
    return score, header + "".join(
        f"AL {i:5d} {f:5d} {p:2d}\n" for i, (f, p) in assignment.items()
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "input",
        type=Path,
        nargs="?",
        default=Path(__file__).with_name("fapp01_0200.in"),
    )
    parser.add_argument("--seconds", type=float, default=5)
    args = parser.parse_args()
    print(solve(args.input, args.seconds)[1], end="")
