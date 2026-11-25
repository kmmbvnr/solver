"""Euclidean TSPLIB tour construction and bounded 2-opt refinement."""
import argparse
import json
from pathlib import Path
from math import hypot
from time import monotonic

from scipy.spatial import cKDTree

from shiftopt import run_pipeline


coords = {}


def distance(a, b):
    x, y = coords[a]
    u, v = coords[b]
    return int(hypot(x - u, y - v) + 0.5)


def length(tour):
    return sum(distance(tour[i - 1], v) for i, v in enumerate(tour))


def sweep(plan, deadline):
    return sorted(coords, key=coords.__getitem__)


def nearest_neighbor(plan, deadline):
    nodes = list(coords)
    tree = cKDTree([coords[v] for v in nodes])
    tour = [nodes[0]]
    seen = set(tour)
    while len(tour) < len(nodes):
        if monotonic() >= deadline:
            return None
        k = min(8, len(nodes))
        while True:
            _, indices = tree.query(coords[tour[-1]], k=k)
            choices = (nodes[i] for i in indices if nodes[i] not in seen)
            node = next(choices, None)
            if node is not None:
                break
            k = min(len(nodes), k * 2)
        tour.append(node)
        seen.add(node)
    return tour


def refine(plan, deadline):
    tour = plan.copy()
    for _ in range(3):
        changed = False
        for i in range(len(tour) - 1):
            if monotonic() >= deadline:
                return tour
            for j in range(i + 1, min(len(tour), i + 48)):
                if i == 0 and j == len(tour) - 1:
                    continue
                a, b = tour[i - 1], tour[i]
                c, d = tour[j], tour[(j + 1) % len(tour)]
                if distance(a, c) + distance(b, d) < distance(a, b) + distance(c, d):
                    tour[i:j + 1] = reversed(tour[i:j + 1])
                    changed = True
                    break
        if not changed:
            break
    return tour


def solve(stream, seconds=float("inf")):
    global coords
    header = {}
    for line in stream:
        if line.strip() == "NODE_COORD_SECTION":
            break
        key, sep, value = line.partition(":")
        if sep:
            header[key.strip()] = value.strip()
    if header.get("EDGE_WEIGHT_TYPE") != "EUC_2D":
        raise ValueError("expected TSPLIB EUC_2D coordinates")
    coords = {}
    for line in stream:
        if line.strip() == "EOF":
            break
        if line.strip():
            node, x, y = line.split()
            coords[int(node)] = (float(x), float(y))
    if not coords or len(coords) != int(header["DIMENSION"]):
        raise ValueError("coordinate count mismatch")

    plan = run_pipeline([sweep, nearest_neighbor, refine], length, seconds=seconds)
    if plan is None:
        raise ValueError("no feasible solution returned within the search budget")
    return {"pipeline_score": length(plan), "solution": plan}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("instance", type=Path, nargs="?", default=Path(__file__).with_name("example.txt"))
    parser.add_argument("--seconds", type=float, default=float("inf"), help="cooperative pipeline budget")
    args = parser.parse_args()
    with args.instance.open() as stream:
        print(json.dumps(solve(stream, args.seconds), allow_nan=False))
