"""Compare a feasible integral flow with a minimum-cost flow."""

import argparse
import json
from pathlib import Path
from time import monotonic

import numpy as np
from scipy.optimize import linprog
from scipy.sparse import coo_matrix

from shiftopt import run_pipeline

matrix = balance = bounds = costs = None


def optimize(objective, deadline):
    remaining = deadline - monotonic()
    if remaining <= 0:
        return None
    options = {} if remaining == float("inf") else {"time_limit": remaining}
    result = linprog(
        objective,
        A_eq=matrix,
        b_eq=balance,
        bounds=bounds,
        method="highs-ds",
        options=options,
    )
    if result.x is None:
        return None
    plan = np.rint(result.x).astype(np.int64)
    if (
        not np.array_equal(matrix @ plan, balance)
        or np.any(plan < bounds[:, 0])
        or np.any(plan > bounds[:, 1])
    ):
        return None
    return plan.tolist()


def feasible(plan, deadline):
    return optimize(np.zeros(len(costs)), deadline)


def cheapest(plan, deadline):
    return optimize(costs, deadline)


def score(plan):
    return sum(int(c) * x for c, x in zip(costs, plan))


def solve(stream, seconds=30.0):
    global matrix, balance, bounds, costs
    arcs = []
    for row in map(str.split, stream):
        if row and row[0] == "p":
            _, kind, n, m = row
            balance = np.zeros(int(n), dtype=np.int64)
        elif row and row[0] == "n":
            balance[int(row[1]) - 1] = int(row[2])
        elif row and row[0] == "a":
            arcs.append(tuple(map(int, row[1:])))
    if kind != "min" or len(arcs) != int(m):
        raise ValueError("invalid flow header")
    rows = []
    cols = []
    values = []
    for i, (u, v, lower, upper, cost) in enumerate(arcs):
        rows.extend((u - 1, v - 1))
        cols.extend((i, i))
        values.extend((1, -1))
    matrix = coo_matrix((values, (rows, cols)), shape=(int(n), len(arcs))).tocsr()
    bounds = np.array([(a[2], a[3]) for a in arcs], dtype=np.int64).reshape(-1, 2)
    costs = np.array([a[4] for a in arcs], dtype=np.int64)
    seed = (
        [0] * len(arcs)
        if not np.any(balance)
        and np.all(bounds[:, 0] <= 0)
        and np.all(bounds[:, 1] >= 0)
        else None
    )
    plan = run_pipeline(
        [feasible, cheapest] if arcs else [], score, initial=seed, seconds=seconds
    )
    if plan is None:
        raise ValueError("no feasible integral flow found")
    return {"solution": plan, "pipeline_score": score(plan)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "instance",
        type=Path,
        nargs="?",
        default=Path(__file__).with_name("example.txt"),
    )
    parser.add_argument("--seconds", type=float, default=30.0)
    args = parser.parse_args()
    with args.instance.open() as stream:
        print(json.dumps(solve(stream, args.seconds), allow_nan=False))
