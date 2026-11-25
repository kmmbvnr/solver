"""Build and improve asymmetric tours in TSPLIB full-matrix format."""

import argparse
import json
from pathlib import Path
from time import monotonic

from shiftopt import run_pipeline

cost = []


def score(tour):
    return sum(cost[tour[i - 1]][v] for i, v in enumerate(tour))


def nearest(plan, deadline):
    tour = [0]
    remaining = set(range(1, len(plan)))
    while remaining and monotonic() < deadline:
        v = min(remaining, key=cost[tour[-1]].__getitem__)
        tour.append(v)
        remaining.remove(v)
    return tour + sorted(remaining)


def relocate(plan, deadline):
    tour = plan.copy()
    for v in plan:
        if monotonic() >= deadline or len(tour) < 3:
            break
        i = tour.index(v)
        a, b = tour[i - 1], tour[(i + 1) % len(tour)]
        saving = cost[a][v] + cost[v][b] - cost[a][b]
        tour.pop(i)
        best, delta = i, saving
        for j, u in enumerate(tour):
            p = tour[j - 1]
            extra = cost[p][v] + cost[v][u] - cost[p][u]
            if extra < delta:
                best, delta = j, extra
        tour.insert(best, v)
    return tour


def solve(stream, seconds=30.0):
    global cost
    header = {}
    for line in stream:
        if line.strip() == "EDGE_WEIGHT_SECTION":
            break
        key, sep, val = line.partition(":")
        if sep:
            header[key.strip()] = val.strip()
    n = int(header["DIMENSION"])
    if header.get("EDGE_WEIGHT_FORMAT") != "FULL_MATRIX":
        raise ValueError("expected TSPLIB FULL_MATRIX")
    weights = [int(x) for line in stream for x in line.split() if x != "EOF"]
    if len(weights) != n * n or n < 1:
        raise ValueError("invalid distance matrix")
    cost = [weights[i * n : (i + 1) * n] for i in range(n)]
    plan = run_pipeline(
        [nearest, relocate], score, initial=list(range(n)), seconds=seconds
    )
    return {"solution": [v + 1 for v in plan], "pipeline_score": score(plan)}


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
