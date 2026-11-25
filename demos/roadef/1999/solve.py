"""Allocate existing equipment to rental orders; subcontract the uncovered demand."""

import argparse
import re
from collections import Counter
from functools import partial
from operator import itemgetter
from pathlib import Path
from time import monotonic

from shiftopt import run_pipeline


def construct(plan, deadline, resources, orders, eligible, maintenance, order):
    usage = {(r, i): [] for r, p in resources.items() for i in range(p[0])}
    wear = dict.fromkeys(usage, 0)
    result = []
    total = 0
    for oid in order:
        if monotonic() >= deadline:
            return None
        start, end, qty, requested = orders[oid]
        duration = end - start
        rental = resources[requested][4] * duration
        allocated = Counter()
        for unit in sorted(
            usage,
            key=lambda unit: resources[unit[0]][5] + duration * resources[unit[0]][6],
        ):
            r, i = unit
            if not qty:
                break
            if (
                r not in eligible[requested]
                or resources[r][5] + duration * resources[r][6] >= rental
            ):
                continue
            if maintenance and wear[unit] + duration > resources[r][1]:
                continue
            if any(a < end and start < b for a, b in usage[unit]):
                continue
            usage[unit].append((start, end))
            wear[unit] += duration
            total += resources[r][5] + duration * resources[r][6]
            allocated[r] += 1
            qty -= 1
            if maintenance:
                result.append(f"alloc({r},{oid},{i + 1})")
        if not maintenance:
            result.extend(f"alloc({r},{oid},{n})" for r, n in allocated.items())
        if qty:
            total += qty * rental
            result.append(f"rent({requested},{oid},{qty})")
    return total, "".join(row + "\n" for row in result)


def maintain(plan, deadline, resources, orders, eligible, horizon):
    start, end, capacity = horizon
    if capacity < 0:
        return None
    workshop = [0] * (end - start)
    units = {r: [[start, 0] for _ in range(row[0])] for r, row in resources.items()}
    lines = []
    cost = 0
    for oid in sorted(orders, key=lambda i: orders[i][0]):
        if monotonic() >= deadline:
            return None
        a, b, qty, requested = orders[oid]
        duration = b - a
        rental = duration * resources[requested][4]
        for _ in range(qty):
            best = (rental, None)
            for r in eligible[requested]:
                (
                    stock,
                    limit,
                    service,
                    demand,
                    _,
                    fixed,
                    rate,
                    purchase,
                    holding,
                    fee,
                    maxbuy,
                ) = resources[r]
                assignment = fixed + rate * duration
                for index, (free, wear) in enumerate(units[r]):
                    if free > a:
                        continue
                    slot = None
                    if wear and wear + duration > limit:
                        if assignment + fee >= best[0]:
                            continue
                        slot = next(
                            (
                                t
                                for t in range(free, a - service + 1)
                                if all(
                                    workshop[h - start] + demand <= capacity
                                    for h in range(t, t + service)
                                )
                            ),
                            None,
                        )
                        if slot is None:
                            continue
                    value = assignment + (fee if slot is not None else 0)
                    if value < best[0]:
                        best = (value, (r, index, slot))
                new_cost = assignment + purchase + holding * (end - a)
                if (maxbuy < 0 or len(units[r]) - stock < maxbuy) and new_cost < best[
                    0
                ]:
                    best = (new_cost, (r, len(units[r]), None))
            value, choice = best
            cost += value
            if choice is None:
                lines.append(f"rent({requested},{oid},1)")
                continue
            r, index, slot = choice
            if index == len(units[r]):
                units[r].append([a, 0])
                lines.append(f"buy({r},{a},{index + 1})")
            if slot is not None:
                for h in range(slot, slot + resources[r][2]):
                    workshop[h - start] += resources[r][3]
                units[r][index][1] = 0
                lines.append(f"maint({r},{index + 1},{slot})")
            units[r][index] = [b, units[r][index][1] + duration]
            lines.append(f"alloc({r},{oid},{index + 1})")
    # The native format has one rental quantity per resource type and order.
    counts = Counter(line for line in lines if line.startswith("rent"))
    output = [line for line in lines if not line.startswith("rent")]
    output.extend(line.rsplit(",", 1)[0] + f",{n})" for line, n in counts.items())
    return cost, "\n".join(output) + "\n"


def solve(path, seconds):
    resources = {}
    orders = {}
    subs = []
    for kind, fields in re.findall(
        r"(globals|resource|order|substituable)\s*\(([^)]+)\)", path.read_text()
    ):
        a, *rest = map(int, fields.split(","))
        if kind == "resource":
            resources[a] = rest
        elif kind == "order":
            orders[a] = rest
        elif kind == "globals":
            horizon = (a, *rest)
            maintenance = rest[-1] >= 0
        else:
            subs.append((a, rest[0]))
    eligible = {r: {r} for r in resources}
    for a, b in subs:
        eligible[a].add(b)
    priorities = [
        sorted(orders, key=lambda i: orders[i][0]),
        sorted(orders, key=lambda i: orders[i][1] - orders[i][0], reverse=True),
    ]
    steps = [
        partial(
            construct,
            resources=resources,
            orders=orders,
            eligible=eligible,
            maintenance=maintenance,
            order=o,
        )
        for o in priorities
    ]
    steps.append(
        partial(
            maintain,
            resources=resources,
            orders=orders,
            eligible=eligible,
            horizon=horizon,
        )
    )
    result = run_pipeline(steps, itemgetter(0), seconds=seconds)
    if result is None:
        raise TimeoutError("no complete allocation")
    value, text = result
    blocks = ("rent", "buy", "alloc", "maint")
    ordered = [
        line
        for kind in blocks
        for line in text.splitlines()
        if line.startswith(kind + "(")
    ]
    return value, "".join(line + "\n" for line in ordered)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "input", type=Path, nargs="?", default=Path(__file__).with_name("I808nb.tes")
    )
    parser.add_argument("--seconds", type=float, default=5)
    args = parser.parse_args()
    print(solve(args.input, args.seconds)[1], end="")
