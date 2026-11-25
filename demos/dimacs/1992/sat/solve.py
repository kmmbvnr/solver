"""Search for a satisfying assignment in DIMACS CNF."""

import argparse
import json
from pathlib import Path
from random import Random
from time import monotonic

from shiftopt import run_pipeline

clauses = []
variables = 0


def read_cnf(stream):
    rows = (
        line.split() for line in stream if line.strip() and not line.startswith("c")
    )
    p, kind, n, m = next(rows)
    if (p, kind) != ("p", "cnf"):
        raise ValueError("expected a DIMACS CNF header")
    parts, clause = [], set()
    for row in rows:
        for token in row:
            literal = int(token)
            if abs(literal) > int(n):
                raise ValueError("literal exceeds the declared variable count")
            if literal:
                clause.add(literal)
            else:
                parts.append(tuple(sorted(clause)))
                clause = set()
    if clause or len(parts) != int(m):
        raise ValueError("invalid clause count or terminator")
    return int(n), parts


def satisfied(clause, assignment):
    return any(assignment[abs(lit) - 1] == (lit > 0) for lit in clause)


def score(plan):
    return sum(not satisfied(clause, plan) for clause in clauses)


def majority(plan, deadline):
    counts = [0] * variables
    for clause in clauses:
        for lit in clause:
            counts[abs(lit) - 1] += 1 if lit > 0 else -1
    return [count >= 0 for count in counts]


def walk(plan, deadline):
    rng = Random(7)
    current = plan.copy()
    best = current.copy()
    best_score = score(best)
    for _ in range(max(100, 8 * variables)):
        if best_score == 0 or monotonic() >= deadline:
            break
        failed = [clause for clause in clauses if not satisfied(clause, current)]
        if not failed or any(not clause for clause in failed):
            break
        lit = rng.choice(rng.choice(failed))
        current[abs(lit) - 1] = not current[abs(lit) - 1]
        value = score(current)
        if value < best_score:
            best, best_score = current.copy(), value
    return best


def solve(stream, seconds=30.0):
    global variables, clauses
    variables, clauses = read_cnf(stream)
    plan = run_pipeline(
        [majority, walk], score, initial=[False] * variables, seconds=seconds
    )
    remaining = score(plan)
    return {
        "pipeline_score": remaining,
        "status": "SAT" if remaining == 0 else "UNKNOWN",
        "solution": [i if value else -i for i, value in enumerate(plan, 1)],
    }


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
