"""Partition a graph into cliques with few edits."""

import argparse
import json
import sys
from functools import partial
from itertools import combinations
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


def pivot(plan, deadline, graph, reverse):
    remaining = set(graph)
    edits = []
    for v in sorted(graph, reverse=reverse):
        if monotonic() >= deadline:
            return None
        if v not in remaining:
            continue
        group = {v} | (graph[v] & remaining)
        remaining -= group
        edits.extend(
            (a, b) for a, b in combinations(sorted(group), 2) if b not in graph[a]
        )
        edits.extend((a, b) for a in group for b in graph[a] & remaining)
    return edits


def solve(stream, seconds):
    graph = read_graph(stream, "cep")
    initial = [(v, u) for v, row in graph.items() for u in row if u > v]
    steps = [partial(pivot, graph=graph, reverse=r) for r in (False, True)]
    edits = run_pipeline(steps, len, initial=initial, seconds=seconds)
    return len(edits), [f"{a} {b}" for a, b in edits]


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
