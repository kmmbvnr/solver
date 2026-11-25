"""Build an event timetable and improve it by exchanging entire periods."""
import argparse
from functools import partial
from itertools import combinations
from pathlib import Path
from time import monotonic

import numpy as np

from demos.itc.unitime import Plan, score, search
from shiftopt import run_pipeline


def penalty(busy):
    days = busy.reshape(-1, 5, 9)
    triples = days[:, :, :-2] & days[:, :, 1:-1] & days[:, :, 2:]
    return int(days[:, :, -1].sum() + (days.sum(axis=2) == 1).sum() + triples.sum())


def exchange_periods(attendance, incumbent, deadline):
    if incumbent is None:
        return None
    events = np.array([list(map(int, line.split())) for line in incumbent.text.splitlines()])
    busy = np.zeros((attendance.shape[0], 45), dtype=bool)
    for event, (slot, _) in enumerate(events):
        busy[:, slot] |= attendance[:, event]
    best = incumbent.cost[0]
    if penalty(busy) != best:
        raise ValueError("Backend and independent timetable scores differ")
    slots = np.arange(45)
    for first, second in combinations(slots.copy(), 2):
        if monotonic() >= deadline:
            break
        busy[:, [first, second]] = busy[:, [second, first]]
        cost = penalty(busy)
        if cost < best:
            best = cost
            slots[[first, second]] = slots[[second, first]]
        else:
            busy[:, [first, second]] = busy[:, [second, first]]
    events[:, 0] = np.argsort(slots)[events[:, 0]]
    return Plan((best,), "".join(f"{t} {r}\n" for t, r in events))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--seconds", type=int, default=30)
    args = parser.parse_args()
    values = np.fromfile(args.input, dtype=int, sep=" ")
    events, rooms, _, students = values[:4]
    start = 4 + rooms
    attendance = values[start:start + students * events].reshape(students, events).astype(bool)
    steps = [partial(search, "ttcomp02", args.input, 1, max(1, args.seconds // 2)),
             partial(exchange_periods, attendance)]
    plan = run_pipeline(steps, score, seconds=args.seconds)
    if plan is None:
        parser.exit(1, "No complete timetable found within the budget.\n")
    args.output.write_text(plan.text)
    print(plan.cost[0])


if __name__ == "__main__":
    main()
