"""Refine approximate nearest neighbors using sorted random projections."""

import argparse
import json
from functools import partial
from pathlib import Path
from time import monotonic

import numpy as np

from shiftopt import run_pipeline

points = queries = None


def score(plan):
    return float(np.linalg.norm(points[plan] - queries, axis=1).sum())


def project(plan, deadline, seed):
    direction = np.random.default_rng(seed).normal(size=points.shape[1])
    order = np.argsort(points @ direction)
    projected = points[order] @ direction
    positions = np.searchsorted(projected, queries @ direction)
    best = plan.copy()
    for i, pos in enumerate(positions):
        if monotonic() >= deadline:
            break
        candidates = np.append(order[max(0, pos - 16) : pos + 16], best[i])
        distances = np.linalg.norm(points[candidates] - queries[i], axis=1)
        best[i] = candidates[distances.argmin()]
    return best


def solve(stream, seconds=30.0):
    global points, queries
    n, q, dim = map(int, next(stream).split())
    rows = np.loadtxt(stream, ndmin=2)
    if n < 1 or q < 0 or rows.shape != (n + q, dim) or not np.all(np.isfinite(rows)):
        raise ValueError("expected n data points followed by q queries")
    points, queries = rows[:n], rows[n:]
    steps = [partial(project, seed=i) for i in range(8)]
    plan = run_pipeline(steps, score, initial=np.zeros(q, dtype=int), seconds=seconds)
    return {"solution": plan.tolist(), "pipeline_score": score(plan)}


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
