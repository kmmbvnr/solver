"""Build a feasible flow, repair it along residual paths and certify it by a cut."""

import argparse
import json
from collections import deque
from pathlib import Path
from time import monotonic

from shiftopt import run_pipeline

arcs = []
adj = {}
source = sink = 0


def search(flow, reverse):
    parent = {source: None}
    queue = deque([source])
    while queue and sink not in parent:
        u = queue.popleft()
        for v, i, direction in adj.get(u, ()):
            capacity = arcs[i][2] - flow[i] if direction == 1 else flow[i]
            if capacity > 0 and (reverse or direction == 1) and v not in parent:
                parent[v] = (u, i, direction, capacity)
                queue.append(v)
    return parent


def augment(plan, deadline, reverse):
    flow = plan.copy()
    while monotonic() < deadline:
        parent = search(flow, reverse)
        if sink not in parent:
            break
        path = []
        u = sink
        while u != source:
            u, i, direction, capacity = parent[u]
            path.append((i, direction, capacity))
        amount = min(cap for _, _, cap in path)
        for i, direction, _ in path:
            flow[i] += direction * amount
    return flow


def forward(plan, deadline):
    return augment(plan, deadline, False)


def repair(plan, deadline):
    return augment(plan, deadline, True)


def score(flow):
    return sum(x * ((v == source) - (u == source)) for (u, v, _), x in zip(arcs, flow))


def solve(stream, seconds=30.0):
    global arcs, adj, source, sink
    arcs, adj, labels = [], {}, {}
    for row in map(str.split, stream):
        if not row or row[0] == "c":
            continue
        if row[0] == "p":
            _, kind, n, m = row
        elif row[0] == "n":
            labels[row[2]] = int(row[1])
        elif row[0] == "a":
            u, v, cap = map(int, row[1:])
            i = len(arcs)
            arcs.append((u, v, cap))
            adj.setdefault(u, []).append((v, i, 1))
            adj.setdefault(v, []).append((u, i, -1))
    source, sink = labels["s"], labels["t"]
    if (
        kind != "max"
        or len(arcs) != int(m)
        or source == sink
        or any(c < 0 or min(u, v) < 1 or max(u, v) > int(n) for u, v, c in arcs)
    ):
        raise ValueError("invalid maximum flow instance")
    plan = run_pipeline(
        [forward, repair], score, initial=[0] * len(arcs), seconds=seconds
    )
    reachable = search(plan, True)
    cut = sorted(reachable) if sink not in reachable else None
    return {"solution": plan, "source_side_min_cut": cut, "pipeline_score": score(plan)}


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
