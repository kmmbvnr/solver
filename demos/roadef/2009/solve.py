"""Recover original rotations by cancelling disrupted legs and reconnecting aircraft at their scheduled airports."""

import argparse
import re
import shutil
import subprocess
from datetime import datetime, timedelta
from functools import partial
from operator import itemgetter
from pathlib import Path
from tempfile import TemporaryDirectory
from time import monotonic

from shiftopt import run_pipeline


def rows(path, name):
    return [
        s.split()
        for s in (path / (name + ".csv")).read_text().splitlines()
        if s.strip() and s.strip() != "#"
    ]


def stamp(date, clock):
    hm, *extra = clock.split("+")
    return datetime.strptime(date + " " + hm, "%d/%m/%y %H:%M") + timedelta(
        days=int(extra[0]) if extra else 0
    )


def shift_clock(clock, minutes):
    base = stamp("01/01/00", "00:00")
    shifted = stamp("01/01/00", clock) + timedelta(minutes=minutes)
    days = (shifted - base).days
    return shifted.strftime("%H:%M") + (f"+{days}" if days else "")


def disruptions(path, flights):
    unavailable = {
        (f, d) for f, d, delay in rows(path, "alt_flights") if int(delay) < 0
    }
    closed = [
        (p, stamp(d, t), stamp(e, u))
        for p, d, t, e, u, *_ in rows(path, "alt_airports")
    ]
    grounded = [
        (p, stamp(d, t), stamp(e, u)) for p, d, t, e, u in rows(path, "alt_aircraft")
    ]
    for f, d, plane in rows(path, "rotations"):
        _, origin, dest, t, u, _ = flights[f]
        takeoff, landing = stamp(d, t), stamp(d, u)
        if any(
            (origin == p and a <= takeoff < b) or (dest == p and a <= landing < b)
            for p, a, b in closed
        ) or any(plane == p and takeoff < b and landing > a for p, a, b in grounded):
            unavailable.add((f, d))
    return unavailable


def propose(plan, deadline, path, flights, blocked, reconnect, evaluate):
    start = stamp(*rows(path, "config")[0][:2])
    rotations = rows(path, "rotations")
    location = {r[0]: r[8] for r in rows(path, "aircraft")}
    grounded = set()
    delays = {(f, d): int(delay) for f, d, delay in rows(path, "alt_flights")}
    cancel = {key for key, delay in delays.items() if delay < 0}
    for f, d, plane in sorted(rotations, key=lambda r: stamp(r[1], flights[r[0]][3])):
        _, origin, dest, t, _u, _ = flights[f]
        if plane == "cancelled":
            cancel.add((f, d))
            continue
        if plane.startswith("TranspCom") or (f, d) in cancel:
            continue
        if stamp(d, t) >= start and (
            (f, d) in blocked or location[plane] != origin or plane in grounded
        ):
            cancel.add((f, d))
            if not reconnect:
                grounded.add(plane)
        else:
            location[plane] = dest
    rotations_out = []
    for f, d, p in rotations:
        row = flights[f].copy()
        delay = delays.get((f, d), 0)
        if delay > 0:
            row[3] = shift_clock(row[3], delay)
            row[4] = shift_clock(row[4], delay)
        rotations_out.append(
            " ".join([*row, d, "cancelled" if (f, d) in cancel else p])
        )
    itin = []
    for row in rows(path, "itineraries"):
        legs = list(zip(row[4::3], row[5::3]))
        itinerary = row[:4] + ["cancelled"] if cancel.intersection(legs) else row
        itin.append(" ".join(itinerary))
    solution = {
        "sol_rotations.csv": "\n".join(rotations_out) + "\n#\n",
        "sol_itineraries.csv": "\n".join(itin) + "\n#\n",
    }
    cost = evaluate(solution, deadline)
    return None if cost is None else (cost, solution)


def checked(solution, deadline, path, checker, cost_checker, runner):
    with TemporaryDirectory() as temp:
        work = Path(temp) / "i"
        work.mkdir()
        for file in path.glob("*.csv"):
            if file.name not in solution:
                shutil.copyfile(file, work / file.name)
        for name, content in solution.items():
            (work / name).write_text(content)
        for binary in (checker, cost_checker):
            try:
                proc = subprocess.run(
                    [*runner, str(binary), work.name],
                    cwd=temp,
                    check=False,
                    capture_output=True,
                    timeout=max(0.01, deadline - monotonic()),
                )
            except subprocess.TimeoutExpired:
                return None
            if proc.returncode:
                return None
            if binary == checker:
                reports = list((work / "results").glob("check*.txt"))
                if len(reports) != 11 or any(
                    p.read_text(errors="replace").strip() for p in reports
                ):
                    return None
        match = re.search(
            r"Total\s+Cost\s*[:=]\s*([-+0-9.eE]+)",
            proc.stdout.decode(errors="replace"),
            re.IGNORECASE,
        )
        if not match:
            raise ValueError("cost checker did not report total cost")
        return float(match[1])


def solve(path, seconds, checker, cost_checker, runner=()):
    flights = {r[0]: r for r in rows(path, "flights")}
    blocked = disruptions(path, flights)
    evaluate = partial(
        checked,
        path=path,
        checker=checker.resolve(),
        cost_checker=cost_checker.resolve(),
        runner=runner,
    )
    steps = [
        partial(
            propose,
            path=path,
            flights=flights,
            blocked=blocked,
            reconnect=r,
            evaluate=evaluate,
        )
        for r in (True, False)
    ]
    best = run_pipeline(steps, itemgetter(0), seconds=seconds)
    if best is None:
        raise ValueError("no checker-accepted recovery plan within budget")
    return best


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--checker", type=Path, required=True)
    parser.add_argument("--cost-checker", type=Path, required=True)
    parser.add_argument("--runner", help="optional Linux executable emulator")
    parser.add_argument("--seconds", type=float, default=30)
    args = parser.parse_args()
    cost, files = solve(
        args.input,
        args.seconds,
        args.checker,
        args.cost_checker,
        [args.runner] if args.runner else [],
    )
    args.output.mkdir(parents=True, exist_ok=True)
    for name, data in files.items():
        (args.output / name).write_text(data)
    print(cost)
