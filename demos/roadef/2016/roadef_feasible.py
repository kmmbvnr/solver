# /// script
# requires-python = ">=3.12,<3.13"
# dependencies = ["ortools==9.15.6755", "numba==0.68.1", "numpy==2.5.5", "highspy==1.16.0", "scipy==1.18.1"]
# ///
"""Build a first ROADEF schedule using calendar-aware parcels and a Boolean assignment model."""

import argparse
import itertools
import json
import time
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path

import numpy as np
from ortools.sat.python import cp_model

from roadef_v2 import build_oracles, export, read, subsets

JOB_FIELDS = ("owner", "minimum", "need", "earliest", "room", "setup", "night")
SHIFT_FIELDS = ("maxdrive", "rest_length", "rest_cost", "time_cost", "km_cost")


def calendar(x, tree, step):
    drivers = list(tree.find("drivers"))
    source_slot = {int(d): i for i, (_, _, d, _) in enumerate(x["slots"])}
    short, long = [], []
    for d, driver in enumerate(drivers):
        if d not in source_slot:
            continue
        k = int(x["slots"][source_slot[d], 3])
        rest = int(driver.findtext("minInterSHIFTDURATION"))
        for window in driver.find("timewindows"):
            left, right = int(window.findtext("start")), int(window.findtext("end"))
            if right - left <= 1440:
                short.append([left, right, d, k])
            else:
                for at in range(left, right, step):
                    for days in (1, 2):
                        end = min(right, at + days * 1440 - rest)
                        if end - at >= 90:
                            long.append((at, end, d, k))
    # Shared trailers change hands at the next short shift opening.
    for k in {row[3] for row in short}:
        ordered = sorted((row for row in short if row[3] == k), key=lambda row: row[0])
        for a, b in itertools.pairwise(ordered):
            if b[0] > a[0]:
                a[1] = min(a[1], b[0])
    slots = sorted(set(map(tuple, short)).union(long))
    indices = [source_slot[d] for _, _, d, _ in slots]
    for key in SHIFT_FIELDS:
        x[key] = x[key][indices]
    x["slots"] = np.array(slots, dtype=int)
    x["windows"] = x["slots"][:, :2]


def singles(x, delays, companions=False):
    jobs = np.flatnonzero(x["need"] > 1e-6)
    rows = jobs[:, None]
    _, perms = subsets([], 1)
    scorer, _ = build_oracles(x, rows, perms, delays)
    costs, _ = scorer(0.0)
    allowed = np.zeros((len(x["slots"]), x["n"]), dtype=bool)
    allowed[:, jobs] = np.isfinite(costs)
    if companions:
        # A distant ordinary customer can share a layover with a customer who
        # requires one even when its solo round trip exceeds the driving limit.
        unreachable = jobs[~allowed[:, jobs].any(axis=0)]
        overnight = jobs[x["night"][jobs]]
        for j in unreachable:
            partners = overnight[x["owner"][overnight] != x["owner"][j]]
            if len(partners):
                rows = np.column_stack((np.full(len(partners), j), partners))
                _, pair_perms = subsets([], 2)
                score, _ = build_oracles(x, rows, pair_perms, delays)
                pair_costs, _ = score(0.0)
                allowed[:, j] = np.isfinite(pair_costs).any(axis=1)
    return allowed


def variable_parcels(x, customer, delays, fleet_aware=False):
    """Find a path between reachable service hours, replenishing to a target stock."""
    point = int(customer.findtext("index"))
    setup = int(customer.findtext("setupTime"))
    cap = float(customer.findtext("Capacity"))
    safety = float(customer.findtext("SafetyLevel"))
    opening = float(customer.findtext("InitialTankQuantity"))
    min_op = float(customer.findtext("MinOperationQuantity"))
    demand = np.array([float(v.text) for v in customer.find("Forecast")])
    after = demand.cumsum()
    before = np.r_[0.0, after[:-1]]
    unit = x["unit"]
    minute = np.arange(len(demand) * unit, dtype=np.int32)
    hour = minute // unit
    service = np.zeros(len(minute), bool)
    for w in customer.find("timewindows"):
        lo, hi = int(w.findtext("start")), int(w.findtext("end")) - setup
        service[max(0, lo) : max(0, hi + 1)] = True
    job = np.flatnonzero(x["owner"] == point)[0]
    # Reachable delivery capacity by hour for a direct visit, including legal waiting.
    loads = np.zeros(len(demand))
    for w, (start, end, _, k) in enumerate(x["slots"]):
        if not x["compatible"][k, job]:
            continue
        for src in np.flatnonzero(x["source_ok"][:, k]):
            travel = x["travel"]
            outward = travel[0, src + 1] + travel[src + 1, point]
            if outward + travel[point, 0] > x["maxdrive"][w]:
                continue
            last = min(len(minute) - 1, end - setup - travel[point, 0])
            for at in start + delays + outward + x["fills"][src]:
                hi = min(last, at + x["rest_length"][w] - 1)
                if hi >= at:
                    available = np.unique(hour[at : hi + 1][service[at : hi + 1]])
                    loads[available] = np.maximum(loads[available], x["truck_caps"][k])
    hours = np.flatnonzero(loads > 0)
    if fleet_aware:
        fleet = np.unique(x["slots"][:, 3])
        eligible = fleet[x["compatible"][fleet, job]]
        cap_options = np.sort(x["truck_caps"][eligible])
        limits = list(
            dict.fromkeys([cap_options[-min(4, len(eligible))], cap_options[-1]])
        )
    else:
        limits = [np.inf]
    for limit, margin in itertools.product(limits, (0.14, 0.08, 0.025, 0.0)):
        payloads = np.minimum(loads, limit)
        target = cap - margin * (cap - safety)
        reserve = safety + margin * (cap - safety)
        # After service the inventory before consumption equals target, so a
        # path needs only its last delivery hour as state. An edge is one load.
        visits = np.full(len(hours), len(hours) + 1, int)
        prev = np.full(len(hours), -1, int)
        for j, h in enumerate(hours):
            q = target - opening + before[h]
            if opening - before[h] >= safety and min_op <= q <= payloads[h]:
                visits[j] = 1
            increments = before[h] - before[hours[:j]]
            ok = (
                (increments >= min_op)
                & (increments <= payloads[h])
                & (increments <= target - reserve)
                & (visits[:j] < len(hours) + 1)
            )
            if ok.any():
                candidates = np.flatnonzero(ok)
                i = candidates[np.argmin(visits[candidates])]
                if visits[i] + 1 < visits[j]:
                    visits[j], prev[j] = visits[i] + 1, i
        ends = np.flatnonzero(
            (target + before[hours] - after[-1] >= safety) & (visits <= len(hours))
        )
        if not len(ends):
            continue
        i = ends[np.argmin(visits[ends])]
        path = []
        while i >= 0:
            path.append(hours[i])
            i = prev[i]
        path.reverse()
        quantities = np.diff(np.r_[opening - target, before[path]])
        quantities[-1] = max(
            min_op, after[-1] + safety - opening - sum(quantities[:-1])
        )
        fields = {k: [] for k in JOB_FIELDS}
        prior = 0.0
        for q in quantities:
            room = cap - opening + before - prior
            short = np.flatnonzero(opening + prior - after < safety - 1e-8)
            deadline = short[0] if len(short) else len(after) - 1
            valid = service & (hour <= deadline) & (room[hour] + 1e-7 >= q)
            earliest = np.minimum.accumulate(
                np.where(valid, minute, len(minute) + 1)[::-1]
            )[::-1]
            for k, v in zip(
                JOB_FIELDS,
                (
                    point,
                    q,
                    q,
                    earliest.astype(np.int32),
                    np.minimum(q, room),
                    setup,
                    False,
                ),
            ):
                fields[k].append(v)
            prior += q
        part = {**x, **{k: np.asarray(v) for k, v in fields.items()}, "n": len(path)}
        part["compatible"] = np.repeat(
            x["compatible"][:, job : job + 1], len(path), axis=1
        )
        allowed = singles(part, delays)
        if allowed.any(axis=0).all():
            yield part, allowed


def select_parcels(
    instance, tree, delays, step, fraction, companions, fleet_aware=False
):
    def rank_options(x, columns):
        days = [len(np.unique(x["slots"][a, 0] // 1440)) for a in columns.T]
        rank = (
            min(days) > 0,
            min(min(days), 4) / len(days) ** 0.25,
            -len(days),
            sum(np.log1p(days)),
        )
        if fleet_aware:
            trucks = min(len(np.unique(x["slots"][a, 3])) for a in columns.T)
            rank = (rank[0], min(trucks, 4), *rank[1:])
        return rank

    best = {}
    for f in dict.fromkeys([fraction, 0.95, 0.75, 0.65, 0.55, 0.45, 0.85, 0.35]):
        x = read(instance, f, 2880, True, True, 0, True)
        calendar(x, tree, step)
        allowed = singles(x, delays, companions)
        for p in np.unique(x["owner"]):
            rows = np.flatnonzero((x["owner"] == p) & (x["need"] > 1e-6))
            if not len(rows):
                continue
            # Count distinct service days; several departure guesses can represent one shift.
            rank = rank_options(x, allowed[:, rows])
            if p not in best or rank > best[p][0]:
                best[p] = (
                    rank,
                    {k: x[k][rows].copy() for k in JOB_FIELDS},
                    x["compatible"][:, rows].copy(),
                    allowed[:, rows].copy(),
                )
    for customer in tree.find("customers"):
        p = int(customer.findtext("index"))
        if (
            p not in best
            or best[p][0][0]
            or int(customer.findtext("callIn"))
            or int(customer.findtext("LayoverCustomer"))
        ):
            continue
        for part, allowed in variable_parcels(x, customer, delays, fleet_aware):
            rank = rank_options(part, allowed)
            if rank > best[p][0]:
                best[p] = (
                    rank,
                    {k: part[k] for k in JOB_FIELDS},
                    part["compatible"],
                    allowed,
                )
        print(
            json.dumps(
                {
                    "variable_parcels": p,
                    "lots": best[p][1]["minimum"].tolist(),
                    "reachable": bool(best[p][0][0]),
                }
            ),
            flush=True,
        )
    selected = [best[p] for p in sorted(best)]
    for k in JOB_FIELDS:
        x[k] = np.concatenate([s[1][k] for s in selected])
    x["compatible"] = np.hstack([s[2] for s in selected])
    x["n"] = len(x["owner"])
    return x, singles(x, delays, True) if companions else np.hstack(
        [s[3] for s in selected]
    )


def route_checker(x, delays, max_stops):
    permutations = {n: subsets([], n)[1] for n in range(1, max_stops + 1)}

    def options(w, rows):
        n = rows.shape[1]
        part = {**x, "slots": x["slots"][w : w + 1]}
        for k in SHIFT_FIELDS:
            part[k] = x[k][w : w + 1]
        score, restore = build_oracles(part, rows, permutations[n], delays)
        costs, codes = score(0.0)
        return np.isfinite(costs[0]), codes[0], restore

    return options


def solve(
    instance,
    output,
    seconds,
    step,
    fraction,
    seed,
    workers,
    max_stops,
    companions=False,
):
    start = time.monotonic()

    def log(**data):
        print(
            json.dumps(dict(t=round(time.monotonic() - start, 2), **data)), flush=True
        )

    tree = ET.parse(instance).getroot()
    delays = np.arange(0, 721, 90, dtype=int)
    x, allowed = select_parcels(instance, tree, delays, step, fraction, companions)
    check = route_checker(x, delays, max_stops)
    jobs = x["n"]
    if not allowed.any(axis=0).all():
        raise ValueError(
            f"Unreachable points {x['owner'][~allowed.any(axis=0)].tolist()}"
        )
    model = cp_model.CpModel()
    choices = defaultdict(list)
    assignments = []
    drivers = defaultdict(list)
    trailers = defaultdict(list)
    rests = [int(d.findtext("minInterSHIFTDURATION")) for d in tree.find("drivers")]
    solo = singles(x, delays) if companions else allowed
    paircuts = 0
    for w, (at, end, d, k) in enumerate(x["slots"]):
        ids = np.flatnonzero(allowed[w])
        row = {}
        assignments.append(row)
        if not len(ids):
            continue
        active = model.new_bool_var("")
        for j in ids:
            var = model.new_bool_var("")
            row[int(j)] = var
            choices[int(j)].append(var)
        for j in ids[~solo[w, ids]]:
            model.add_bool_or(
                [
                    row[int(j)].Not(),
                    *[row[int(v)] for v in ids if x["night"][v] and v != j],
                ]
            )
        count = sum(row.values())
        model.add(count >= active)
        model.add(count <= max_stops * active)
        model.add(
            sum(round(x["minimum"][j] * 1000) * v for j, v in row.items())
            <= int(x["truck_caps"][k] * 1000) + max_stops
        )
        drivers[d].append(
            model.new_optional_fixed_size_interval_var(
                int(at), int(end - at + rests[d]), active, ""
            )
        )
        trailers[k].append(
            model.new_optional_fixed_size_interval_var(
                int(at), int(end - at), active, ""
            )
        )
        # Discard incompatible pairs before searching. Higher-order combinations are checked on demand.
        pairs = np.array(list(itertools.combinations(ids, 2)), dtype=int).reshape(-1, 2)
        if len(pairs):
            fit = x["minimum"][pairs].sum(axis=1) <= x["truck_caps"][k] + 1e-7
            distinct = x["owner"][pairs[:, 0]] != x["owner"][pairs[:, 1]]
            valid = np.zeros(len(pairs), bool)
            mask = fit & distinct
            if mask.any():
                valid[mask] = check(w, pairs[mask])[0]
            for a, b in pairs[~valid]:
                model.add_bool_or([row[int(a)].Not(), row[int(b)].Not()])
            paircuts += int((~valid).sum())
    for opts in choices.values():
        model.add_exactly_one(opts)
    for intervals in (*drivers.values(), *trailers.values()):
        model.add_no_overlap(intervals)
    log(
        jobs=jobs,
        slots=len(x["slots"]),
        assignment_options=int(allowed.sum()),
        paircuts=paircuts,
    )
    solver = cp_model.CpSolver()
    solver.parameters.num_search_workers = workers
    solver.parameters.random_seed = seed
    seen_cuts = set()
    for iteration in itertools.count():
        left = seconds - (time.monotonic() - start)
        if left < 1:
            break
        solver.parameters.max_time_in_seconds = left
        status = solver.solve(model)
        log(iteration=iteration, status=solver.status_name(status))
        if status not in (cp_model.FEASIBLE, cp_model.OPTIMAL):
            break
        good = []
        bad = 0
        for w, row in enumerate(assignments):
            bundle = tuple(j for j, v in row.items() if solver.value(v))
            if not bundle:
                continue
            vals = np.array([bundle], int)
            ok, codes, restore = check(w, vals)
            if ok[0]:
                tour = restore(0, vals[0], codes[0])
                good.append((w, tour))
            else:
                # Cut the incompatible assignment in this window; feasible shorter subsets survive.
                for size in range(3, len(bundle) + 1):
                    candidates = [
                        t
                        for t in itertools.combinations(bundle, size)
                        if (w, t) not in seen_cuts
                    ]
                    if not candidates:
                        continue
                    oks, _, _ = check(w, np.asarray(candidates, int))
                    for group, feasible in zip(candidates, oks):
                        if not feasible:
                            seen_cuts.add((w, group))
                            model.add_bool_or([row[j].Not() for j in group])
                bad += 1
        log(valid_shifts=len(good), incompatible_shifts=bad, cuts=len(seen_cuts))
        if not bad:
            export(output, x, good)
            return True
        model.clear_hints()
        for w, tour in good:
            for j in tour.order:
                model.add_hint(assignments[w][j], 1)
    return False


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("instance", type=Path)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--seconds", type=int, default=900)
    p.add_argument("--step", type=int, default=720)
    p.add_argument("--fraction", type=float, default=0.8)
    p.add_argument("--seed", type=int, default=7)
    p.add_argument("--workers", type=int, default=1)
    p.add_argument("--stops", type=int, choices=(3, 4), default=4)
    p.add_argument(
        "--companions",
        action="store_true",
        help="offer a layover partner for visits unreachable alone",
    )
    a = p.parse_args()
    if a.seconds <= 0 or a.step <= 0 or a.workers <= 0 or not 0 < a.fraction <= 1:
        p.error(
            "positive budget, calendar step, workers and a fraction in (0,1] required"
        )
    raise SystemExit(
        0
        if solve(
            a.instance,
            a.output,
            a.seconds,
            a.step,
            a.fraction,
            a.seed,
            a.workers,
            a.stops,
            a.companions,
        )
        else 2
    )
