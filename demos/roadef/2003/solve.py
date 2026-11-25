"""Sequence historical observation requests with time windows and a conservative setup allowance."""

import argparse
from collections import defaultdict
from functools import partial
from math import atan, hypot
from operator import itemgetter
from pathlib import Path
from time import monotonic

from shiftopt import run_pipeline


def build(plan, deadline, items, requests, setup, by_end):
    order = sorted(
        items,
        key=lambda j: ((items[j][3][1] if by_end else -requests[items[j][0]][0]), j),
    )
    finish = float("-inf")
    used = defaultdict(float)
    sequence = []
    for j in order:
        if monotonic() >= deadline:
            break
        req, area, duration, *windows = items[j]
        for direction, (early, late) in enumerate(windows):
            start = max(finish + setup, early)
            if start <= late:
                finish = start + duration
                sequence.append((j, direction))
                gain, total, kind = requests[req]
                used[req] = 1 if kind == 0 else used[req] + area / total
                break
    value = 0
    for req, x in used.items():
        gain, total, _ = requests[req]
        value += (
            gain
            * total
            * (0.25 * min(x, 0.4) + min(max(0, x - 0.4), 0.3) + 2 * max(0, x - 0.7))
        )
    return -int(value), sequence


def solve(path, seconds):
    rows = iter(row.split() for row in path.read_text().splitlines() if row.strip())
    header = next(rows)[:3]
    nr, ns = map(int, next(rows))
    next(rows)
    requests = {}
    for _ in range(nr):
        i, g, a, k, _st = next(rows)
        requests[int(i)] = (float(g), float(a), int(k))
    items = {}
    xs = []
    ys = []
    for _ in range(ns):
        j, req, _, twin = map(int, next(rows))
        next(rows)
        area, duration = map(float, next(rows))
        a, b = (list(map(float, next(rows))) for _ in range(2))
        if twin:
            continue
        xs.extend([a[0], b[0]])
        ys.extend([a[1], b[1]])
        windows = [
            (max(p[2], q[2] - duration), min(p[3], q[3] - duration))
            for p, q in ((a, b), (b, a))
        ]
        items[j] = (req, area, duration, *windows)
    diameter = hypot(max(xs) - min(xs), max(ys) - min(ys)) if xs else 0
    setup = 2.5 + 2 * atan(diameter / (2 * 633000)) / 0.05
    steps = [
        partial(build, items=items, requests=requests, setup=setup, by_end=x)
        for x in (True, False)
    ]
    value, seq = run_pipeline(steps, itemgetter(0), initial=(0, []), seconds=seconds)
    return -value, " ".join(header) + "\n" + str(len(seq)) + "\n" + "".join(
        f"{j} {d}\n" for j, d in seq
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "input", type=Path, nargs="?", default=Path(__file__).with_name("example")
    )
    parser.add_argument("--seconds", type=float, default=5)
    args = parser.parse_args()
    print(solve(args.input, args.seconds)[1], end="")
