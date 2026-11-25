"""Build a guarded path decomposition of a hypergraph."""

import argparse
import json
import sys
from functools import partial
from operator import itemgetter
from pathlib import Path
from time import monotonic

from shiftopt import run_pipeline
from shiftopt.cover import greedy_cover


def construct(plan, deadline, edges, n, order):
    last = {v: i for i, e in enumerate(order) for v in edges[e]}
    active = {}
    lines = []
    width = 0
    for i, e in enumerate(order):
        if monotonic() >= deadline:
            return None
        active = {j: end for j, end in active.items() if end >= i}
        active[e] = max((last[v] for v in edges[e]), default=i)
        bag = set().union(*(edges[j] for j in active))
        width = max(width, len(active))
        lines.append(" ".join(map(str, ["b", i + 1, *sorted(bag)])))
        lines.extend(f"w {i + 1} {j} 1" for j in active)
        if i:
            lines.append(f"{i} {i + 1}")
    return width, [f"s htd {len(order)} {width} {n} {len(edges)}", *lines]


def single_bag(plan, deadline, edges, n):
    vertices = set().union(*edges.values())
    guards = greedy_cover(plan, deadline, sets=edges, universe=vertices)
    if guards is None:
        return None
    lines = [
        f"s htd 1 {len(guards)} {n} {len(edges)}",
        " ".join(map(str, ["b", 1, *sorted(vertices)])),
    ]
    lines.extend(f"w 1 {e} 1" for e in guards)
    return len(guards), lines


def solve(stream, seconds):
    rows = (
        line.split() for line in stream if line.strip() and not line.startswith("c")
    )
    _, _, n, m = next(rows)
    edges = {}
    for row in rows:
        e, *vertices = map(int, row)
        edges[e] = set(vertices)
    guards = list(edges)
    witnesses = [
        f"s htd 1 {m} {n} {m}",
        " ".join(map(str, ["b", 1, *sorted(set().union(*edges.values()))])),
        *(f"w 1 {e} 1" for e in guards),
    ]
    steps = [
        partial(construct, edges=edges, n=n, order=order)
        for order in (guards, guards[::-1])
    ]
    return run_pipeline(
        [partial(single_bag, edges=edges, n=n), *steps],
        itemgetter(0),
        initial=(len(edges), witnesses),
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
