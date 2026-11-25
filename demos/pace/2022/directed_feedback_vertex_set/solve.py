"""Delete vertices until all surviving arcs point forward."""

import argparse
import json
import sys
from functools import partial
from pathlib import Path
from time import monotonic

from shiftopt import run_pipeline


def remove_backward(plan, deadline, graph, order):
    index = {v: i for i, v in enumerate(order)}
    removed = set()
    for v in order:
        if monotonic() >= deadline:
            return None
        if any(index[u] <= index[v] and u not in removed for u in graph[v]):
            removed.add(v)
    return sorted(removed)


def solve(stream, seconds):
    rows = (line.strip() for line in stream if not line.startswith("%"))
    n, m, *flags = map(int, next(rows).split())
    graph = {v: set(map(int, next(rows).split())) for v in range(1, n + 1)}
    incoming = dict.fromkeys(graph, 0)
    for row in graph.values():
        for u in row:
            incoming[u] += 1
    ranked = sorted(graph, key=lambda v: incoming[v] - len(graph[v]))
    steps = [
        partial(remove_backward, graph=graph, order=o)
        for o in (list(graph), ranked, ranked[::-1])
    ]
    answer = run_pipeline(steps, len, initial=list(graph), seconds=seconds)
    return len(answer), answer


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
