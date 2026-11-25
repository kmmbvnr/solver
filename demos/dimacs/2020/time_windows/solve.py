"""Insert Solomon customers in two orders under capacity, fleet and time constraints."""

import argparse
import json
from math import floor, hypot
from pathlib import Path
from time import monotonic

from shiftopt import run_pipeline

customers = {}
fleet = capacity = 0


def travel(a, b):
    x, y = customers[a][:2]
    u, v = customers[b][:2]
    return floor(10 * hypot(x - u, y - v)) / 10


def evaluate(route):
    previous, load = 0, 0
    distance = 0.0
    clock = customers[0][3] + customers[0][5]
    for v in route:
        _, _, qty, ready, due, service = customers[v]
        leg = travel(previous, v)
        distance += leg
        clock = max(ready, clock + leg)
        load += qty
        if clock > due + 1e-8 or load > capacity:
            return float("inf")
        previous, clock = v, clock + service
    back = travel(previous, 0)
    return distance + back if clock + back <= customers[0][4] + 1e-8 else float("inf")


def score(routes):
    return sum(evaluate(route) for route in routes)


def due_order(v):
    return customers[v][4]


def far_order(v):
    return -travel(0, v)


def insert_customers(key, deadline):
    routes, costs = [], []
    for v in sorted(customers.keys() - {0}, key=key):
        if monotonic() >= deadline:
            return None
        choice = None
        if len(routes) < fleet and evaluate([v]) < float("inf"):
            choice = (evaluate([v]), len(routes), 0)
        for i, route in enumerate(routes):
            for j in range(len(route) + 1):
                cost = evaluate(route[:j] + [v] + route[j:])
                if cost < float("inf"):
                    proposal = cost - costs[i], i, j
                    if choice is None or proposal < choice:
                        choice = proposal
        if choice is None:
            return None
        _, i, j = choice
        if i == len(routes):
            routes.append([])
            costs.append(0.0)
        routes[i].insert(j, v)
        costs[i] = evaluate(routes[i])
    return routes


def earliest_due(plan, deadline):
    return insert_customers(due_order, deadline)


def farthest_first(plan, deadline):
    return insert_customers(far_order, deadline)


def solve(stream, seconds=30.0):
    global customers, fleet, capacity
    customers = {}
    fleet = capacity = 0
    for line in stream:
        row = line.split()
        if row and row[0].isdigit():
            if len(row) == 2:
                fleet, capacity = map(int, row)
            elif len(row) == 7:
                customers[int(row[0])] = tuple(map(float, row[1:]))
    if 0 not in customers or fleet <= 0 or capacity <= 0:
        raise ValueError("expected Solomon vehicle and customer sections")
    plan = run_pipeline([earliest_due, farthest_first], score, seconds=seconds)
    if plan is None:
        raise ValueError("no feasible schedule found")
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
