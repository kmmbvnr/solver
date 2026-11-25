"""Construct and prune degree-constrained Steiner trees."""

import argparse
import json
from functools import partial
from heapq import heappop, heappush
from pathlib import Path
from random import Random
from time import monotonic

from shiftopt import run_pipeline

graph = {}
limits = []
terminals = set()


def construct(seed, deadline):
    rng = Random(seed)
    root = rng.choice(sorted(terminals))
    degrees = {root: 0}
    needed = terminals - {root}
    edges, queue = [], []
    current = root
    while needed and monotonic() < deadline:
        for v, cost in graph.get(current, ()):
            if v not in degrees:
                priority = cost * (1 + rng.random() if seed else 1)
                heappush(queue, (priority, cost, current, v))
        while queue:
            _, cost, u, v = heappop(queue)
            if v not in degrees and degrees[u] < limits[u] and limits[v] > 0:
                if limits[v] > 1 or v in needed:
                    break
        else:
            return None
        degrees[v] = 1
        degrees[u] += 1
        edges.append((u, v, cost))
        needed.discard(v)
        current = v
    if needed:
        return None
    keep = set(terminals)
    tree = []
    for u, v, cost in reversed(edges):
        if v in keep:
            keep.add(u)
            tree.append((u, v, cost))
    return tree


def propose(plan, deadline, seed):
    return construct(seed, deadline)


def score(plan):
    return sum(cost for _, _, cost in plan)


def solve(stream, seconds=30.0):
    global graph, limits, terminals
    graph, limits, terminals = {}, [0], set()
    for row in map(str.split, stream):
        if not row:
            continue
        if row[0] == "E":
            u, v, cost = map(int, row[1:])
            graph.setdefault(u, []).append((v, cost))
            graph.setdefault(v, []).append((u, cost))
        elif row[0] == "T":
            terminals.add(int(row[1]))
        elif row[0] == "MD":
            limits.append(int(row[1]))
        elif row[0] == "Nodes":
            n = int(row[1])
    if len(limits) != n + 1 or not terminals:
        raise ValueError(
            "expected one maximum degree per vertex and at least one terminal"
        )
    plan = run_pipeline(
        (partial(propose, seed=i) for i in range(128)), score, seconds=seconds
    )
    if plan is None:
        raise ValueError("no feasible degree-constrained tree found")
    return {"solution": plan, "pipeline_score": score(plan)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "instance",
        type=Path,
        nargs="?",
        default=Path(__file__).with_name("example.txt"),
    )
    parser.add_argument("--seconds", type=float, default=30.0)
    args = parser.parse_args()
    with args.instance.open() as stream:
        print(json.dumps(solve(stream, args.seconds), allow_nan=False))
