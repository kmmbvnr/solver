"""Assign shipments to eligible departures and pack nested stacks along trailer walls."""

import argparse
import csv
from bisect import bisect_right
from collections import defaultdict
from contextlib import ExitStack
from itertools import chain, islice, repeat
from pathlib import Path

from time import monotonic

from shiftopt import beam_search, run_pipeline


def records(folder, kind):
    with (folder / f"input_{kind}.csv").open(encoding="latin1", newline="") as f:
        yield from csv.DictReader(f, delimiter=";")


def number(s):
    return float(s.replace(",", "."))


def route_key(row):
    return tuple(
        row[k].strip().replace(" ", "") for k in ("Plant code", "Supplier code", "Product code")
    )


def axles(truck, mass, moment):
    harness = (
        mass * (truck["EJeh"] + truck["EJhr"]) - moment + truck["EM"] * truck["EJcr"]
    ) / truck["EJhr"]
    return (
        (truck["CM"] * truck["CJfc"] + harness * truck["CJfh"]) / truck["CJfm"],
        mass + truck["EM"] - harness,
    )


class Load:
    def __init__(self, truck):
        self.truck = truck
        self.boxes = []
        self.stacks = []
        self.mass = self.moment = self.volume = 0
        self.ends = [0, 0]

    def place(self, count, item):
        t = self.truck
        a, b, h, weight, nest, forced = item
        fits = []
        for length, width, direction in ((a, b, "lengthwise"), (b, a, "widthwise")):
            if forced not in ("none", direction) or width > t["Width"]:
                continue
            for lane, x in enumerate(self.ends):
                y = 0 if lane == 0 else int(t["Width"]) - width
                if x + length > t["Length"] or any(
                    x < xx + dx and xx < x + length and y < yy + dy and yy < y + width
                    for xx, yy, dx, dy in self.boxes
                ):
                    continue
                mass = self.mass + count * weight
                moment = self.moment + count * weight * (x + length / 2)
                middle, rear = axles(t, mass, moment)
                if mass <= t["Max weight"] and middle <= t["EMmm"] and rear <= t["EMmr"]:
                    fits.append(
                        (max(max(self.ends), x + length), x + length, lane, x, y, length, width)
                    )
        if not fits:
            return None
        _, end, lane, x, y, length, width = min(fits)
        self.ends[lane] = end
        self.boxes.append((x, y, length, width))
        self.mass += count * weight
        self.moment += count * weight * (x + length / 2)
        self.volume += length * width * (h + (count - 1) * (h - nest)) / 1e9
        return x, y, length, width


def pack_group(rows, truck, ident, limits, combine, beam_width=0):
    """Build homogeneous stacks and preserve the identity of every shipped unit."""
    groups = defaultdict(list)
    for r in rows:
        key = (
            r["Product code"],
            r["Stackability code"],
            r["Length"],
            r["Width"],
            r["Height"],
            r["Weight"],
            r["Nesting height"],
            r["Forced orientation"],
            r["Max stackability"],
        )
        groups[key if combine else r["Item ident"]].append(r)
    order = list(groups.values())
    if combine:
        # Fill long and wide stacks first, before the remaining lanes get fragmented.
        order = sorted(order, key=lambda g: int(g[0]["Length"]) * int(g[0]["Width"]), reverse=True)
    base = pack_order(order, truck, ident, limits)
    if not combine or not beam_width or len(base) < 2 or len(order) < 2:
        return base
    best = base

    def expand(state):
        nonlocal best
        depth, sequence, plan = state
        yield depth + 1, sequence, plan
        for i in range(depth, min(len(sequence) - 1, depth + 3)):
            proposal = list(sequence)
            proposal[i], proposal[i + 1] = proposal[i + 1], proposal[i]
            trial = pack_order((order[j] for j in proposal), truck, ident, limits)
            if len(trial) < len(best):
                best = trial
            yield depth + 1, tuple(proposal), trial

    beam_search(
        (0, tuple(range(len(order))), base),
        expand,
        key=lambda state: state[1],
        priority=lambda state: (len(state[2]), sum(max(load.ends) for load in state[2])),
        complete=lambda state: state[0] == 3,
        width=beam_width,
        deadline=monotonic() + 10,
    )
    return best


def pack_order(order, truck, ident, limits):
    loads = []
    load = Load(truck)
    for group in order:
        r = group[0]
        a, b, h = (int(r[k]) for k in ("Length", "Width", "Height"))
        nest, weight = int(r["Nesting height"]), number(r["Weight"])
        item = (a, b, h, weight, nest, r["Forced orientation"].strip().lower())
        units = chain.from_iterable(
            repeat(row["Item ident"], int(row["Number of items"])) for row in group
        )
        left = sum(int(row["Number of items"]) for row in group)
        cap = min(int(r["Max stackability"]), left)
        if h > truck["Height"]:
            raise ValueError("Item exceeds trailer height")
        if h > nest:
            cap = min(cap, 1 + int((truck["Height"] - h) // (h - nest)))
        else:
            cap = 1
        if weight:
            cap = min(
                cap,
                int(truck["Max density"] * a * b / 1e6 / weight + 1e-9),
                1 + int(limits[ident, route_key(r)[-1]] / weight + 1e-9),
            )
        while left:
            count = min(left, cap)
            pos = load.place(count, item) if count else None
            if pos is None and load.boxes:
                loads.append(load)
                load = Load(truck)
                continue
            while pos is None and count > 1:
                count -= 1
                pos = load.place(count, item)
            if pos is None:
                raise ValueError(f"Cannot load {r['Item ident']} in {ident}")
            load.stacks.append((pos, h, nest, list(islice(units, count))))
            left -= count
    if load.boxes:
        loads.append(load)
    return loads


def solve(folder, output, combine=True, beam_width=0):
    trips, bottom_limit = {}, {}
    eligible = defaultdict(set)
    numeric = "Length Width Height EMmm EMmr CM CJfm CJfc CJfh EM EJhr EJcr EJeh".split()
    for r in records(folder, "trucks"):
        ident = r["Id truck"].strip()
        if ident not in trips:
            trips[ident] = {k: number(r[k]) for k in numeric + ["Max weight", "Max density"]}
        key = route_key(r)
        bottom_limit[ident, key[-1]] = number(r["Max weight on the bottom item in stacks"])
        eligible[key].add((r["Arrival time"], ident))
    eligible = {k: sorted(v) for k, v in eligible.items()}
    batches = defaultdict(list)
    for r in records(folder, "items"):
        key = route_key(r)
        schedule = eligible[key]
        i = bisect_right(schedule, (r["Latest arrival time"], chr(0x10FFFF))) - 1
        if i < 0 or schedule[i][0] < r["Earliest arrival time"]:
            raise ValueError(f"No eligible departure for {r['Item ident']}")
        ident = schedule[i][1]
        group = (ident, key[1], r["Supplier dock"], r["Plant dock"])
        batches[group].append(r)
    output.mkdir(parents=True, exist_ok=True)
    headers = {
        "items": "Item ident;Id truck;Id stack;Item code;X origin;Y origin;Z origin;X extremity;Y extremity;Z extremity",
        "stacks": "Id truck;Id stack;Stack code;X origin;Y origin;Z origin;X extremity;Y extremity;Z extremity",
        "trucks": "Id truck;Loaded length;Weight of loaded items;Volume of loaded items;EMm;EMr",
    }
    copies = defaultdict(int)
    with ExitStack() as files:
        writers = {}
        for kind, header in headers.items():
            f = files.enter_context((output / f"output_{kind}.csv").open("w", newline=""))
            writers[kind] = csv.writer(f, delimiter=";", lineterminator="\n")
            writers[kind].writerow(header.split(";"))
        for (ident, *_), rows in batches.items():
            t = trips[ident]

            def original(plan, deadline):
                return pack_group(rows, t, ident, bottom_limit, False)

            def consolidate(plan, deadline):
                return pack_group(rows, t, ident, bottom_limit, True, beam_width)

            steps = [original, consolidate] if combine else [original]
            for load in run_pipeline(steps, len):
                truck = ident if not copies[ident] else f"Q{ident[1:]}_{copies[ident]}"
                copies[ident] += 1
                writers["trucks"].writerow(
                    (
                        truck,
                        max(load.ends),
                        load.mass,
                        load.volume,
                        *axles(t, load.mass, load.moment),
                    )
                )
                for i, (pos, h, nest, units) in enumerate(load.stacks, 1):
                    x, y, dx, dy = pos
                    stack = f"{truck}_{i}"
                    height = h + (len(units) - 1) * (h - nest)
                    writers["stacks"].writerow(
                        (truck, stack, i, x, y, 0, x + dx, y + dy, height)
                    )
                    for k, item_id in enumerate(units):
                        z = h + (k - 1) * (h - nest) if k else 0
                        writers["items"].writerow(
                            (
                                item_id,
                                truck,
                                stack,
                                k + 1,
                                x,
                                y,
                                z,
                                x + dx,
                                y + dy,
                                h + k * (h - nest),
                            )
                        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("instance", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--rows-only", action="store_true", help="disable stack consolidation")
    parser.add_argument("--beam-width", type=int, choices=range(3), default=0,
                        help="explore alternative stack orders (0 disables search)")
    args = parser.parse_args()
    solve(args.instance, args.output, not args.rows_only, args.beam_width)
