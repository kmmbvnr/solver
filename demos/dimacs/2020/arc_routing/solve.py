"""Route required nodes, edges and arcs using capacitated bins and earliest-arrival paths."""

import argparse
import json
import re
from bisect import bisect_right
from heapq import heappop, heappush
from pathlib import Path
from random import Random
from time import monotonic

from shiftopt import run_pipeline

adj = {}
tasks = []
depot = fleet = capacity = 0
start = 0.0
horizon = float("inf")
service_factor = 1.0


def link(a, b, length, ends=(), speeds=(1.0,)):
    edge = (a, b, length, tuple(ends), tuple(speeds))
    adj.setdefault(a, []).append(edge)
    return edge


def read_instance(stream):
    global adj, tasks, depot, fleet, capacity, start, horizon, service_factor
    text = stream.read()
    adj, tasks = {}, []
    start, horizon, service_factor = 0.0, float("inf"), 1.0
    headers = {}
    td_edges = {}
    for line in text.splitlines():
        line = line.strip()
        fields = line.split()
        if not fields:
            continue
        if ":" in line:
            name, value = line.split(":", 1)
            headers[name.strip().upper()] = value.strip()
        elif line.startswith("("):
            vals = list(map(int, re.findall(r"\d+", line)))
            a, b, length = vals[:3]
            options = [link(a, b, length), link(b, a, length)]
            if len(vals) == 4 and vals[3]:
                tasks.append((len(tasks) + 1, vals[3], options, length))
        elif fields[0].isdigit() and "[" in line:
            vals = line.replace("[", " ").replace("]", " ").split()
            a, b = map(int, vals[:2])
            length, qty = map(float, vals[2:4])
            k = int(vals[4])
            edge = link(
                a, b, length, map(float, vals[5 : 4 + k]), map(float, vals[4 + k :])
            )
            if qty:
                key = tuple(sorted((a, b)))
                td_edges.setdefault(key, (qty, []))[1].append(edge)
        elif re.fullmatch(r"N\d+", fields[0]):
            v = int(fields[0][1:])
            tasks.append(
                (fields[0], int(fields[1]), [(v, v, 0.0, (), (1.0,))], float(fields[2]))
            )
        elif re.fullmatch(r"(?:Nr)?[AE]\d+", fields[0], re.I):
            tag, a, b, length, *extra = fields
            a, b, length = int(a), int(b), float(length)
            options = [link(a, b, length)]
            if "E" in tag.upper():
                options.append(link(b, a, length))
            if extra and int(extra[0]):
                tasks.append((tag, int(extra[0]), options, float(extra[1])))
    for (a, b), (qty, options) in td_edges.items():
        tasks.append((f"{a}-{b}", qty, options, None))
    if td_edges:
        start, horizon = float(headers["STARTTIME"]), float(headers["ENDTIME"])
        service_factor = float(headers["SERVICE_SPEED_FACTOR"])
    depot = int(
        headers.get("DEPOT", headers.get("DEPOSITO", headers.get("DEPOT NODE", 0)))
    )
    capacity = int(headers.get("CAPACIDAD", headers.get("CAPACITY", 0)))
    fleet = int(
        headers.get("VEHICULOS", headers.get("VEHICLES", headers.get("#VEHICLES", -1)))
    )
    if capacity <= 0 or depot not in adj:
        raise ValueError("invalid capacity or depot")


def arrival(edge, clock, factor=1.0):
    _, _, remaining, ends, speeds = edge
    i = bisect_right(ends, clock)
    while i < len(ends):
        rate = speeds[i] * factor
        length = (ends[i] - clock) * rate
        if length >= remaining:
            break
        remaining -= length
        clock = ends[i]
        i += 1
    return clock + remaining / (speeds[i] * factor)


def earliest(source, clock):
    times = {source: clock}
    queue = [(clock, source)]
    while queue:
        t, u = heappop(queue)
        if t != times[u]:
            continue
        for edge in adj.get(u, []):
            v = edge[1]
            end = arrival(edge, t)
            if end < times.get(v, float("inf")):
                times[v] = end
                heappush(queue, (end, v))
    return times


def route(group, deadline):
    left = set(group)
    now, u = start, depot
    itinerary = []
    while left:
        if monotonic() >= deadline:
            return None
        times = earliest(u, now)
        choices = []
        for i in left:
            name, qty, options, service = tasks[i]
            for edge in options:
                a, b = edge[:2]
                t = times.get(a, float("inf"))
                if t == float("inf"):
                    continue
                end = (
                    t + service
                    if service is not None
                    else arrival(edge, t, service_factor)
                )
                choices.append((end, i, a, b))
        if not choices:
            return None
        now, i, a, u = min(choices)
        left.remove(i)
        itinerary.append((tasks[i][0], a, u))
    end = earliest(u, now).get(depot, float("inf"))
    if end > horizon or end == float("inf"):
        return None
    return {"services": itinerary, "duration": end - start}


def demand(i):
    return tasks[i][1]


def build(reverse, deadline):
    groups, loads = [], []
    ids = list(range(len(tasks)))
    if reverse:
        ids.reverse()
    for i in sorted(ids, key=demand, reverse=True):
        qty = demand(i)
        candidates = [
            (capacity - load - qty, k)
            for k, load in enumerate(loads)
            if qty + load <= capacity
        ]
        if candidates:
            _, k = min(candidates)
        elif qty <= capacity and (fleet <= 0 or len(groups) < fleet):
            k = len(groups)
            groups.append([])
            loads.append(0.0)
        else:
            return None
        groups[k].append(i)
        loads[k] += qty
    routes = []
    for group in groups:
        trip = route(group, deadline)
        if trip is None:
            return None
        routes.append(trip)
    return routes


def forward(plan, deadline):
    return build(False, deadline)


def reverse_ties(plan, deadline):
    return build(True, deadline)


def scan(deadline, rng, pool=None):
    remaining = set(range(len(tasks)))
    routes = []
    while remaining:
        load, u, now = 0, depot, start
        itinerary = []
        while remaining and monotonic() < deadline:
            times = earliest(u, now)
            choices = []
            for i in remaining:
                name, qty, options, service = tasks[i]
                if load + qty > capacity:
                    continue
                for edge in options:
                    a, b = edge[:2]
                    t = times.get(a, float("inf"))
                    if t == float("inf"):
                        continue
                    end = (
                        t + service
                        if service is not None
                        else arrival(edge, t, service_factor)
                    )
                    choices.append((end, i, a, b))
            choices.sort()
            if rng and choices:
                k = rng.randrange(min(3, len(choices)))
                choices[0], choices[k] = choices[k], choices[0]
            for end, i, a, b in choices:
                back = earliest(b, end).get(depot, float("inf"))
                if back <= horizon and back < float("inf"):
                    break
            else:
                break
            remaining.remove(i)
            load += demand(i)
            now, u = end, b
            itinerary.append((tasks[i][0], a, b))
        if not itinerary:
            return None
        routes.append(
            {"services": itinerary, "duration": earliest(u, now)[depot] - start}
        )
    if pool is not None:
        for trip in routes:
            key = frozenset(x[0] for x in trip["services"])
            if key not in pool or trip["duration"] < pool[key]["duration"]:
                pool[key] = trip
    if fleet > 0 and len(routes) > fleet:
        return None
    return routes


def path_scan(plan, deadline):
    return scan(deadline, None)


def restart_scan(plan, deadline):
    rng = Random(7)
    best = plan
    pool = {}
    for _ in range(36):
        if monotonic() >= deadline:
            break
        trial = scan(deadline, rng, pool)
        if trial is not None and (best is None or score(trial) < score(best)):
            best = trial
    if not pool or monotonic() >= deadline:
        return best
    import numpy as np
    from scipy.optimize import Bounds, LinearConstraint, milp
    from scipy.sparse import coo_matrix

    ids = {task[0]: i for i, task in enumerate(tasks)}
    rows, cols = [], []
    trips = list(pool.values())
    for j, names in enumerate(pool):
        rows.extend(ids[name] for name in names)
        cols.extend([j] * len(names))
        rows.append(len(ids))
        cols.append(j)
    matrix = coo_matrix(
        (np.ones(len(rows)), (rows, cols)), shape=(len(ids) + 1, len(trips))
    ).tocsr()
    lower = [1] * len(ids) + [0]
    upper = [1] * len(ids) + [fleet if fleet > 0 else len(trips)]
    result = milp(
        [trip["duration"] for trip in trips],
        integrality=np.ones(len(trips)),
        bounds=Bounds(0, 1),
        constraints=LinearConstraint(matrix, lower, upper),
        options={"time_limit": max(0.001, deadline - monotonic())},
    )
    if result.x is not None:
        chosen = [trip for x, trip in zip(result.x, trips) if x > 0.5]
        if best is None or score(chosen) < score(best):
            return chosen
    return best


def score(plan):
    return sum(trip["duration"] for trip in plan)


def solve(stream, seconds=30.0):
    read_instance(stream)
    plan = run_pipeline(
        [path_scan, forward, reverse_ties, restart_scan], score, seconds=seconds
    )
    if plan is None:
        raise ValueError("no feasible arc routing plan found")
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
