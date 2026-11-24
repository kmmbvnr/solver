# /// script
# requires-python = ">=3.12,<3.13"
# dependencies = ["ortools==9.15.6755", "numba==0.68.1", "numpy==2.5.5", "highspy==1.16.0", "scipy==1.18.1"]
# ///
"""Insert visits into actual shifts and repair conflicts by ejecting other visits."""

import argparse
import functools
import json
import time
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np

from roadef_feasible import route_checker, select_parcels
from roadef_v2 import export


def search(instance, output, seconds, seed, rotate=False, step=720, fleet_aware=False):
    start = time.monotonic()
    rng = np.random.default_rng(seed)
    root = ET.parse(instance).getroot()
    delays = np.arange(0, 721, 90)
    x, allowed = select_parcels(instance, root, delays, step, 0.8, True, fleet_aware)
    check = route_checker(x, delays, 4)
    rests = [int(d.findtext("minInterSHIFTDURATION")) for d in root.find("drivers")]
    slots = x["slots"]
    owner = x["owner"]
    n = len(owner)
    windows = [np.flatnonzero(a) for a in allowed.T]
    if any(not len(a) for a in windows):
        raise ValueError("A visit has no candidate shift")
    conflicts = [
        np.flatnonzero(
            ((slots[:, 2] == d) | (slots[:, 3] == k))
            & (slots[:, 0] < end + rests[d])
            & (slots[:, 1] + np.asarray(rests)[slots[:, 2]] > at)
        )
        for at, end, d, k in slots
    ]

    @functools.lru_cache(maxsize=120000)
    def route(w, jobs):
        if len({owner[i] for i in jobs}) != len(jobs):
            return None
        rows = np.asarray([jobs], dtype=int)
        ok, codes, restore = check(w, rows)
        if not ok[0]:
            return None
        tour = restore(0, rows[0], codes[0])
        last = tour.order[-1]
        end = tour.arrival[-1] + x["setup"][last] + x["travel"][owner[last], 0]
        return tour, end

    def displaced(w, tour, end):
        driver = slots[w, 2]
        result = []
        for v in conflicts[w]:
            if w == v or v not in plan:
                continue
            _, other, finish = plan[v]
            gap = rests[driver] if slots[v, 2] == driver else 0
            if tour.start < finish + gap and other.start < end + gap:
                result.append(v)
        return result

    plan = {}
    best = {}
    best_missing = n
    since = 0
    frequency = np.zeros(n)
    pending = set(range(n))
    sizes = np.asarray([len(ws) for ws in windows])
    last_attempt = np.full(n, -n, dtype=int)

    def remaining(plan):
        missing = set(range(n)).difference(
            j for jobs, _, _ in plan.values() for j in jobs
        )
        return [
            (int(owner[j]), round(float(x["minimum"][j]), 1), len(windows[j]))
            for j in sorted(missing)
        ]

    iteration = 0
    while time.monotonic() - start < seconds and pending:
        iteration += 1
        if len(pending) < best_missing:
            best_missing, best, since = len(pending), plan.copy(), 0
            if best_missing <= 10 or best_missing % 25 == 0:
                print(
                    json.dumps(
                        {
                            "t": round(time.monotonic() - start, 2),
                            "missing": best_missing,
                            "iterations": iteration,
                            "residual": remaining(best) if best_missing <= 10 else None,
                        }
                    ),
                    flush=True,
                )
        since += 1
        if since > 200 and best and (not rotate or iteration > n):
            plan = best.copy()
            for w in rng.choice(
                list(plan), size=max(1, len(plan) // 12), replace=False
            ):
                del plan[w]
            pending = set(range(n)).difference(
                j for jobs, _, _ in plan.values() for j in jobs
            )
            frequency *= 0.7
            since = 0
        candidates = np.array(sorted(pending))
        priority = np.log1p(sizes[candidates]) + rng.gumbel(size=len(candidates)) * 0.4
        if rotate:
            # Let every visit compete, even when a few rare visits eject each other.
            priority += 8 * np.exp(
                (last_attempt[candidates] - iteration) / max(8, len(pending))
            )
        else:
            priority -= 0.6 * frequency[candidates]
        j = int(candidates[np.argmin(priority)])
        last_attempt[j] = iteration
        frequency[j] += 0.25
        # A little randomness breaks cycles when two scarce deliveries compete.
        weights = 1.0 + np.clip(frequency, 0.0, 20.0) * 0.35
        options = []
        for w in rng.permutation(windows[j]):
            jobs = plan[w][0] if w in plan else ()
            if len(jobs) >= 4:
                continue
            trial = tuple(sorted((*jobs, j)))
            candidate = route(w, trial)
            if candidate is None:
                continue
            tour, end = candidate
            victims = displaced(w, tour, end)
            cost = sum(sum(weights[i] for i in plan[v][0]) for v in victims)
            previous = plan[w][1].cost if jobs else 0.0
            price = (tour.cost - previous) / max(1.0, tour.cost)
            options.append(
                (
                    cost + 0.20 * price + 0.22 * rng.random(),
                    w,
                    trial,
                    tour,
                    end,
                    victims,
                )
            )
        # Permit replacing a visit in a full or incompatible route.
        if not options or min(o[0] for o in options) >= 0.9:
            for w in rng.permutation(windows[j]):
                if w not in plan:
                    continue
                jobs, _, _ = plan[w]
                for old in jobs:
                    trial = tuple(sorted((*[i for i in jobs if i != old], j)))
                    candidate = route(w, trial)
                    if candidate is None:
                        continue
                    tour, end = candidate
                    victims = displaced(w, tour, end)
                    cost = weights[old] + sum(
                        sum(weights[i] for i in plan[v][0]) for v in victims
                    )
                    options.append(
                        (cost + 0.3 * rng.random(), w, trial, tour, end, victims)
                    )
        if not options:
            # A remote visit may need an overnight partner that is still unscheduled.
            pairs = [i for i in pending if x["night"][i] and i != j]
            for w in rng.permutation(windows[j]):
                if w in plan:
                    continue
                for i in pairs:
                    trial = tuple(sorted((i, j)))
                    candidate = route(w, trial)
                    if candidate is None:
                        continue
                    tour, end = candidate
                    victims = displaced(w, tour, end)
                    cost = sum(sum(weights[l] for l in plan[v][0]) for v in victims)
                    options.append(
                        (cost + rng.random() * 0.2, w, trial, tour, end, victims)
                    )
        if not options:
            frequency[j] = -10.0
            continue
        _, w, trial, tour, end, victims = min(options, key=lambda o: o[0])
        for v in victims:
            pending.update(plan.pop(v)[0])
        if w in plan:
            pending.update(plan[w][0])
        plan[w] = trial, tour, end
        pending.difference_update(trial)
    if not pending:
        export(output, x, [(w, tour) for w, (_, tour, _) in plan.items()])
        best_missing = 0
    print(
        json.dumps(
            {
                "t": round(time.monotonic() - start, 2),
                "jobs": n,
                "missing": best_missing,
                "iterations": iteration,
                "complete": not pending,
                "residual": remaining(best) if pending else [],
            }
        ),
        flush=True,
    )
    return not pending


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("instance", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seconds", type=int, default=600)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument(
        "--rotate",
        action="store_true",
        help="temporarily defer recently attempted visits",
    )
    parser.add_argument(
        "--step",
        type=int,
        default=720,
        help="spacing of candidate shift starts in minutes",
    )
    parser.add_argument(
        "--fleet-aware",
        action="store_true",
        help="favor lot sizes accessible to several trailers",
    )
    args = parser.parse_args()
    if min(args.seconds, args.step) <= 0:
        parser.error("positive search budget and calendar step required")
    raise SystemExit(
        0
        if search(
            args.instance,
            args.output,
            args.seconds,
            args.seed,
            args.rotate,
            args.step,
            args.fleet_aware,
        )
        else 2
    )
