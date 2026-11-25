"""Contract similar vertices and track the largest red degree."""

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


def contract(plan, deadline, graph, reverse):
    black = {v: set(row) for v, row in graph.items()}
    red = {v: set() for v in graph}
    width = 0
    sequence = []
    while len(black) > 1:
        if monotonic() >= deadline:
            return None
        pool = sorted(
            black, key=lambda v: (len(red[v]) + len(black[v]), -v if reverse else v)
        )[:12]
        _, v, w = min(
            (len((black[v] ^ black[w]) | red[v] | red[w]), v, w)
            for i, v in enumerate(pool)
            for w in pool[i + 1 :]
        )
        common = (black[v] & black[w]) - {v, w}
        mixed = (black[v] | black[w] | red[v] | red[w]) - {v, w} - common
        for u in common | mixed:
            black[u].discard(w)
            red[u].discard(w)
            if u in mixed:
                black[u].discard(v)
                red[u].add(v)
                width = max(width, len(red[u]))
        black[v], red[v] = common, mixed
        del black[w], red[w]
        width = max(width, len(mixed))
        sequence.append(f"{v} {w}")
    return width, sequence


def solve(stream, seconds):
    graph = read_graph(stream, "tww")
    steps = [partial(contract, graph=graph, reverse=r) for r in (False, True)]
    best = run_pipeline(steps, itemgetter(0), seconds=seconds)
    if best is None:
        raise TimeoutError("no complete contraction sequence within budget")
    return best


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
