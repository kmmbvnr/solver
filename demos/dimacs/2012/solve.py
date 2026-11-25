"""Balanced bisection of unweighted undirected METIS graphs."""
import argparse
import json
from pathlib import Path
from collections import deque
from time import monotonic

from shiftopt import run_pipeline


def solve(stream, seconds=float("inf")):
    lines = (line.strip() for line in stream if not line.lstrip().startswith("%"))
    n, m, *fmt = map(int, next(lines).split())
    if fmt and fmt != [0]:
        raise ValueError("expected unweighted METIS format")
    graph = [set(int(v) - 1 for v in row.split()) for row in lines]
    if len(graph) != n or sum(map(len, graph)) != 2 * m:
        raise ValueError("invalid METIS adjacency counts")

    def cut(side):
        return sum(side[v] != side[u] for u, row in enumerate(graph) for v in row) // 2

    def breadth_first(plan, deadline):
        seen = set()
        order = []
        for root in range(n):
            if root in seen:
                continue
            seen.add(root)
            queue = deque([root])
            while queue:
                u = queue.popleft()
                order.append(u)
                for v in sorted(graph[u] - seen):
                    seen.add(v)
                    queue.append(v)
        side = [1] * n
        for v in order[:n // 2]:
            side[v] = 0
        return side

    def swap(plan, deadline):
        side = plan.copy()
        def gain(u):
            return sum(1 if side[v] != side[u] else -1 for v in graph[u])
        for _ in range(6):
            groups = [[], []]
            for u in range(n):
                groups[side[u]].append(u)
            for group in groups:
                group.sort(key=gain, reverse=True)
            changed = False
            for a, b in zip(*groups):
                if monotonic() >= deadline:
                    return side
                if gain(a) + gain(b) > 2 * (b in graph[a]):
                    side[a], side[b] = side[b], side[a]
                    changed = True
            if not changed:
                break
        return side

    plan = run_pipeline([breadth_first, swap], cut, seconds=seconds)
    if plan is None:
        raise ValueError("no feasible solution returned within the search budget")
    return {"pipeline_score": cut(plan), "solution": plan}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("instance", type=Path, nargs="?", default=Path(__file__).with_name("example.txt"))
    parser.add_argument("--seconds", type=float, default=float("inf"), help="cooperative pipeline budget")
    args = parser.parse_args()
    with args.instance.open() as stream:
        print(json.dumps(solve(stream, args.seconds), allow_nan=False))
