"""Improve a daily assembly sequence by swapping vehicles under the paint batch limit."""

import argparse
import csv
import itertools
from functools import partial
from operator import itemgetter
from pathlib import Path
from random import Random
from time import monotonic

import numpy as np

from shiftopt import run_pipeline


def rows(path):
    with path.open(encoding="latin1") as stream:
        return [
            row
            for row in list(csv.reader(stream, delimiter=";"))[1:]
            if row and row[0].strip()
        ]


def score(order, history, colors, options, ratios, limit, objectives):
    seq = np.concatenate((history, order))
    boundary = len(history)
    paint = colors[seq]
    changes = np.flatnonzero(paint[1:] != paint[:-1]) + 1
    runs = np.r_[0, changes, len(seq)]
    if any(b - a > limit for a, b in itertools.pairwise(runs) if b > boundary):
        return None
    metrics = {"paint": int(np.sum(changes >= boundary)), "high": 0, "low": 0}
    ends = np.arange(boundary + 1, len(seq) + 1)
    for j, (n, p, priority) in enumerate(ratios):
        sums = np.r_[0, np.cumsum(options[seq, j])]
        counts = sums[ends] - sums[np.maximum(0, ends - p)]
        tail = sums[-1] - sums[np.arange(max(0, len(seq) - p + 1), len(seq))]
        metrics[priority] += int(
            np.maximum(counts - n, 0).sum() + np.maximum(tail - n, 0).sum()
        )
    return sum(
        metrics[key] * weight for key, weight in zip(objectives, (10000, 100, 1))
    )


def swaps(plan, deadline, data, seed):
    value, order = plan
    rng = Random(seed)
    for _ in range(500):
        if len(order) < 2 or monotonic() >= deadline:
            break
        a, b = rng.sample(range(len(order)), 2)
        proposed = order.copy()
        proposed[a], proposed[b] = proposed[b], proposed[a]
        cost = score(proposed, *data)
        if cost is not None and cost < value:
            value, order = cost, proposed
    return value, order


def solve(path, seconds):
    cars = rows(path / "vehicles.txt")
    today = cars[-1][0]
    history = np.array([i for i, r in enumerate(cars) if r[0] != today], dtype=int)
    order = np.arange(len(history), len(cars))
    colors = np.array([r[3] for r in cars])
    ratios = [
        (*map(int, r[0].split("/")), "high" if int(r[1]) else "low")
        for r in rows(path / "ratios.txt")
    ]
    options = np.array([list(map(int, r[4 : 4 + len(ratios)])) for r in cars])
    limit = int(rows(path / "paint_batch_limit.txt")[0][0])
    objectives = [
        r[1].split("_")[0] for r in rows(path / "optimization_objectives.txt")
    ]
    data = history, colors, options, ratios, limit, objectives
    value = score(order, *data)
    if value is None:
        raise ValueError("input sequence exceeds the batch limit")
    steps = [partial(swaps, data=data, seed=s) for s in (0, 1)]
    value, order = run_pipeline(
        steps, itemgetter(0), initial=(value, order), seconds=seconds
    )
    return value, "".join(f"{i};{cars[v][2]}\n" for i, v in enumerate(order, 1))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "input", type=Path, nargs="?", default=Path(__file__).with_name("example")
    )
    parser.add_argument("--seconds", type=float, default=5)
    args = parser.parse_args()
    print(solve(args.input, args.seconds)[1], end="")
