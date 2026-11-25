"""Optimize replenishment and vehicle assignments, then route each vehicle."""
import argparse
import json
import os
import sys
from pathlib import Path
from functools import partial
from math import hypot
from time import monotonic

from shiftopt import Model, quicksum, run_pipeline


periods = capacity = fleet = 0
depot = []
customers = []
points = []


def distance(i, j):
    x, y = points[i]
    u, v = points[j]
    return int(hypot(x - u, y - v) + 0.5)


def route_cost(route):
    stops = [0, *(i for i, q in route), 0]
    return sum(distance(a, b) for a, b in zip(stops, stops[1:]))


def cost(plan):
    return plan["holding"] + sum(route_cost(route) for day in plan["routes"] for route in day)


def just_in_time(plan, deadline):
    levels = [row[3] for row in [depot, *customers]]
    routes, holding = [], 0.
    for _ in range(periods):
        remaining = [capacity] * fleet
        trips = [[] for _ in remaining]
        orders = []
        for i, row in enumerate(customers, 1):
            qty = max(0, int(row[5] + row[6] - levels[i]))
            if qty + levels[i] > row[4]:
                return None
            if qty:
                orders.append((qty, i))
            levels[i] += qty - row[6]
        for qty, i in sorted(orders, reverse=True):
            k = max(range(fleet), key=remaining.__getitem__)
            if remaining[k] < qty:
                return None
            trips[k].append((i, qty))
            remaining[k] -= qty
        levels[0] += depot[4] - sum(qty for qty, i in orders)
        if levels[0] < 0:
            return None
        holding += depot[5] * levels[0] + sum(row[7] * levels[i] for i, row in enumerate(customers, 1))
        routes.append(trips)
    return {"routes": routes, "holding": holding}


def replenish(plan, deadline):
    model = Model(threads=1)
    stock = [row[3] for row in [depot, *customers]]
    objective = []
    allocations = []
    for t in range(periods):
        load = [[] for _ in range(fleet)]
        day = []
        for i, row in enumerate(customers, 1):
            _, _, _, _, upper, lower, demand, holding = row
            visits = [model.addVar(vtype="B") for _ in load]
            model.addConstr(quicksum(visits) <= 1)
            drops = [model.addVar(ub=capacity, vtype="I") for _ in load]
            for k, (qty, visit) in enumerate(zip(drops, visits)):
                model.addConstr(qty <= capacity * visit)
                load[k].append(qty)
            end = model.addVar(lb=lower, ub=upper - demand)
            model.addConstr(end == stock[i] + quicksum(drops) - demand)
            stock[i] = end
            objective.extend([holding * end, distance(0, i) * quicksum(visits)])
            day.append(drops)
        for truck in load:
            model.addConstr(quicksum(truck) <= capacity)
        end = model.addVar()
        model.addConstr(end == stock[0] + depot[4] - quicksum(q for truck in load for q in truck))
        stock[0] = end
        objective.append(depot[5] * end)
        allocations.append((day, stock.copy()))
    model.setObjective(quicksum(objective))
    solution = model.optimize(time_limit=max(0.001, min(10, deadline - monotonic())))
    if not solution.has_solution:
        return None
    routes, holding_cost = [], 0.
    for day, levels in allocations:
        trips = [[] for _ in range(fleet)]
        for i, drops in enumerate(day, 1):
            for trip, q in zip(trips, drops):
                qty = round(solution.value(q))
                if qty > 1e-6:
                    trip.append((i, qty))
        routes.append(trips)
        holding_cost += sum(rate * solution.value(level) for rate, level in
                            zip([depot[5], *(row[7] for row in customers)], levels))
    return {"routes": routes, "holding": holding_cost}


def nearest_key(node, candidate):
    return distance(node, candidate), candidate


def route_vehicles(plan, deadline):
    if plan is None:
        return None
    routes = []
    for day in plan["routes"]:
        trips = []
        for trip in day:
            left = dict(trip)
            route = []
            node = 0
            while left:
                node = min(left, key=partial(nearest_key, node))
                route.append((node, left.pop(node)))
            trips.append(min([trip, route], key=route_cost))
        routes.append(trips)
    return {"routes": routes, "holding": plan["holding"]}


def solve(stream, seconds=float("inf")):
    global periods, capacity, fleet, depot, customers, points
    nodes, periods, capacity, fleet = map(int, stream.readline().split())
    depot, *customers = [list(map(float, row.split())) for row in stream if row.strip()]
    if len(customers) + 1 != nodes or [row[0] for row in [depot, *customers]] != list(range(nodes)):
        raise ValueError("expected depot 0 followed by consecutive customer IDs")
    points = [(row[1], row[2]) for row in [depot, *customers]]

    plan = run_pipeline([just_in_time, replenish, route_vehicles], cost, seconds=seconds)
    if plan is None:
        raise ValueError("no feasible solution returned within the search budget")
    return {"pipeline_score": cost(plan), "solution": plan}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("instance", type=Path, nargs="?", default=Path(__file__).with_name("example.txt"))
    parser.add_argument("--seconds", type=float, default=float("inf"), help="cooperative pipeline budget")
    args = parser.parse_args()
    # HiGHS may print a banner before its logger is configured.
    with os.fdopen(os.dup(sys.stdout.fileno()), "w") as output, args.instance.open() as stream:
        os.dup2(sys.stderr.fileno(), sys.stdout.fileno())
        print(json.dumps(solve(stream, args.seconds), allow_nan=False), file=output)
