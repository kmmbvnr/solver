"""Improve a machine assignment while enforcing all five feasibility constraints."""

import argparse
from collections import Counter
from functools import partial
from operator import itemgetter
from pathlib import Path
from time import monotonic

from shiftopt import run_pipeline


def read_model(path):
    data = iter(map(int, path.read_text().split()))
    nr = next(data)
    resources = [(next(data), next(data)) for _ in range(nr)]
    nm = next(data)
    machines = [
        (
            [next(data) for _ in range(2)],
            [next(data) for _ in range(nr)],
            [next(data) for _ in range(nr)],
            [next(data) for _ in range(nm)],
        )
        for _ in range(nm)
    ]
    services = []
    for _ in range(next(data)):
        spread, count = next(data), next(data)
        services.append((spread, [next(data) for _ in range(count)]))
    processes = [
        (next(data), [next(data) for _ in range(nr)], next(data))
        for _ in range(next(data))
    ]
    balance = [tuple(next(data) for _ in range(4)) for _ in range(next(data))]
    return resources, machines, services, processes, balance, list(data)


def cost(assignment, model, initial):
    resources, machines, services, processes, balances, weights = model
    load = [[0] * len(resources) for _ in machines]
    extra = [row.copy() for row in load]
    locations = [set() for _ in services]
    neighborhoods = [set() for _ in services]
    used = set()
    moves = Counter()
    pcost = mcost = 0
    for dest, old, (s, req, move_cost) in zip(assignment, initial, processes):
        if (s, dest) in used:
            return None
        used.add((s, dest))
        neigh, loc = machines[dest][0]
        locations[s].add(loc)
        neighborhoods[s].add(neigh)
        for r, amount in enumerate(req):
            load[dest][r] += amount
            if dest != old and resources[r][0]:
                extra[old][r] += amount
        if dest != old:
            moves[s] += 1
            pcost += move_cost
            mcost += machines[old][3][dest]
    total = (
        pcost * weights[0]
        + max(moves.values(), default=0) * weights[1]
        + mcost * weights[2]
    )
    for s, (spread, deps) in enumerate(services):
        if len(locations[s]) < spread or any(
            neighborhoods[s] - neighborhoods[d] for d in deps
        ):
            return None
    for m, (_, cap, safe, _) in enumerate(machines):
        for r, (_, w) in enumerate(resources):
            if load[m][r] + extra[m][r] > cap[r]:
                return None
            total += max(0, load[m][r] - safe[r]) * w
        for a, b, target, w in balances:
            total += max(0, target * (cap[a] - load[m][a]) - (cap[b] - load[m][b])) * w
    return total


def improve(plan, deadline, model, initial, reverse):
    best, assignment = plan[0], plan[1].copy()
    order = range(len(assignment) - 1, -1, -1) if reverse else range(len(assignment))
    for p in order:
        old = assignment[p]
        for m in range(len(model[1])):
            if monotonic() >= deadline:
                assignment[p] = old
                return best, assignment
            assignment[p] = m
            score = cost(assignment, model, initial)
            if score is not None and score < best:
                best, old = score, m
        assignment[p] = old
    return best, assignment


def solve(path, seconds):
    model = read_model(path)
    original = path.with_name(path.name.replace("model_", "assignment_", 1))
    initial = list(map(int, original.read_text().split()))
    if len(initial) != len(model[3]):
        raise ValueError("assignment size mismatch")
    start = cost(initial, model, initial)
    if start is None:
        raise ValueError("infeasible original assignment")
    steps = [
        partial(improve, model=model, initial=initial, reverse=r) for r in (False, True)
    ]
    value, plan = run_pipeline(
        steps, itemgetter(0), initial=(start, initial), seconds=seconds
    )
    return value, " ".join(map(str, plan)) + "\n"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "input",
        type=Path,
        nargs="?",
        default=Path(__file__).with_name("model_a1_1.txt"),
    )
    parser.add_argument("--seconds", type=float, default=5)
    args = parser.parse_args()
    print(solve(args.input, args.seconds)[1], end="")
