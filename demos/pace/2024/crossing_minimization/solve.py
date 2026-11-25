"""Order one side of a bipartite graph to reduce crossings."""

import argparse
import json
import sys
from functools import partial
from operator import itemgetter
from pathlib import Path
from statistics import mean, median

from shiftopt import run_pipeline


def crossings(order, edges, n):
    counts = [0] * (n + 1)
    total = seen = 0
    for v in order:
        for x in edges[v]:
            i = x
            total += seen
            while i:
                total -= counts[i]
                i -= i & -i
        for i in edges[v]:
            seen += 1
            while i <= n:
                counts[i] += 1
                i += i & -i
    return total


def reorder(plan, deadline, edges, n, center):
    order = sorted(edges, key=lambda v: center(edges[v]) if edges[v] else 0)
    return crossings(order, edges, n), order


def solve(stream, seconds):
    rows = (
        line.split() for line in stream if line.strip() and not line.startswith("c")
    )
    _, _, a, b, m, *cw = next(rows)
    n, b = int(a), int(b)
    if cw:
        for _ in range(n + b):
            next(rows)
    edges = {v: [] for v in range(n + 1, n + b + 1)}
    for row in rows:
        u, v = map(int, row)
        edges[v].append(u)
    order = list(edges)
    steps = [partial(reorder, edges=edges, n=n, center=f) for f in (median, mean)]
    return run_pipeline(
        steps,
        itemgetter(0),
        initial=(crossings(order, edges, n), order),
        seconds=seconds,
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
