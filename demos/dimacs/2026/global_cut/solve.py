"""Compare singleton cuts with cuts along graph traversals."""

import argparse
import json
from collections import deque
from functools import partial
from pathlib import Path
from time import monotonic

from shiftopt import run_pipeline

graph = []
edges = []


def score(side):
    return sum(w for u, v, w in edges if (u in side) != (v in side))


def singleton(plan, deadline):
    degree = [sum(w for v, w in row) for row in graph]
    return {degree.index(min(degree))}


def sweep(plan, deadline, root):
    seen = set()
    side = set()
    order = []
    value = 0
    best = score(plan)
    prefix = 0
    for start in [root, *range(len(graph))]:
        if start in seen:
            continue
        queue = deque([start])
        seen.add(start)
        while queue and monotonic() < deadline:
            v = queue.popleft()
            for u, w in graph[v]:
                value += -w if u in side else w
                if u not in seen:
                    queue.append(u)
                    seen.add(u)
            side.add(v)
            order.append(v)
            if len(side) < len(graph) and value < best:
                best, prefix = value, len(side)
    return set(order[:prefix]) if prefix else plan


def solve(stream, seconds=30.0):
    global graph, edges
    edges = []
    for row in map(str.split, stream):
        if row and row[0] == "p":
            _, kind, n, m = row
            graph = [[] for _ in range(int(n))]
        elif row and row[0] == "a":
            a, b, w = map(int, row[1:])
            if not 1 <= a <= len(graph) or not 1 <= b <= len(graph) or w < 0:
                raise ValueError("invalid cut edge")
            edges.append((a - 1, b - 1, w))
            if a != b:
                graph[a - 1].append((b - 1, w))
                graph[b - 1].append((a - 1, w))
    if kind != "glb" or len(edges) != int(m) or len(graph) < 2:
        raise ValueError("invalid glb header")
    plan = run_pipeline(
        [singleton, partial(sweep, root=0), partial(sweep, root=len(graph) - 1)],
        score,
        initial={0},
        seconds=seconds,
    )
    return {"solution": sorted(v + 1 for v in plan), "pipeline_score": score(plan)}


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
