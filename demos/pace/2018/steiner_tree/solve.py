"""Connect terminals in a weighted undirected graph."""

import argparse
import json
import sys
from heapq import heappop, heappush
from pathlib import Path
from time import monotonic

from shiftopt import run_pipeline

graph = []
edges = []
terminals = []


def connect(root, deadline):
    dist = {root: 0}
    parent = {}
    queue = [(0, root)]
    while queue:
        if monotonic() >= deadline:
            return None
        value, a = heappop(queue)
        if value != dist[a]:
            continue
        for b, w, i in graph[a]:
            if value + w < dist.get(b, float("inf")):
                dist[b] = value + w
                parent[b] = (a, i)
                heappush(queue, (dist[b], b))
    connected = {root}
    chosen = []
    for v in terminals:
        while v not in connected:
            if v not in parent:
                raise ValueError("disconnected terminals")
            connected.add(v)
            v, i = parent[v]
            chosen.append(i)
    return {
        "cost": sum(edges[i][2] for i in chosen),
        "edges": [edges[i][:2] for i in chosen],
    }


def first_root(plan, deadline):
    return connect(terminals[0], deadline)


def last_root(plan, deadline):
    return connect(terminals[-1], deadline)


def score(plan):
    return plan["cost"]


def solve(stream, seconds=float("inf")):
    global graph, edges, terminals
    edges, terminals = [], []
    for line in stream:
        fields = line.split()
        if not fields:
            continue
        if fields[0] == "Nodes":
            n = int(fields[1])
        elif fields[0] == "E":
            a, b = map(int, fields[1:3])
            w = int(fields[3])
            if w < 0:
                raise ValueError("negative edge length")
            edges.append((a, b, w))
        elif fields[0] == "T":
            terminals.append(int(fields[1]))
    if not terminals:
        raise ValueError("expected an undirected STP graph with terminals")
    graph = [[] for _ in range(n + 1)]
    for i, (a, b, w) in enumerate(edges):
        graph[a].append((b, w, i))
        graph[b].append((a, w, i))

    plan = run_pipeline([first_root, last_root], score, seconds=seconds)
    if plan is None:
        raise ValueError("no feasible solution returned within the search budget")
    return score(plan), [
        f"VALUE {score(plan)}",
        *(f"{u} {v}" for u, v in plan["edges"]),
    ]


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
