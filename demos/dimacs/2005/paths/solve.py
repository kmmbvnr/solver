"""Tighten feasible path lengths and check the shortest-path tree inequalities."""

import argparse
import json
from collections import deque
from heapq import heappop, heappush
from pathlib import Path
from time import monotonic

from shiftopt import run_pipeline

graph = []
source = target = 0


def tree(plan, deadline):
    distance = [None] * len(graph)
    parent = [None] * len(graph)
    distance[source] = 0
    queue = deque([source])
    while queue:
        u = queue.popleft()
        for v, w in graph[u]:
            if distance[v] is None:
                distance[v] = distance[u] + w
                parent[v] = u
                queue.append(v)
    return distance, parent


def tighten(plan, deadline):
    distance, parent = [part.copy() for part in plan]
    visited = set()
    queue = [(0, source)]
    while queue:
        if monotonic() >= deadline:
            return None
        d, u = heappop(queue)
        if u in visited:
            continue
        visited.add(u)
        for v, w in graph[u]:
            if v not in visited and d + w <= distance[v]:
                distance[v] = d + w
                parent[v] = u
                heappush(queue, (d + w, v))
    return distance, parent


def score(plan):
    distances, _ = plan
    if target:
        return (
            distances[target] if distances[target] is not None else 0,
            sum(d for d in distances if d is not None),
        )
    return sum(d for d in distances if d is not None)


def solve(stream, seconds=30.0, start=1, end=0):
    global graph, source, target
    source, target = start, end
    count = 0
    for row in map(str.split, stream):
        if row and row[0] == "p":
            _, kind, n, m = row
            graph = [[] for _ in range(int(n) + 1)]
        elif row and row[0] == "a":
            u, v, w = map(int, row[1:])
            if not (0 < u < len(graph) and 0 < v < len(graph) and w >= 0):
                raise ValueError("expected nonnegative weighted arcs")
            graph[u].append((v, w))
            count += 1
    if (
        kind != "sp"
        or count != int(m)
        or not (0 < source < len(graph) and 0 <= target < len(graph))
    ):
        raise ValueError("invalid graph or query")
    plan = run_pipeline([tree, tighten], score, seconds=seconds)
    if plan is None:
        raise ValueError("no tree within budget")
    distances, parent = plan
    certified = all(
        distances[v] <= distances[u] + w
        for u, row in enumerate(graph)
        if distances[u] is not None
        for v, w in row
    )
    return {
        "solution": {"distance": distances[1:], "parent": parent[1:]},
        "pipeline_score": score(plan),
        "certified": certified,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "instance",
        type=Path,
        nargs="?",
        default=Path(__file__).with_name("example.txt"),
    )
    parser.add_argument("--seconds", type=float, default=30.0)
    parser.add_argument("--source", type=int, default=1)
    parser.add_argument(
        "--target", type=int, default=0, help="target node for a point-to-point query"
    )
    args = parser.parse_args()
    with args.instance.open() as stream:
        print(
            json.dumps(
                solve(stream, args.seconds, args.source, args.target), allow_nan=False
            )
        )
