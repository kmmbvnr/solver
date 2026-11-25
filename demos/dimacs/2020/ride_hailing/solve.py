"""Choose a dispatch action for one observed pyhailing decision epoch."""

import argparse
import json
import sys
from functools import partial
from pathlib import Path
from time import monotonic

import numpy as np
from scipy.optimize import linear_sum_assignment

from shiftopt import run_pipeline


def distance(a, b):
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def score(plan, values):
    return -sum(values[r, v] for r, v in plan)


def greedy(plan, deadline, values):
    used = set()
    pairs = []
    for r, row in enumerate(values):
        if monotonic() >= deadline:
            break
        for v in np.argsort(-row):
            if row[v] <= 0:
                break
            if v not in used:
                pairs.append((r, int(v)))
                used.add(v)
                break
    return pairs


def assign(plan, deadline, values):
    if not values.size:
        return []
    rows, cols = linear_sum_assignment(values, maximize=True)
    return [(int(r), int(v)) for r, v in zip(rows, cols) if values[r, v] > 0]


def dispatch(observation, lots, seconds=1.0):
    vehicles = observation["v_locs"]
    jobs = observation["v_jobs"]
    requests = observation["request_locs"]
    values = np.zeros((len(requests), len(vehicles)))
    for r, (origin, dest) in enumerate(requests):
        for v, loc in enumerate(vehicles):
            if jobs[v][0] in (0, 1, 4) and (
                "pickup_seconds" not in observation
                or observation["pickup_seconds"][r][v] <= 300
            ):
                values[r, v] = max(
                    0.0,
                    10.75
                    + (4.02 - 0.53) * distance(origin, dest)
                    - 0.53 * distance(loc, origin),
                )
    objective = partial(score, values=values)
    plan = run_pipeline(
        [partial(greedy, values=values), partial(assign, values=values)],
        objective,
        initial=[],
        seconds=seconds,
    )
    assignments = [len(vehicles)] * len(requests)
    reposition = [len(lots)] * len(vehicles)
    for v, loc in enumerate(vehicles):
        if jobs[v][0] == 4:
            reposition[v] = int(np.argmin([distance(loc, p) for p in lots]))
    for r, v in plan:
        assignments[r] = v
        if "pickup_seconds" in observation:
            reposition[v] = len(lots)
    action = {
        "req_rejections": [0] * len(requests),
        "req_assgts": assignments,
        "reposition": reposition,
    }
    return {"solution": action, "pipeline_score": float(objective(plan))}


def solve(stream, seconds=30.0):
    epoch = json.load(stream)
    return dispatch(epoch["observation"], epoch["lots"], seconds)


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
        "--epochs",
        action="store_true",
        help="read one JSON observation and lot list per line",
    )
    args = parser.parse_args()
    if args.epochs:
        for line in sys.stdin:
            epoch = json.loads(line)
            result = dispatch(epoch["observation"], epoch["lots"], args.seconds)
            print(json.dumps(result["solution"], allow_nan=False), flush=True)
        sys.exit(0)
    with args.instance.open() as stream:
        print(json.dumps(solve(stream, args.seconds), allow_nan=False))
