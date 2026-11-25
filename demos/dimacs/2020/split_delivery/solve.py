"""Compare angular sweeps with split deliveries, then shorten each route."""

import argparse
import json
from math import atan2, hypot
from pathlib import Path
from time import monotonic

from shiftopt import run_pipeline

points = []
demands = []
capacity = 0


def angle(v):
    x, y = points[v]
    dx, dy = points[0]
    return atan2(y - dy, x - dx)


def distance(u, v):
    x, y = points[u]
    a, b = points[v]
    return int(hypot(x - a, y - b) + 0.5)


def score(routes):
    total = 0
    for route in routes:
        stops = [0, *(v for v, qty in route), 0]
        total += sum(distance(u, v) for u, v in zip(stops, stops[1:]))
    return total


def pack(order):
    routes, route = [], []
    space = capacity
    for v in order:
        due = demands[v - 1]
        while due:
            qty = min(space, due)
            route.append((v, qty))
            due -= qty
            space -= qty
            if space == 0:
                routes.append(route)
                route, space = [], capacity
    if route:
        routes.append(route)
    return routes


def clockwise(plan, deadline):
    return pack(sorted(range(1, len(points)), key=angle))


def counterclockwise(plan, deadline):
    return pack(sorted(range(1, len(points)), key=angle, reverse=True))


def shorten(plan, deadline):
    routes = [route.copy() for route in plan]
    for route in routes:
        for i in range(len(route) - 1):
            for j in range(i + 1, len(route)):
                if monotonic() >= deadline:
                    return routes
                a = route[i - 1][0] if i else 0
                b, c = route[i][0], route[j][0]
                d = route[j + 1][0] if j + 1 < len(route) else 0
                if distance(a, c) + distance(b, d) < distance(a, b) + distance(c, d):
                    route[i : j + 1] = reversed(route[i : j + 1])
    return routes


def solve(stream, seconds=30.0):
    global points, demands, capacity
    n, capacity = map(int, stream.readline().split())
    demands = list(map(int, stream.readline().split()))
    points = [tuple(map(float, line.split())) for line in stream if line.strip()]
    if (
        capacity <= 0
        or len(demands) != n
        or min(demands, default=0) < 0
        or len(points) != n + 1
    ):
        raise ValueError("invalid split-delivery instance")
    plan = run_pipeline([clockwise, counterclockwise, shorten], score, seconds=seconds)
    if plan is None:
        raise ValueError("no plan within the time budget")
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
