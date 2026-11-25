"""Compare chordal completions from two elimination orders."""

import argparse
import json
import sys
from functools import partial
from pathlib import Path

from shiftopt import run_pipeline
from shiftopt.elimination import eliminate


def propose(plan, deadline, graph, min_fill):
    result = eliminate(graph, deadline, min_fill=min_fill)
    return None if result is None else result[1]


def solve(stream, seconds):
    graph = {}
    for line in stream:
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        u, v = line.split()
        graph.setdefault(u, set()).add(v)
        graph.setdefault(v, set()).add(u)
    plan = run_pipeline(
        [partial(propose, graph=graph, min_fill=m) for m in (False, True)],
        len,
        seconds=seconds,
    )
    if plan is None:
        raise ValueError("no completion within budget")
    return len(plan), [f"{u} {v}" for u, v in plan]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "instance", nargs="?", default=str(Path(__file__).with_name("example.txt"))
    )
    parser.add_argument("--seconds", type=float, default=30)
    parser.add_argument(
        "--json",
        action="store_true",
        help="include the objective in machine-readable output",
    )
    args = parser.parse_args()
    if args.instance == "-":
        value, lines = solve(sys.stdin, args.seconds)
    else:
        with open(args.instance) as stream:
            value, lines = solve(stream, args.seconds)
    if args.json:
        print(json.dumps({"objective": value, "solution": lines}, allow_nan=False))
    else:
        sys.stdout.writelines(str(line) + "\n" for line in lines)
