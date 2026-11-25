"""Cover every edge."""

import argparse
import json
import sys
from functools import partial
from pathlib import Path

from shiftopt import run_pipeline
from shiftopt.cover import greedy_cover


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


def solve(stream, seconds):
    graph = read_graph(stream, "td")
    sets = {v: {(min(v, u), max(v, u)) for u in row} for v, row in graph.items()}
    universe = set().union(*sets.values())
    steps = [
        partial(greedy_cover, sets=sets, universe=universe, reverse=r)
        for r in (False, True)
    ]
    chosen = run_pipeline(steps, len, initial=list(sets), seconds=seconds)
    return len(chosen), [f"s vc {len(graph)} {len(chosen)}", *chosen]


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
