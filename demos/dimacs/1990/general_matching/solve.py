"""Maximize matching cardinality in a general graph, then minimize edge cost."""

import argparse
import json
from pathlib import Path
from time import monotonic

import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp
from scipy.sparse import coo_matrix

from shiftopt import run_pipeline

edges = []
n = 0


def score(plan):
    return -len(plan), sum(edges[i][2] for i in plan)


def greedy(plan, deadline):
    used = set()
    chosen = []
    for i in sorted(range(len(edges)), key=edge_cost):
        a, b, _ = edges[i]
        if a not in used and b not in used:
            chosen.append(i)
            used.update((a, b))
    return chosen


def edge_cost(i):
    return edges[i][2]


def optimize(plan, deadline):
    if not edges:
        return []
    rows = [v - 1 for a, b, _ in edges for v in (a, b)]
    cols = np.repeat(np.arange(len(edges)), 2)
    matrix = coo_matrix(
        (np.ones(len(rows)), (rows, cols)), shape=(n, len(edges))
    ).tocsr()
    bonus = 1 + sum(abs(w) for _, _, w in edges)
    remaining = deadline - monotonic()
    if remaining <= 0:
        return None
    opts = {} if remaining == float("inf") else {"time_limit": remaining}
    result = milp(
        [w - bonus for _, _, w in edges],
        integrality=np.ones(len(edges)),
        bounds=Bounds(0, 1),
        constraints=LinearConstraint(matrix, 0, 1),
        options=opts,
    )
    if result.x is None:
        return None
    selected = np.rint(result.x)
    if np.any(matrix @ selected > 1):
        return None
    return np.flatnonzero(selected).tolist()


def solve(stream, seconds=30.0):
    global n, edges
    edges = []
    for row in map(str.split, stream):
        if row and row[0] == "p":
            _, kind, count, m = row
            n = int(count)
        elif row and row[0] == "e":
            a, b, *weight = map(int, row[1:])
            if a == b or min(a, b) < 1 or max(a, b) > n:
                raise ValueError("invalid matching edge")
            edges.append((a, b, weight[0] if weight else 0))
    if kind != "edge" or len(edges) != int(m):
        raise ValueError("edge count mismatch")
    plan = run_pipeline([greedy, optimize], score, initial=[], seconds=seconds)
    return {"solution": [edges[i][:2] for i in plan], "pipeline_score": score(plan)}


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
