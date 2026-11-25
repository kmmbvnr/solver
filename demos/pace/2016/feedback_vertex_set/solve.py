"""Construct induced forests and return the complementary feedback vertex set."""

import argparse
import json
import sys
from functools import partial
from pathlib import Path
from time import monotonic

from shiftopt import run_pipeline


def forest(order, edges, deadline):
    parent = {v: v for v in order}
    kept = set()
    for v in order:
        if monotonic() >= deadline:
            break
        roots = []
        for u in edges[v]:
            if u == v:
                roots.append(None)
                break
            if u in kept:
                while parent[u] != u:
                    parent[u] = parent[parent[u]]
                    u = parent[u]
                roots.append(u)
        if None not in roots and len(set(roots)) == len(roots):
            kept.add(v)
            for root in roots:
                parent[root] = v
    return sorted(set(order) - kept)


def propose(plan, deadline, edges, reverse):
    order = sorted(edges, key=lambda v: (len(edges[v]), v), reverse=reverse)
    return forest(order, edges, deadline)


def solve(stream, seconds):
    edges = {}
    for line in stream:
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        u, v = line.split()
        edges.setdefault(u, []).append(v)
        edges.setdefault(v, []).append(u)
    plan = run_pipeline(
        [partial(propose, edges=edges, reverse=r) for r in (False, True)],
        len,
        initial=sorted(edges),
        seconds=seconds,
    )
    return len(plan), plan


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
