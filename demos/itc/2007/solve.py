"""Construct and improve an exam, event or curriculum timetable."""

import argparse
from dataclasses import replace
from functools import partial
from importlib import import_module
from itertools import count, repeat
from operator import itemgetter
from pathlib import Path
from time import monotonic

from demos.itc.events import penalty_event, read_events, write_events
from demos.itc.timetable import TimetableMoves, construct, exchange_labels
from shiftopt import ResumableAnnealing, great_deluge, hill_climbing, run_pipeline, simulated_annealing, stagnation_policy

curriculum = import_module("demos.itc.2007.curriculum")
exams = import_module("demos.itc.2007.exams")


ThreeEventChains = import_module("demos.itc.2007.chains").ThreeEventChains
room_moves = import_module("demos.itc.2007.room_repair")


class PrecedenceMoves:
    """Price each reversed or simultaneous prerequisite pair once."""

    def __init__(self, problem, proposals, *, allow_violations):
        self.pairs = [(i, j) for i, relations in enumerate(problem.relations)
                      for j, relation in relations if relation == "before"]
        self.proposals = proposals
        self.allow_violations = allow_violations
        self.last = None
        self.last_penalty = 0

    def penalty(self, plan):
        if plan is self.last:
            return self.last_penalty
        positions = plan[1]
        return 8 * sum(positions[i][0] >= positions[j][0] for i, j in self.pairs)

    def __call__(self, plan, rng, deadline):
        candidate = self.proposals(plan, rng, deadline)
        if candidate is None:
            return None
        penalty = self.penalty(candidate)
        self.last, self.last_penalty = candidate, penalty
        if penalty and not self.allow_violations:
            return None
        return candidate


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
        help="reserve 10%% of attempts for a compactness polishing step",
    )
    parser.add_argument("--policy", choices=("fixed", "repeat", "stagnation"), default="fixed")
    parser.add_argument("--patience", type=int, default=1, help="unsuccessful bursts before switching")
    parser.add_argument("--room-repair", action="store_true", help="include a room relaxation step (tim)")
    parser.add_argument("--resume", action="store_true", help="preserve annealing state across bursts")
    parser.add_argument("--cycle-attempts", type=int, default=50000)
    parser.add_argument("--penalty-events", action="store_true", help="bias tim moves toward penalized student days")
    parser.add_argument("--conflict-memory", action=argparse.BooleanOptionalAction,
                        help="penalize repeated evictions during construction (enabled by default for tim)")
    parser.add_argument("--event-moves", choices=("standard", "displace"),
                        help="select event moves (displace by default for post-enrolment annealing)")
    comparison = parser.add_mutually_exclusive_group()
    comparison.add_argument("--precedence", choices=("strict", "relaxed"),
                            help="compare rejecting out-of-order pairs with charging eight points per pair")
    comparison.add_argument("--mixed-rooms", choices=("strict", "relaxed"),
                        help="mix room repair into resumed tim search; relaxed allows missing rooms")
    finish = parser.add_mutually_exclusive_group()
    finish.add_argument("--partial-rooms", action="store_true",
                        help="use the final 10%% of the tim budget to search through unroomed events")
    finish.add_argument("--three-event-finish", action="store_true",
                        help="reserve the final 10%% of the tim budget for three-event chains")
    parser.add_argument("--construction-seconds", type=int, help="cap time spent on the initial timetable")
    args = parser.parse_args()
    if args.precedence and (args.track != "tim" or not args.resume):
        parser.error("--precedence requires tim and --resume")
    if args.mixed_rooms and (args.track != "tim" or not args.resume):
        parser.error("--mixed-rooms requires tim and --resume")
    if args.partial_rooms and args.track != "tim":
        parser.error("--partial-rooms requires tim")
    if args.three_event_finish and args.track != "tim":
        parser.error("--three-event-finish requires tim")
    if args.construction_seconds is not None and args.construction_seconds < 0:
        parser.error("--construction-seconds must be nonnegative")
    if args.event_moves == "displace" and args.track != "tim":
        parser.error("--event-moves displace requires tim")
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
    conflict_memory = args.track == "tim" if args.conflict_memory is None else args.conflict_memory
    construction_seconds = args.seconds * 0.8
    if args.construction_seconds is not None:
        construction_seconds = min(construction_seconds, args.construction_seconds)
    steps = [partial(construct, problem, args.seed, construction_seconds,
                     conflict_weight=int(conflict_memory))]
    if args.track == "ctt":
        steps.append(partial(exchange_labels, problem, 1))
    polish = args.attempts // 10 if args.compactness else 0
    prefix = tuple(steps)
    move_types = TimetableMoves.operators
    if args.event_moves == "displace" or (
        args.event_moves is None and args.track == "tim" and args.search == "anneal"
    ):
        move_types = ("displace", "displace", "displace", "chain", "room")
    moves = TimetableMoves(problem, move_types, select_event=penalty_event if args.penalty_events else None)
    factory = partial(methods[args.search], moves, score, attempts=args.attempts - polish)
    operators = [SearchBurst(factory, args.seed)]
    if args.resume:
        move, penalty = moves, None
        if args.precedence:
            search_problem = replace(problem, relations=[()] * len(problem.periods))
            proposals = TimetableMoves(search_problem, move_types, select_event=moves.select_event)
            move = PrecedenceMoves(problem, proposals, allow_violations=args.precedence == "relaxed")
            penalty = move.penalty
        if args.mixed_rooms:
            move = room_moves.MixedRoomMoves(problem, moves, allow_partial=args.mixed_rooms == "relaxed")
            penalty = move.penalty
        operators = [ResumableAnnealing(move, score, attempts=args.attempts, cycle_attempts=args.cycle_attempts,
                                        temperature=8, seed=args.seed, penalty=penalty)]
    if args.policy == "stagnation":
        alternate = methods["anneal" if args.search == "hill" else "hill"]
        factory = partial(alternate, moves, score, attempts=args.attempts)
        operators.append(SearchBurst(factory, args.seed))
    if args.room_repair:
        operators.append(SearchBurst(partial(room_moves.room_repair, problem, attempts=args.attempts), args.seed))
    if polish:
        operators.append(hill_climbing(TimetableMoves(problem, ("compact",)), score,
                                       attempts=polish, seed=args.seed))
    steps.extend(operators)
    policy = None
    if args.policy != "fixed":
        policy = stagnation_policy(operators, prefix=prefix, patience=args.patience)
    finish_seconds = args.seconds * 0.1 if args.three_event_finish or args.partial_rooms else 0
    deadline = monotonic() + args.seconds
    plan = run_pipeline(steps, score, seconds=args.seconds - finish_seconds, policy=policy,
                        max_steps=100000 if policy else None)
    if plan is not None and finish_seconds:
        remaining = min(finish_seconds, max(0, deadline - monotonic()))
        finish_steps = (repeat(room_moves.partial_room_search(problem, args.seed)) if args.partial_rooms
                        else [ThreeEventChains(problem, args.seed)])
        plan = run_pipeline(finish_steps, score, initial=plan, seconds=remaining)
    if plan is None:
        parser.exit(1, "No complete timetable found within the budget.\n")
    write(args.output, plan[1])
    if args.track == "tim":
        print(0, plan[0])
    else:
        print(plan[0])


if __name__ == "__main__":
    main()
