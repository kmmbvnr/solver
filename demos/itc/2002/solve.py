"""Construct a timetable and anneal feasible event moves."""

import argparse
from functools import partial
from operator import itemgetter
from pathlib import Path

from demos.itc.events import read_events, write_events
from demos.itc.timetable import TimetableMoves, construct, exchange_labels
from shiftopt import run_pipeline, simulated_annealing


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--seconds", type=int, default=30)
    parser.add_argument("--seed", type=int, default=1)
    args = parser.parse_args()
    problem = read_events(args.input, False)
    score = itemgetter(0)
    steps = [
        partial(construct, problem, args.seed, args.seconds * 0.8),
        partial(exchange_labels, problem, 0),
        simulated_annealing(
            TimetableMoves(problem), score, attempts=50000, temperature=8, seed=args.seed
        ),
    ]
    plan = run_pipeline(steps, score, seconds=args.seconds)
    if plan is None:
        parser.exit(1, "No complete timetable found within the budget.\n")
    write_events(args.output, plan[1])
    print(plan[0])


if __name__ == "__main__":
    main()
