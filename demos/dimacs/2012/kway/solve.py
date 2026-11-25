"""Build balanced k-way partitions for edge cut or maximum communication volume."""

import argparse
import json
from collections import Counter, deque
from functools import partial
from pathlib import Path

from shiftopt import run_pipeline

graph = []
parts = 2
metric = "volume"


def score(plan):
    if metric == "cut":
        return sum(plan[u] != plan[v] for v, row in enumerate(graph) for u in row) // 2
    volume = Counter()
    for v, row in enumerate(graph):
        volume[plan[v]] += len({plan[u] for u in row} - {plan[v]})
    return max(volume.values(), default=0)


def traverse(plan, deadline, reverse):
    seen = set()
    order = []
    for root in range(len(graph)):
        if root in seen:
            continue
        queue = deque([root])
        seen.add(root)
        while queue:
            v = queue.popleft()
            order.append(v)
            for u in sorted(graph[v], reverse=reverse):
                if u not in seen:
                    queue.append(u)
                    seen.add(u)
    labels = plan.copy()
    for i, v in enumerate(order):
        labels[v] = i * parts // len(order)
    return labels


def solve(stream, seconds=30.0, k=2, objective="volume"):
    global graph, parts, metric
    parts, metric = k, objective
    rows = (r for r in stream if not r.lstrip().startswith("%"))
    n, m, *fmt = map(int, next(rows).split())
    graph = [set(int(x) - 1 for x in row.split()) for row in rows]
    if (
        (fmt and fmt != [0])
        or len(graph) != n
        or sum(map(len, graph)) != 2 * m
        or not 2 <= k <= n
    ):
        raise ValueError("expected unweighted METIS graph and 2 <= parts <= n")
    seed = [i * k // n for i in range(n)]
    plan = run_pipeline(
        [partial(traverse, reverse=False), partial(traverse, reverse=True)],
        score,
        initial=seed,
        seconds=seconds,
    )
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
    parser.add_argument("--parts", type=int, default=2)
    parser.add_argument("--objective", choices=("cut", "volume"), default="volume")
    args = parser.parse_args()
    with args.instance.open() as stream:
        print(
            json.dumps(
                solve(stream, args.seconds, args.parts, args.objective), allow_nan=False
            )
        )
