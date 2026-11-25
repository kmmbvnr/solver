"""Construct and improve an exam, event or curriculum timetable."""

import argparse
from functools import partial
from importlib import import_module
from itertools import count
from operator import itemgetter
from pathlib import Path

from demos.itc.events import penalty_event, read_events, write_events
from demos.itc.timetable import TimetableMoves, construct, exchange_labels
from shiftopt import ResumableAnnealing, great_deluge, hill_climbing, run_pipeline, simulated_annealing, stagnation_policy

curriculum = import_module("demos.itc.2007.curriculum")
exams = import_module("demos.itc.2007.exams")


room_repair = import_module("demos.itc.2007.room_repair").room_repair


class SearchBurst:
    """Start each bounded search invocation with its next reproducible seed."""

    def __init__(self, factory, seed):
        self.factory = factory
        self.seeds = count(seed)

    def __call__(self, incumbent, deadline):
        return self.factory(seed=next(self.seeds))(incumbent, deadline)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("track", choices=("exam", "tim", "ctt"))
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--seconds", type=int, default=60)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument(
        "--search", choices=("anneal", "hill", "greedy", "deluge"), default="anneal"
    )
    parser.add_argument("--attempts", type=int, default=50000)
    parser.add_argument(
        "--compactness",
        action="store_true",
        help="reserve 10% of attempts for a compactness polishing step",
    )
    parser.add_argument("--policy", choices=("fixed", "repeat", "stagnation"), default="fixed")
    parser.add_argument("--patience", type=int, default=1, help="unsuccessful bursts before switching")
    parser.add_argument("--room-repair", action="store_true", help="include a room relaxation step (tim)")
    parser.add_argument("--resume", action="store_true", help="preserve annealing state across bursts")
    parser.add_argument("--cycle-attempts", type=int, default=50000)
    parser.add_argument("--penalty-events", action="store_true", help="bias tim moves toward penalized student days")
    parser.add_argument("--conflict-memory", action="store_true", help="penalize repeated evictions during construction")
    args = parser.parse_args()
    if args.penalty_events and args.track != "tim":
        parser.error("--penalty-events requires tim")
    if args.resume and (args.search != "anneal" or args.policy == "fixed" or args.cycle_attempts < 1):
        parser.error("--resume requires annealing, a repeating policy and a positive cycle length")
    if args.room_repair and (args.track != "tim" or args.policy == "repeat"):
        parser.error("--room-repair requires tim and the fixed or stagnation policy")
    if args.policy != "fixed" and (args.compactness or args.attempts < 1):
        parser.error("repeated search requires positive attempts and no fixed compactness finish")
    if args.patience < 1:
        parser.error("--patience must be positive")
    if args.compactness and args.track != "ctt":
        parser.error("--compactness requires the ctt track")
    if args.track == "exam":
        problem, write = exams.read_exam(args.input), exams.write_exam
    elif args.track == "tim":
        problem, write = read_events(args.input, True), write_events
    else:
        problem, write = curriculum.read_curriculum(args.input)
    score = itemgetter(0)
    methods = {
        "anneal": partial(simulated_annealing, temperature=8),
        "hill": hill_climbing,
        "greedy": partial(hill_climbing, allow_equal=False),
        "deluge": partial(great_deluge, margin=8, target=0),
    }
    steps = [partial(construct, problem, args.seed, args.seconds * 0.8,
                     conflict_weight=int(args.conflict_memory))]
    if args.track == "ctt":
        steps.append(partial(exchange_labels, problem, 1))
    polish = args.attempts // 10 if args.compactness else 0
    prefix = tuple(steps)
    moves = TimetableMoves(problem, select_event=penalty_event if args.penalty_events else None)
    factory = partial(methods[args.search], moves, score, attempts=args.attempts - polish)
    operators = [SearchBurst(factory, args.seed)]
    if args.resume:
        operators = [ResumableAnnealing(moves, score, attempts=args.attempts,
                                        cycle_attempts=args.cycle_attempts, temperature=8, seed=args.seed)]
    if args.policy == "stagnation":
        alternate = methods["anneal" if args.search == "hill" else "hill"]
        factory = partial(alternate, moves, score, attempts=args.attempts)
        operators.append(SearchBurst(factory, args.seed))
    if args.room_repair:
        operators.append(SearchBurst(partial(room_repair, problem, attempts=args.attempts), args.seed))
    if polish:
        operators.append(hill_climbing(TimetableMoves(problem, ("compact",)), score,
                                       attempts=polish, seed=args.seed))
    steps.extend(operators)
    policy = None
    if args.policy != "fixed":
        policy = stagnation_policy(operators, prefix=prefix, patience=args.patience)
    plan = run_pipeline(steps, score, seconds=args.seconds, policy=policy,
                        max_steps=100000 if policy else None)
    if plan is None:
        parser.exit(1, "No complete timetable found within the budget.\n")
    write(args.output, plan[1])
    if args.track == "tim":
        print(0, plan[0])
    else:
        print(plan[0])


if __name__ == "__main__":
    main()
