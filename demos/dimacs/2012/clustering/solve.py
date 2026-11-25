"""Find communities by maximizing unweighted graph modularity."""

import argparse
import json
from collections import Counter
from functools import partial
from pathlib import Path
from time import monotonic

from shiftopt import run_pipeline

graph = []
volume = 0


def score(labels):
    if not volume:
        return 0.0
    degrees = Counter()
    internal = 0
    for v, neighbors in enumerate(graph):
        degrees[labels[v]] += len(neighbors)
        internal += sum(labels[u] == labels[v] for u in neighbors)
    return sum((k / volume) ** 2 for k in degrees.values()) - internal / volume


def move(plan, deadline, reverse):
    labels = plan.copy()
    totals = Counter()
    for v, label in enumerate(labels):
        totals[label] += len(graph[v])
    order = range(len(graph) - 1, -1, -1) if reverse else range(len(graph))
    for _ in range(20):
        changed = False
        for v in order:
            if monotonic() >= deadline:
                return labels
            counts = Counter(labels[u] for u in graph[v])
            old = labels[v]
            degree = len(graph[v])
            totals[old] -= degree
            best = old
            gain = counts[old] * volume - degree * totals[old]
            for label, inside in counts.items():
                value = inside * volume - degree * totals[label]
                if value > gain:
                    best, gain = label, value
            labels[v] = best
            totals[best] += degree
            changed |= best != old
        if not changed:
            break
    return labels


def solve(stream, seconds=30.0):
    global graph, volume
    lines = (r for r in stream if not r.lstrip().startswith("%"))
    n, m, *fmt = map(int, next(lines).split())
    if fmt and fmt != [0]:
        raise ValueError("expected unweighted METIS graph")
    graph = [set(int(x) - 1 for x in row.split()) for row in lines]
    volume = sum(map(len, graph))
    if (
        len(graph) != n
        or volume != 2 * m
        or any(
            u < 0 or u >= n or u == v or v not in graph[u]
            for v, row in enumerate(graph)
            for u in row
        )
    ):
        raise ValueError("invalid undirected graph")
    plan = run_pipeline(
        [partial(move, reverse=False), partial(move, reverse=True)],
        score,
        initial=list(range(n)),
        seconds=seconds,
    )
    return {"solution": plan, "pipeline_score": score(plan), "modularity": -score(plan)}


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
