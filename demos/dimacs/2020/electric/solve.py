"""Route electric vehicles with nonlinear charging and optional shared chargers."""

import argparse
import json
from math import atan2, dist
from pathlib import Path
from time import monotonic
from xml.etree import ElementTree

import numpy as np

from shiftopt import run_pipeline

points, stations, service, curves = {}, {}, {}, {}
depot = battery = speed = consumption = horizon = 0
chargers = 0


def angle(v):
    x, y = points[v]
    a, b = points[depot]
    return atan2(y - b, x - a)


def read_instance(stream):
    global \
        points, \
        stations, \
        service, \
        curves, \
        depot, \
        battery, \
        speed, \
        consumption, \
        horizon
    doc = ElementTree.parse(stream)
    points, stations, curves = {}, {}, {}
    for node in doc.findall(".//network/nodes/node"):
        i = int(node.get("id"))
        points[i] = float(node.findtext("cx")), float(node.findtext("cy"))
        if node.get("type") == "2":
            stations[i] = node.findtext("custom/cs_type")
    profile = doc.find(".//vehicle_profile")
    depot = int(profile.findtext("departure_node"))
    if int(profile.findtext("arrival_node")) != depot:
        raise ValueError("expected a single depot")
    horizon = float(profile.findtext("max_travel_time"))
    speed = float(profile.findtext("speed_factor"))
    battery = float(profile.findtext("custom/battery_capacity"))
    consumption = float(profile.findtext("custom/consumption_rate"))
    for curve in profile.findall("custom/charging_functions/function"):
        levels = [
            float(p.findtext("battery_level")) for p in curve.findall("breakpoint")
        ]
        times = [
            float(p.findtext("charging_time")) for p in curve.findall("breakpoint")
        ]
        curves[curve.get("cs_type")] = levels, times
    service = {
        int(r.get("node")): float(r.findtext("service_time"))
        for r in doc.findall(".//request")
    }


def available(start, duration, bookings):
    if not chargers:
        return start
    for candidate in sorted({start, *(b for a, b in bookings if b >= start)}):
        events = []
        for a, b in bookings:
            if a < candidate + duration and b > candidate:
                events.extend(
                    [(max(a, candidate), 1), (min(b, candidate + duration), -1)]
                )
        used = peak = 0
        for t, delta in sorted(events):
            used += delta
            peak = max(peak, used)
        if peak < chargers:
            return candidate
    raise RuntimeError("missing free interval")


def schedule(order, reservations):
    # Try insertion of one partial recharge before each destination. Keep enough
    # charge to reach a station or depot after servicing that destination.
    plan = []
    u, clock, level = depot, 0.0, battery
    bookings = {s: rows.copy() for s, rows in reservations.items()}
    for v in [*order, depot]:
        safe = (
            0
            if v == depot
            else min(dist(points[v], points[s]) for s in [depot, *stations])
            * consumption
        )
        direct = dist(points[u], points[v])
        options = []
        if level + 1e-8 >= direct * consumption + safe:
            options.append((clock + direct / speed, level - direct * consumption, None))
        for s, kind in stations.items():
            first, second = dist(points[u], points[s]), dist(points[s], points[v])
            arrived = level - first * consumption
            if arrived < -1e-8 or second * consumption + safe > battery + 1e-8:
                continue
            levels, times = curves[kind]
            target = max(arrived, min(battery, second * consumption + safe))
            duration = float(
                np.interp(target, levels, times)
                - np.interp(max(0.0, arrived), levels, times)
            )
            if duration <= 1e-10:
                continue
            begin = available(clock + first / speed, duration, bookings[s])
            finish = begin + duration
            options.append(
                (
                    finish + second / speed,
                    target - second * consumption,
                    (s, begin, finish, max(0.0, arrived), target),
                )
            )
        if not options:
            return None
        clock, level, visit = min(options, key=arrival)
        if visit:
            s, begin, finish, charge, target = visit
            bookings[s].append((begin, finish))
            plan.append(
                {
                    "station": s,
                    "start": begin,
                    "end": finish,
                    "arrival_charge": charge,
                    "departure_charge": target,
                }
            )
        if v != depot:
            plan.append({"customer": v, "arrival": clock})
            clock += service[v]
        if clock > horizon + 1e-8:
            return None
        u = v
    return {"visits": plan, "duration": clock}, bookings


def arrival(option):
    return option[0]


def build(reverse, deadline):
    bookings = {s: [] for s in stations}
    routes, batch = [], []
    accepted = None
    for v in sorted(service, key=angle, reverse=reverse):
        if monotonic() >= deadline:
            return None
        trial = schedule([*batch, v], bookings)
        if trial is None:
            if accepted is None:
                return None
            route, bookings = accepted
            routes.append(route)
            batch = []
            trial = schedule([v], bookings)
            if trial is None:
                return None
        batch.append(v)
        accepted = trial
    if accepted:
        routes.append(accepted[0])
    return routes


def forward(plan, deadline):
    return build(False, deadline)


def backward(plan, deadline):
    return build(True, deadline)


def score(routes):
    return sum(r["duration"] for r in routes)


def solve(stream, seconds=30.0, station_capacity=0):
    global chargers
    if station_capacity < 0:
        raise ValueError("negative station capacity")
    chargers = station_capacity
    read_instance(stream)
    plan = run_pipeline([forward, backward], score, seconds=seconds)
    if plan is None:
        raise ValueError("no feasible electric routing plan found")
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
    parser.add_argument(
        "--chargers", type=int, default=0, help="chargers per station (0 for unlimited)"
    )
    args = parser.parse_args()
    with args.instance.open() as stream:
        print(json.dumps(solve(stream, args.seconds, args.chargers), allow_nan=False))
