"""Construct and improve an exam, event or curriculum timetable."""

import argparse
from functools import partial
from importlib import import_module
from operator import itemgetter
from pathlib import Path

from demos.itc.events import read_events, write_events
from demos.itc.timetable import TimetableMoves, construct, exchange_labels
from shiftopt import run_pipeline, simulated_annealing

curriculum = import_module("demos.itc.2007.curriculum")
exams = import_module("demos.itc.2007.exams")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("track", choices=("exam", "tim", "ctt"))
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--seconds", type=int, default=60)
    parser.add_argument("--seed", type=int, default=1)
    args = parser.parse_args()
    if args.track == "exam":
        problem, write = exams.read_exam(args.input), exams.write_exam
    elif args.track == "tim":
        problem, write = read_events(args.input, True), write_events
    else:
        problem, write = curriculum.read_curriculum(args.input)
    score = itemgetter(0)
    steps = [
        partial(construct, problem, args.seed, args.seconds * 0.8),
        simulated_annealing(
            TimetableMoves(problem), score, attempts=50000, temperature=8, seed=args.seed
        ),
    ]
    if args.track == "ctt":
        steps.insert(1, partial(exchange_labels, problem, 1))
    plan = run_pipeline(steps, score, seconds=args.seconds)
    if plan is None:
        parser.exit(1, "No complete timetable found within the budget.\n")
    write(args.output, plan[1])
    if args.track == "tim":
        print(0, plan[0])
    else:
        print(plan[0])


if __name__ == "__main__":
    main()
