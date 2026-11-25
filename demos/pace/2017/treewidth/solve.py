"""Compare degree, fill and reverse tie-breaking in tree decompositions."""

import argparse
import json
import sys
from functools import partial
from pathlib import Path

from shiftopt import run_pipeline
from shiftopt.elimination import eliminate


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


def construct(plan, deadline, graph, min_fill, reverse=False):
    result = eliminate(graph, deadline, min_fill=min_fill, reverse=reverse)
    if result is None:
        return None
    bags, _ = result
    index = {v: i for i, (v, row) in enumerate(bags, 1)}
    width = max((len(row) for _, row in bags), default=0)
    lines = [f"s td {len(bags)} {width + 1} {len(graph)}"]
    for i, (v, row) in enumerate(bags, 1):
        lines.append(" ".join(map(str, ["b", i, v, *row])))
    for i, (_, row) in enumerate(bags, 1):
        if i < len(bags):
            parent = min((index[u] for u in row), default=len(bags))
            lines.append(f"{i} {parent}")
    return width, lines


def objective(plan):
    return plan[0]


def solve(stream, seconds):
    graph = read_graph(stream, "tw")
    n = len(graph)
    initial = (n - 1, [f"s td 1 {n} {n}", " ".join(map(str, ["b", 1, *graph]))])
    steps = [
        partial(construct, graph=graph, min_fill=False),
        partial(construct, graph=graph, min_fill=True),
    ]
    steps.append(partial(construct, graph=graph, min_fill=True, reverse=True))
    return run_pipeline(steps, objective, initial=initial, seconds=seconds)


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
