"""Remove clique components and lift four edits from the reduced graph."""

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


def reduce_cliques(plan, deadline, graph):
    unseen = set(plan)
    kept = set(plan)
    while unseen and monotonic() < deadline:
        v = unseen.pop()
        component = {v}
        stack = [v]
        while stack:
            row = graph[stack.pop()] & unseen
            unseen -= row
            component.update(row)
            stack.extend(row)
        if all(len(graph[u]) == len(component) - 1 for u in component):
            kept -= component
    return sorted(kept)


def pivot_edits(graph, vertices):
    remaining = set(vertices)
    edits = []
    for v in vertices:
        if v in remaining:
            group = {v} | (graph[v] & remaining)
            remaining -= group
            edits.extend(
                (a, b) for a, b in combinations(sorted(group), 2) if b not in graph[a]
            )
            edits.extend((a, b) for a in group for b in graph[a] & remaining)
    return edits


def solve(stream, seconds):
    graph = read_graph(stream, "cep")
    kept = run_pipeline(
        [partial(reduce_cliques, graph=graph)],
        len,
        initial=list(graph),
        seconds=seconds,
    )
    ids = {v: i for i, v in enumerate(kept, 1)}
    deleted = [(v, u) for v in kept for u in graph[v] if v < u]
    lines = [
        0,
        f"p cep {len(kept)} {len(deleted)}",
        *(f"{ids[a]} {ids[b]}" for a, b in deleted),
    ]
    inserted = [(a, b) for a, b in combinations(kept, 2) if b not in graph[a]]
    for edits in (
        deleted,
        inserted,
        pivot_edits(graph, kept),
        pivot_edits(graph, kept[::-1]),
    ):
        lines.append(len(edits))
        lines.extend(f"{a} {b}" for a, b in edits)
    return len(kept), lines


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
