"""Find a clustering satisfying both DIMACS Mix coverage thresholds."""

import argparse
import json
from collections import Counter
from functools import partial
from pathlib import Path
from time import monotonic

from shiftopt import run_pipeline

graph = []
edges = []


def measures(labels):
    n = len(graph)
    sizes = Counter(labels)
    inside = Counter()
    boundary = Counter()
    for u, v in edges:
        if labels[u] == labels[v]:
            inside[labels[u]] += 1
        else:
            boundary[labels[u]] += 1
            boundary[labels[v]] += 1
    internal = sum(inside.values())
    pairs = n * (n - 1) // 2
    cross_non_edges = (
        pairs - sum(s * (s - 1) // 2 for s in sizes.values()) - (len(edges) - internal)
    )
    if internal * 2 < len(edges) or cross_non_edges * 2 < pairs - len(edges):
        return None
    density = 1.0
    cond = expansion = 0.0
    for label, size in sizes.items():
        cut = boundary[label]
        vol = 2 * inside[label] + cut
        if size > 1:
            density = min(density, 2 * inside[label] / (size * (size - 1)))
        cond += cut / max(1, min(vol, 2 * len(edges) - vol))
        expansion += cut / max(1, min(size, n - size))
    return {
        "performance": (internal + cross_non_edges) / pairs,
        "density": density,
        "conductance": cond / len(sizes),
        "expansion": expansion / len(sizes),
    }


def score(plan):
    m = plan["metrics"]
    return (-m["performance"], -m["density"], m["conductance"], m["expansion"])


def cluster(plan, deadline, reverse):
    labels = list(range(len(graph)))
    for _ in range(12):
        changed = False
        order = range(len(graph) - 1, -1, -1) if reverse else range(len(graph))
        for v in order:
            if monotonic() >= deadline:
                return plan
            counts = Counter(labels[u] for u in graph[v])
            if counts:
                label = max(counts, key=counts.get)
                if counts[label] > counts[labels[v]]:
                    labels[v] = label
                    changed = True
        metrics = measures(labels)
        if metrics:
            trial = {"labels": labels.copy(), "metrics": metrics}
            if plan is None or score(trial) < score(plan):
                plan = trial
        if not changed:
            break
    return plan


def solve(stream, seconds=30.0):
    global graph, edges
    rows = (r for r in stream if not r.lstrip().startswith("%"))
    n, m, *fmt = map(int, next(rows).split())
    graph = [sorted(set(int(x) - 1 for x in row.split())) for row in rows]
    edges = [(v, u) for v, row in enumerate(graph) for u in row if u > v]
    if (fmt and fmt != [0]) or len(graph) != n or len(edges) != m or n < 2:
        raise ValueError("expected unweighted simple METIS graph")
    plan = run_pipeline(
        [partial(cluster, reverse=False), partial(cluster, reverse=True)],
        score,
        seconds=seconds,
    )
    if plan is None:
        raise ValueError("no clustering meeting both coverage thresholds found")
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
