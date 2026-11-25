"""Color vertices by first fit in two vertex orders."""
import argparse
import json
from pathlib import Path
from functools import partial
from heapq import heappop, heappush
from time import monotonic

from shiftopt import run_pipeline


graph = []


def read_graph(stream):
    graph = None
    count = 0
    for line in stream:
        fields = line.split()
        if not fields or fields[0] == "c":
            continue
        if fields[:2] == ["p", "edge"]:
            n, m = map(int, fields[2:])
            graph = [set() for _ in range(n)]
        elif fields[0] == "e" and graph is not None:
            a, b = (int(v) - 1 for v in fields[1:])
            if not (0 <= a < n and 0 <= b < n and a != b):
                raise ValueError("invalid edge")
            graph[a].add(b)
            graph[b].add(a)
            count += 1
        else:
            raise ValueError(line)
    if graph is None or count != m:
        raise ValueError("missing header or edge count mismatch")
    return graph


def degree_order(v):
    return -len(graph[v])


def class_order(plan, v):
    return -plan[v], -len(graph[v])


def color(order):
    colors = [0] * len(graph)
    for v in order:
        used = {colors[u] for u in graph[v]}
        k = 1
        while k in used:
            k += 1
        colors[v] = k
    return colors


def by_degree(plan, deadline):
    return color(sorted(range(len(graph)), key=degree_order))


def saturation(plan, deadline):
    colors = [0] * len(graph)
    used = [set() for _ in graph]
    queue = []
    for v, row in enumerate(graph):
        heappush(queue, (0, -len(row), v))
    while queue:
        if monotonic() >= deadline:
            return None
        rank, _, v = heappop(queue)
        if colors[v] or -rank != len(used[v]):
            continue
        k = 1
        while k in used[v]:
            k += 1
        colors[v] = k
        for u in graph[v]:
            if not colors[u] and k not in used[u]:
                used[u].add(k)
                heappush(queue, (-len(used[u]), -len(graph[u]), u))
    return colors


def by_color_class(plan, deadline):
    return color(sorted(range(len(graph)), key=partial(class_order, plan)))


def score(plan):
    return max(plan, default=0)


def solve(stream, seconds=float("inf")):
    global graph
    graph = read_graph(stream)

    plan = run_pipeline([by_degree, saturation, by_color_class], score, seconds=seconds)
    if plan is None:
        raise ValueError("no feasible solution returned within the search budget")
    return {"pipeline_score": score(plan), "solution": plan}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("instance", type=Path, nargs="?", default=Path(__file__).with_name("example.txt"))
    parser.add_argument("--seconds", type=float, default=float("inf"), help="cooperative pipeline budget")
    args = parser.parse_args()
    with args.instance.open() as stream:
        print(json.dumps(solve(stream, args.seconds), allow_nan=False))
