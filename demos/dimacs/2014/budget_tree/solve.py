"""Grow a rooted revenue tree subject to a budget and a hop limit."""

import argparse
import json
from functools import partial
from heapq import heapify, heappop, heappush
from pathlib import Path
from time import monotonic

from shiftopt import run_pipeline

graph = {}
reward = {}
root = budget = hops = 0


def grow(plan, deadline, by_ratio):
    tree = {root: 0}
    edges = []
    spent = 0
    while monotonic() < deadline:
        queue = [(0, depth, v, ()) for v, depth in tree.items()]
        heapify(queue)
        best = {}
        chosen = ()
        priority = 0
        while queue and monotonic() < deadline:
            cost, depth, v, path = heappop(queue)
            if cost > best.get((v, depth), cost):
                continue
            value = reward.get(v, 0) / (max(cost, 1) if by_ratio else 1)
            if path and value > priority:
                chosen, priority = path, value
            if depth >= hops:
                continue
            for u, weight in graph.get(v, ()):
                total = cost + weight
                if (
                    u in tree
                    or any(edge[1] == u for edge in path)
                    or total + spent > budget
                ):
                    continue
                if total < best.get((u, depth + 1), float("inf")):
                    best[u, depth + 1] = total
                    heappush(queue, (total, depth + 1, u, path + ((v, u, weight),)))
        if not chosen:
            break
        for v, u, weight in chosen:
            edges.append((v, u))
            tree[u] = tree[v] + 1
            spent += weight
    return {"vertices": sorted(tree), "edges": edges, "cost": spent}


def score(plan):
    return -sum(reward.get(v, 0) for v in plan["vertices"])


def solve(stream, seconds=30.0):
    global graph, reward, root, budget, hops
    graph, reward = {}, {}
    params = {}
    for row in map(str.split, stream):
        if not row:
            continue
        if row[0] in ("Root", "Budget", "HopLimit"):
            params[row[0]] = int(row[1])
        elif row[0] == "E":
            a, b, cost = map(int, row[1:])
            graph.setdefault(a, []).append((b, cost))
            graph.setdefault(b, []).append((a, cost))
        elif row[0] == "PV":
            reward[int(row[1])] = int(row[2])
    root, budget, hops = (params[key] for key in ("Root", "Budget", "HopLimit"))
    seed = {"vertices": [root], "edges": [], "cost": 0}
    plan = run_pipeline(
        [partial(grow, by_ratio=True), partial(grow, by_ratio=False)],
        score,
        initial=seed,
        seconds=seconds,
    )
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
