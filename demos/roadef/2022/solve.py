"""Assign shipments to eligible departures and pack nested stacks along trailer walls."""

import argparse
import csv
from bisect import bisect_right
from collections import Counter, defaultdict
from datetime import date
from contextlib import ExitStack
from functools import lru_cache, partial
from itertools import chain, islice, repeat
from math import isfinite
from pathlib import Path

from time import monotonic

from shiftopt.reassign import reassignment_search
from shiftopt import beam_search, neighborhood_search, run_pipeline


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


def pack_group(rows, truck, ident, limits, combine, beam_width=0, deadline=float("inf"), attempts=0, temperature=0.0):
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
    if not combine or len(base) < 2 or len(order) < 2:
        return base
    if attempts:
        def destroy(state, rng):
            sequence, _ = state
            removed = set(rng.sample(sequence, max(2, len(sequence) // 3)))
            return [i for i in sequence if i not in removed], [i for i in sequence if i in removed]

        def repair(partial_order, rng, deadline):
            kept, removed = partial_order
            for i in removed:
                kept.insert(rng.randrange(len(kept) + 1), i)
            return kept, pack_order((order[i] for i in kept), truck, ident, limits)

        def score(state):
            loads = state[1]
            length = sum(max(load.ends) for load in loads)
            return len(loads) + length / (1 + len(loads) * truck["Length"])

        search = neighborhood_search(destroy, repair, score, attempts=attempts, seed=7, temperature=temperature)
        result = run_pipeline([search], score, initial=(list(range(len(order))), base),
                              seconds=max(0., deadline - monotonic()))
        return result[1]
    if not beam_width:
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
        deadline=min(deadline, monotonic() + 10),
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


def solve(folder, output, combine=True, beam_width=0, group_limit=None, largest_first=False, attempts=0, temperature=0.0, reassign=0):
    if reassign < 0 or (reassign and not combine):
        raise ValueError("reassignment requires consolidation and a nonnegative budget")
    if not isfinite(temperature) or temperature < 0:
        raise ValueError("temperature must be finite and nonnegative")
    if temperature and not attempts:
        raise ValueError("temperature requires neighborhood attempts")
    if attempts < 0 or (attempts and (not combine or beam_width)):
        raise ValueError("neighborhood attempts require consolidation and an exclusive search budget")
    if group_limit is not None and (group_limit < 0 or not (combine and beam_width)):
        raise ValueError("a group limit requires beam search and a nonnegative budget")
    if largest_first and group_limit is None:
        raise ValueError("largest-first requires a group limit")
    trips, bottom_limit = {}, {}
    eligible = defaultdict(set)
    arrivals = {}
    prices = {}
    numeric = "Length Width Height EMmm EMmr CM CJfm CJfc CJfh EM EJhr EJcr EJeh".split()
    for r in records(folder, "trucks"):
        ident = r["Id truck"].strip()
        if ident not in trips:
            trips[ident] = {k: number(r[k]) for k in numeric + ["Max weight", "Max density"]}
        if reassign:
            arrivals[ident] = r["Arrival time"]
            prices[ident] = number(r["Cost"])
        key = route_key(r)
        bottom_limit[ident, key[-1]] = number(r["Max weight on the bottom item in stacks"])
        eligible[key].add((r["Arrival time"], ident))
    eligible = {k: sorted(v) for k, v in eligible.items()}
    def assign_and_pack(plan, deadline):
        batches = defaultdict(list)
        for r in records(folder, "items"):
            if reassign:
                r["_holding"] = number(r["Inventory cost"]) * int(r["Number of items"])
            key = route_key(r)
            schedule = eligible[key]
            i = bisect_right(schedule, (r["Latest arrival time"], chr(0x10FFFF))) - 1
            if i < 0 or schedule[i][0] < r["Earliest arrival time"]:
                raise ValueError(f"No eligible departure for {r['Item ident']}")
            ident = schedule[i][1]
            group = (ident, key[1], r["Supplier dock"], r["Plant dock"])
            batches[group].append(r)
        return {group: (rows, pack_group(rows, trips[group[0]], group[0], bottom_limit, False))
                for group, rows in batches.items()}

    def repack_groups(plan, deadline, width, trials=0):
        proposal = plan.copy()
        for group, (rows, incumbent) in plan.items():
            if monotonic() >= deadline:
                break
            ident = group[0]
            loads = pack_group(rows, trips[ident], ident, bottom_limit, True, width, deadline, trials, temperature)
            if len(loads) < len(incumbent):
                proposal[group] = rows, loads
        return proposal

    def consolidate(plan, deadline):
        return repack_groups(plan, deadline, 0)

    def reorder_stacks(plan, deadline):
        if group_limit is None:
            return repack_groups(plan, deadline, beam_width)

        def try_group(shipment, deadline, *, group):
            rows, incumbent = shipment[group]
            ident = group[0]
            loads = pack_group(rows, trips[ident], ident, bottom_limit, True, beam_width, deadline)
            if len(loads) < len(incumbent):
                return {**shipment, group: (rows, loads)}
            return None

        groups = {partial(try_group, group=key): key for key, (_, loads) in plan.items()
                  if len(loads) > 1}

        def choose_group(shipment, history, remaining):
            tried = {trial.step for trial in history}
            return max((step for step in groups if step not in tried),
                       key=lambda step: len(shipment[groups[step]][1]), default=None)

        return run_pipeline(tuple(groups), truck_count, initial=plan, max_steps=group_limit,
                            seconds=max(0., deadline - monotonic()),
                            policy=choose_group if largest_first else None)

    def truck_count(plan):
        return sum(len(loads) for _, loads in plan.values())

    steps = [assign_and_pack]
    if combine:
        steps.append(consolidate)
        if attempts:
            def search_groups(plan, deadline):
                return repack_groups(plan, deadline, 0, attempts)
            steps.append(search_groups)
        if beam_width:
            steps.append(reorder_stacks)
    score = truck_count
    if reassign:
        weights = next(records(folder, "parameters"))
        transport = number(weights["Coefficient transportation cost"])
        inventory = number(weights["Coefficient inventory cost"])
        extra = number(weights["Coefficient cost extra truck"])

        @lru_cache(None)
        def day(stamp):
            return date(int(stamp[:4]), int(stamp[4:6]), int(stamp[6:8])).toordinal()

        def cost(plan):
            counts = Counter()
            storage = 0.
            for (ident, *_), (rows, loads) in plan.items():
                counts[ident] += len(loads)
                delivered = day(arrivals[ident])
                for r in rows:
                    storage += (day(r["Latest arrival time"]) - delivered) * r["_holding"]
            freight = sum(prices[i] * (n + max(0, n - 1) * extra) for i, n in counts.items())
            return transport * freight + inventory * storage

        def transfers(plan):
            for source, (rows, loads) in sorted(plan.items(), key=lambda item: len(item[1][1])):
                targets = set()
                for r in rows:
                    for stamp, ident in eligible[route_key(r)]:
                        if ident != source[0] and r["Earliest arrival time"] <= stamp <= r["Latest arrival time"]:
                            targets.add(ident)
                for ident in sorted(targets, key=lambda i: (arrivals[i], i), reverse=True):
                    yield source, (ident, *source[1:])

        def rebuild(plan, transfer, deadline):
            source, target = transfer
            if source not in plan:
                return None
            keep, move = [], []
            stamp = arrivals[target[0]]
            for r in plan[source][0]:
                can_move = (r["Earliest arrival time"] <= stamp <= r["Latest arrival time"]
                            and (stamp, target[0]) in eligible[route_key(r)])
                (move if can_move else keep).append(r)
            if not move:
                return None
            updated = plan.copy()
            del updated[source]
            for group, rows in ((source, keep), (target, plan.get(target, ([], []))[0] + move)):
                if rows:
                    if monotonic() >= deadline:
                        return None
                    try:
                        loads = pack_group(rows, trips[group[0]], group[0], bottom_limit, True)
                    except ValueError:
                        return None
                    updated[group] = rows, loads
            return updated

        score = cost
        steps.append(reassignment_search(transfers, rebuild, cost, attempts=reassign))
    shipment = run_pipeline(steps, score)

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
        for (ident, *_), (_, loads) in shipment.items():
            t = trips[ident]
            for load in loads:
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
    parser.add_argument("--group-limit", type=int, help="limit the number of groups to reorder")
    parser.add_argument("--largest-first", action="store_true", help="prioritize groups using the most trucks")
    parser.add_argument("--lns-attempts", type=int, default=0, help="destroy-and-repair trials per group")
    parser.add_argument("--temperature", type=float, default=0.0, help="initial neighborhood search temperature")
    parser.add_argument("--reassign", type=int, default=0, help="number of transfers to try between departures")
    args = parser.parse_args()
    solve(args.instance, args.output, not args.rows_only, args.beam_width, args.group_limit, args.largest_first, args.lns_attempts, args.temperature, args.reassign)
