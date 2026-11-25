"""Color vertices by first fit in two vertex orders."""
import argparse
import json
from pathlib import Path
from functools import partial
from heapq import heappop, heappush
from time import monotonic

from shiftopt import assignment_constructor, run_pipeline


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


class ColoringState:
    def __init__(self, neighbors, limit):
        self.neighbors = neighbors
        self.colors = [0] * len(neighbors)
        self.classes = [0] * (limit + 1)

    def options(self, vertex, rng):
        colors = list(range(1, len(self.classes)))
        rng.shuffle(colors)
        for color in colors:
            yield color, self.neighbors[vertex] & self.classes[color]

    def remove(self, vertex):
        self.classes[self.colors[vertex]] ^= 1 << vertex
        self.colors[vertex] = 0

    def assign(self, vertex, color):
        self.classes[color] |= 1 << vertex
        self.colors[vertex] = color

    def finish(self):
        return self.colors


def start_coloring(neighbors, limit, rng):
    order = list(range(len(neighbors)))
    rng.shuffle(order)
    order.sort(key=lambda v: neighbors[v].bit_count())
    return ColoringState(neighbors, limit), order


def fewer_colors(plan, deadline):
    if not plan:
        return plan
    neighbors = [sum(1 << u for u in row) for row in graph]
    limit = score(plan) - 1
    while limit > 0 and monotonic() < deadline:
        build = assignment_constructor(partial(start_coloring, neighbors, limit), moves_per_start=8 * len(plan),
                                       starts=8, conflict_weight=1, seed=1)
        candidate = build(plan, deadline)
        if candidate is None:
            break
        plan, limit = candidate, score(candidate) - 1
    return plan


def solve(stream, seconds=float("inf"), *, reconstruct=False):
    global graph
    graph = read_graph(stream)

    steps = [by_degree, saturation, by_color_class]
    if reconstruct:
        steps.append(fewer_colors)
    plan = run_pipeline(steps, score, seconds=seconds)
    if plan is None:
        raise ValueError("no feasible solution returned within the search budget")
    return {"pipeline_score": score(plan), "solution": plan}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("instance", type=Path, nargs="?", default=Path(__file__).with_name("example.txt"))
    parser.add_argument("--seconds", type=float, default=float("inf"), help="cooperative pipeline budget")
    parser.add_argument("--reconstruct", action="store_true", help="try successively smaller color limits")
    args = parser.parse_args()
    with args.instance.open() as stream:
        print(json.dumps(solve(stream, args.seconds, reconstruct=args.reconstruct), allow_nan=False))
