"""Find a large clique using degree ordering and random destroy-and-repair."""

import argparse
import json
from pathlib import Path
from time import monotonic

from shiftopt import neighborhood_search, run_pipeline

graph = []


def read_graph(stream):
    rows = (
        line.split() for line in stream if line.strip() and not line.startswith("c")
    )
    p, kind, n, m = next(rows)
    if p != "p" or kind not in ("edge", "col"):
        raise ValueError("expected a DIMACS edge list")
    adj = [set() for _ in range(int(n))]
    count = 0
    for record, a, b in rows:
        u, v = int(a) - 1, int(b) - 1
        if record != "e" or not (0 <= u < len(adj) and 0 <= v < len(adj) and u != v):
            raise ValueError("invalid edge")
        adj[u].add(v)
        adj[v].add(u)
        count += 1
    if count != int(m):
        raise ValueError("edge count mismatch")
    return adj


def degree(v):
    return len(graph[v])


def greedy(plan, deadline):
    clique = []
    for v in sorted(range(len(graph)), key=degree, reverse=True):
        if monotonic() >= deadline:
            break
        if all(v in graph[u] for u in clique):
            clique.append(v)
    return clique


def release(plan, rng):
    return rng.sample(plan, len(plan) // 2)


def regrow(kept, rng, deadline):
    clique = kept.copy()
    candidates = set(range(len(graph)))
    for u in clique:
        candidates.intersection_update(graph[u])
    while candidates and monotonic() < deadline:
        u = rng.choice(sorted(candidates))
        clique.append(u)
        candidates.intersection_update(graph[u])
    return clique


def score(plan):
    return -len(plan)


def solve(stream, seconds=30.0):
    global graph
    graph = read_graph(stream)
    improve = neighborhood_search(release, regrow, score, attempts=128, seed=7)
    plan = run_pipeline([greedy, improve], score, initial=[], seconds=seconds)
    return {"pipeline_score": score(plan), "solution": [v + 1 for v in plan]}


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
