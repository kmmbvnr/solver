"""Prize-collecting, rooted prize-collecting and maximum-weight connected subgraphs."""

import argparse
import json
from heapq import heappop, heappush
from pathlib import Path
from time import monotonic

from shiftopt import run_pipeline

adj = []
prizes = []
root = None
node_weighted = False


def read_instance(stream):
    global adj, prizes, root, node_weighted
    root, node_weighted = None, False
    adj, prizes = [], []
    for line in stream:
        f = line.split()
        if not f:
            continue
        if f[0] == "Nodes":
            n = int(f[1])
            adj = [[] for _ in range(n + 1)]
            prizes = [0.0] * (n + 1)
        elif f[0] == "E":
            a, b = map(int, f[1:3])
            w = float(f[3]) if len(f) == 4 else 0.0
            adj[a].append((b, w))
            adj[b].append((a, w))
        elif f[0] in ("T", "TP"):
            v, p = int(f[1]), float(f[2])
            prizes[v] = p
            node_weighted |= f[0] == "T"
        elif f[0] == "RootP":
            root = int(f[1])
    if len(adj) < 2:
        raise ValueError("missing STP graph")


def score(tree):
    reward = sum(prizes[v] for v in tree["vertices"])
    if node_weighted:
        return -reward
    return sum(prizes) - reward + sum(w for a, b, w in tree["edges"])


def singleton(plan, deadline):
    v = root or max(range(1, len(adj)), key=prizes.__getitem__)
    return {"vertices": [v], "edges": []}


def rooted_subtree(start, guided, deadline):
    dist = {start: 0.0}
    parent = {}
    order = []
    heap = [(0.0, start)]
    while heap:
        if monotonic() >= deadline:
            return None
        d, u = heappop(heap)
        if d != dist[u]:
            continue
        order.append(u)
        for v, w in adj[u]:
            increment = w + (max(0.0, -prizes[v]) if node_weighted else 0.0)
            if guided:
                increment = (increment + 1) / (1 + max(0.0, prizes[v]))
            new = d + increment
            if new < dist.get(v, float("inf")):
                dist[v] = new
                parent[v] = u, w
                heappush(heap, (new, v))
    # Optimal rooted connected subtree of this particular shortest-path tree.
    profit = prizes.copy()
    keep = set()
    for v in reversed(order[1:]):
        u, w = parent[v]
        if profit[v] > w:
            profit[u] += profit[v] - w
            keep.add(v)
    active = {start}
    edges = []
    for v in order[1:]:
        u, w = parent[v]
        if u in active and v in keep:
            active.add(v)
            edges.append((u, v, w))
    return {"vertices": sorted(active), "edges": edges}


def cheapest_paths(plan, deadline):
    return rooted_subtree(plan["vertices"][0], False, deadline)


def reward_guided(plan, deadline):
    starts = (
        [root]
        if root
        else sorted(range(1, len(adj)), key=prizes.__getitem__, reverse=True)[:4]
    )
    best, value = plan, score(plan)
    for start in starts:
        candidate = rooted_subtree(start, True, deadline)
        if candidate is None:
            break
        cost = score(candidate)
        if cost < value:
            best, value = candidate, cost
    return best


def solve(stream, seconds=30.0):
    read_instance(stream)
    plan = run_pipeline(
        [singleton, cheapest_paths, reward_guided], score, seconds=seconds
    )
    if plan is None:
        raise ValueError("no tree within budget")
    return {"pipeline_score": score(plan), "solution": plan}


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
