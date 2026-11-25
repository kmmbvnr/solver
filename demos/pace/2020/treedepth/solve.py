"""Build a low-height elimination forest."""

import argparse
import json
import sys
from functools import partial
from operator import itemgetter
from pathlib import Path
from time import monotonic

from shiftopt import run_pipeline


def read_graph(stream, kind):
    rows = (
        line.split()
        for line in stream
        if line.strip() and not line.lstrip().startswith("c")
    )
    p, tag, n, m = next(rows)
    if (p, tag) != ("p", kind):
        raise ValueError(f"expected p {kind}")
    graph = {v: set() for v in range(1, int(n) + 1)}
    count = 0
    for row in rows:
        u, v = map(int, row)
        graph[u].add(v)
        graph[v].add(u)
        count += 1
    if count != int(m):
        raise ValueError("edge count mismatch")
    return graph


def split(plan, deadline, graph, reverse):
    parents = {v: 0 for v in graph}
    queue = [(set(graph), 0, 1)]
    height = 0
    while queue:
        if monotonic() >= deadline:
            return None
        vertices, parent, depth = queue.pop()
        if not vertices:
            continue
        root = max(
            (len(graph[v] & vertices), -v if reverse else v, v) for v in vertices
        )[2]
        parents[root] = parent
        height = max(height, depth)
        vertices.remove(root)
        while vertices:
            seed = vertices.pop()
            component = {seed}
            stack = [seed]
            while stack:
                adjacent = graph[stack.pop()] & vertices
                vertices -= adjacent
                component.update(adjacent)
                stack.extend(adjacent)
            queue.append((component, root, depth + 1))
    return height, [height, *parents.values()]


def solve(stream, seconds):
    graph = read_graph(stream, "tdp")
    n = len(graph)
    steps = [partial(split, graph=graph, reverse=r) for r in (False, True)]
    return run_pipeline(
        steps, itemgetter(0), initial=(n, [n, *range(n)]), seconds=seconds
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "instance", nargs="?", default=str(Path(__file__).with_name("example.txt"))
    )
    parser.add_argument("--seconds", type=float, default=30)
    parser.add_argument(
        "--json",
        action="store_true",
        help="include the objective in machine-readable output",
    )
    args = parser.parse_args()
    if args.instance == "-":
        value, lines = solve(sys.stdin, args.seconds)
    else:
        with open(args.instance) as stream:
            value, lines = solve(stream, args.seconds)
    if args.json:
        print(json.dumps({"objective": value, "solution": lines}, allow_nan=False))
    else:
        sys.stdout.writelines(str(line) + "\n" for line in lines)
