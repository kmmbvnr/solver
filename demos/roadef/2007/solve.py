"""Schedule skill-qualified teams in precedence order."""

import argparse
import re
from functools import partial
from operator import itemgetter
from pathlib import Path
from time import monotonic

from shiftopt import run_pipeline


def read_groups(line):
    before, inside, after = re.split(r"[\[\]]", line)
    return [list(map(int, x.split())) for x in (before, inside, after)]


def schedule(plan, deadline, tasks, tech, levels, order):
    remaining = set(tasks)
    days = []
    assignments = {}
    ends = [0] * 4
    last_absence = max((d for _, absent in tech.values() for d in absent), default=0)
    while remaining:
        if monotonic() >= deadline:
            return None
        day = len(days) + 1
        available = [i for i, (_, absent) in tech.items() if day not in absent]
        days.append((set(tech) - set(available), available))
        time = 0
        counts = [
            sum(tech[i][0][j // levels] >= j % levels + 1 for i in available)
            for j in range(len(next(iter(tasks.values()))[-1]))
        ]
        for i in order:
            if i not in remaining:
                continue
            duration, preds, priority, needs = tasks[i]
            if (
                remaining.intersection(preds)
                or duration + time > 120
                or any(a < b for a, b in zip(counts, needs))
            ):
                continue
            assignments[i] = (day, time, 1)
            remaining.remove(i)
            time += duration
            end = (day - 1) * 120 + time
            ends[priority - 1] = end
            ends[3] = end
        if time == 0 and day > last_absence:
            return None
    return sum(a * b for a, b in zip(ends, (28, 14, 4, 1))), days, assignments


def solve(path, seconds):
    inst = (path / "instance").read_text().splitlines()[1].split()
    tech = {}
    for line in (path / "tech_list").read_text().splitlines()[1:]:
        if line.strip():
            row, absent, _ = read_groups(line)
            tech[row[0]] = (row[1:], absent)
    tasks = {}
    for line in (path / "interv_list").read_text().splitlines()[1:]:
        if line.strip():
            (i, duration), preds, (prio, _fee, *needs) = read_groups(line)
            tasks[i] = duration, preds, prio, needs
    orders = [list(tasks), sorted(tasks, key=lambda i: (tasks[i][2], tasks[i][0], i))]
    steps = [
        partial(schedule, tasks=tasks, tech=tech, levels=int(inst[2]), order=o)
        for o in orders
    ]
    plan = run_pipeline(steps, itemgetter(0), seconds=seconds)
    if plan is None:
        raise ValueError("no complete team schedule found")
    return plan


def group(ids):
    return "[ " + " ".join(map(str, sorted(ids))) + " ]"


def write_solution(path, plan):
    _, days, assignments = plan
    path.mkdir(parents=True, exist_ok=True)
    (path / "tech_teams").write_text(
        "day not working team1\n"
        + "".join(
            f"{d} {group(off)} {group(on)}\n" for d, (off, on) in enumerate(days, 1)
        )
    )
    (path / "interv_dates").write_text(
        "interv day time team\n"
        + "".join(f"{i} {d} {t} {g}\n" for i, (d, t, g) in sorted(assignments.items()))
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "input", type=Path, nargs="?", default=Path(__file__).with_name("example")
    )
    parser.add_argument("--seconds", type=float, default=5)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    plan = solve(args.input, args.seconds)
    write_solution(args.output, plan)
    print(plan[0])
