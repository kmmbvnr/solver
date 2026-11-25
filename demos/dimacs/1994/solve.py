"""Sort a signed permutation by reversing intervals and flipping their signs."""
import argparse
import json
from pathlib import Path

from shiftopt import run_pipeline


original = []


def reverse(values, positions, moves, left, right):
    values[left:right + 1] = [-v for v in reversed(values[left:right + 1])]
    for i in range(left, right + 1):
        positions[abs(values[i])] = i
    moves.append([left + 1, right + 1])


def place_in_order(backwards):
    values = original.copy()
    moves = []
    positions = {abs(v): i for i, v in enumerate(values)}

    order = range(len(values))
    for i in reversed(order) if backwards else order:
        j = positions[i + 1]
        if i != j:
            reverse(values, positions, moves, min(i, j), max(i, j))
        if values[i] < 0:
            reverse(values, positions, moves, i, i)
    return moves


def from_left(plan, deadline):
    return place_in_order(False)


def from_right(plan, deadline):
    return place_in_order(True)


def solve(stream, seconds=float("inf")):
    global original
    original = list(map(int, stream.read().split()))
    if sorted(map(abs, original)) != list(range(1, len(original) + 1)):
        raise ValueError("expected a signed permutation of 1..n")

    plan = run_pipeline([from_left, from_right], len, seconds=seconds)
    if plan is None:
        raise ValueError("no feasible solution returned within the search budget")
    return {"pipeline_score": len(plan), "solution": plan}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("instance", type=Path, nargs="?", default=Path(__file__).with_name("example.txt"))
    parser.add_argument("--seconds", type=float, default=float("inf"), help="cooperative pipeline budget")
    args = parser.parse_args()
    with args.instance.open() as stream:
        print(json.dumps(solve(stream, args.seconds), allow_nan=False))
