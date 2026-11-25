"""Optimize a feasible low-rank factor of the torus semidefinite relaxation."""

import argparse
import json
from pathlib import Path
from time import monotonic

import numpy as np

from shiftopt import run_pipeline

edges = []
neighbors = []


def score(vectors):
    return -sum(w * (1 - vectors[u].dot(vectors[v])) for u, v, w in edges)


def descend(vectors, deadline):
    for _ in range(100):
        change = 0.0
        for v, (indices, weights) in enumerate(neighbors):
            if monotonic() >= deadline:
                return vectors
            field = weights @ vectors[indices]
            norm = np.linalg.norm(field)
            if norm:
                change += norm + field @ vectors[v]
                vectors[v] = -field / norm
        if change < 1e-8 * max(1, len(edges)):
            break
    return vectors


def cut(plan, deadline):
    return descend(plan.copy(), deadline)


def lift(plan, deadline):
    rng = np.random.default_rng(7)
    extra = rng.normal(0, 0.2, (len(plan), min(7, len(plan))))
    lifted = np.column_stack((plan, extra))
    lifted /= np.linalg.norm(lifted, axis=1)[:, None]
    return descend(lifted, deadline)


def solve(stream, seconds=30.0):
    global edges, neighbors
    n, m = map(int, next(stream).split())
    rows = [[] for _ in range(n)]
    edges = []
    for row in stream:
        if row.strip():
            u, v, w = map(int, row.split())
            if not (1 <= u <= n and 1 <= v <= n and u != v):
                raise ValueError("invalid edge")
            rows[u - 1].append((v - 1, w))
            rows[v - 1].append((u - 1, w))
            edges.append((u - 1, v - 1, w))
    if len(edges) != m:
        raise ValueError("edge count mismatch")
    neighbors = [
        (np.array([v for v, w in r], dtype=int), np.array([w for v, w in r]))
        for r in rows
    ]
    plan = run_pipeline([cut, lift], score, initial=np.ones((n, 1)), seconds=seconds)
    return {"solution": plan.tolist(), "pipeline_score": float(score(plan))}


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
