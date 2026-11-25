"""Compare capacitated angular sweeps and improve the incumbent by relocation."""

import argparse
import json
from math import atan2, hypot
from pathlib import Path
from time import monotonic

from shiftopt import run_pipeline

points = {}
demand = {}
capacity = depot = 0
rounded = True


def read_instance(stream):
    fields, coords, loads, depots = {}, {}, {}, []
    section = None
    for raw in stream:
        line = raw.strip()
        if not line or line == "EOF":
            continue
        if line.endswith("_SECTION"):
            section = line
        elif section == "NODE_COORD_SECTION":
            node, x, y = line.split()
            coords[int(node)] = float(x), float(y)
        elif section == "DEMAND_SECTION":
            node, qty = map(int, line.split())
            loads[node] = qty
        elif section == "DEPOT_SECTION":
            if line != "-1":
                depots.append(int(line))
        else:
            key, _, value = line.partition(":")
            fields[key.strip()] = value.strip()
    q = int(fields["CAPACITY"])
    if (
        fields.get("EDGE_WEIGHT_TYPE") != "EUC_2D"
        or len(depots) != 1
        or len(coords) != int(fields["DIMENSION"])
        or coords.keys() != loads.keys()
        or loads[depots[0]] != 0
        or any(v < 0 or v > q for v in loads.values())
    ):
        raise ValueError("expected a single-depot EUC_2D CVRP instance")
    name = fields.get("NAME", "").lower().replace("-", "").replace("_", "")
    continuous = {"cmt4", "cmt5", "tai385", *(f"golden{i}" for i in range(9, 21))}
    return coords, loads, q, depots[0], name not in continuous


def distance(a, b):
    x, y = points[a]
    u, v = points[b]
    length = hypot(x - u, y - v)
    return int(length + 0.5) if rounded else length


def angle(v):
    x, y = points[v]
    u, w = points[depot]
    return atan2(y - w, x - u)


def score(routes):
    total = 0
    for route in routes:
        stops = [depot, *route, depot]
        total += sum(distance(a, b) for a, b in zip(stops, stops[1:]))
    return total


def sweep(reverse):
    routes, trip, load = [], [], 0
    for v in sorted(points.keys() - {depot}, key=angle, reverse=reverse):
        if load + demand[v] > capacity:
            routes.append(trip)
            trip, load = [], 0
        trip.append(v)
        load += demand[v]
    if trip:
        routes.append(trip)
    return routes


def forward(plan, deadline):
    return sweep(False)


def backward(plan, deadline):
    return sweep(True)


def relocate(plan, deadline):
    routes = [trip.copy() for trip in plan]
    loads = [sum(demand[v] for v in trip) for trip in routes]
    for i, trip in enumerate(routes):
        for v in trip.copy():
            pos = trip.index(v)
            before = trip[pos - 1] if pos else depot
            after = trip[pos + 1] if pos + 1 < len(trip) else depot
            saving = distance(before, v) + distance(v, after) - distance(before, after)
            best = None
            for j, other in enumerate(routes):
                if monotonic() >= deadline:
                    return [r for r in routes if r]
                if i == j or loads[j] + demand[v] > capacity:
                    continue
                stops = [depot, *other, depot]
                for k, (a, b) in enumerate(zip(stops, stops[1:])):
                    extra = distance(a, v) + distance(v, b) - distance(a, b)
                    if extra < saving:
                        best, saving = (j, k), extra
            if best is not None:
                j, k = best
                trip.pop(pos)
                routes[j].insert(k, v)
                loads[i] -= demand[v]
                loads[j] += demand[v]
    return [r for r in routes if r]


def solve(stream, seconds=30.0):
    global points, demand, capacity, depot, rounded
    points, demand, capacity, depot, rounded = read_instance(stream)
    plan = run_pipeline([forward, backward, relocate], score, seconds=seconds)
    if plan is None:
        raise ValueError("no plan within budget")
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
