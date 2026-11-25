"""Build outage calendars, refuel plants and dispatch production across scenarios."""

import argparse
import re
from collections import defaultdict
from datetime import datetime, timezone
from functools import partial
from operator import itemgetter
from pathlib import Path
from random import Random
from time import monotonic

import numpy as np

from shiftopt import run_pipeline


def redispatch(plan, deadline, plants, hours):
    value, original = plan
    lines = original.copy()
    active = False
    slots = {}
    change = 0.0
    scenarios = sum(line.startswith("scenario ") for line in lines)
    for i, line in enumerate(original):
        fields = line.split()
        if not fields:
            continue
        if fields[0] == "scenario":
            scenario = int(fields[1])
        elif fields[:2] == ["begin", "type1_plants"]:
            active = True
            slots = {}
        elif active and fields[0] == "name":
            slots[int(fields[2])] = i
        elif active and fields[:2] == ["end", "type1_plants"]:
            active = False
            indices = list(slots)
            if not indices:
                continue
            old = np.array([lines[slots[j]].split()[3:] for j in indices], dtype=float)
            low, high, prices = (
                np.array([plants[j][key][scenario] for j in indices])
                for key in ("pmin", "pmax", "cost")
            )
            new = low.copy()
            remaining = old.sum(axis=0) - low.sum(axis=0)
            periods = np.arange(len(hours))
            for row in np.argsort(prices, axis=0, kind="stable"):
                if monotonic() >= deadline:
                    return None
                added = np.minimum(np.maximum(0, remaining), (high - low)[row, periods])
                new[row, periods] += added
                remaining -= added
            if np.max(np.abs(remaining)) > 1e-6:
                return None
            change += float(np.sum((new - old) * prices * hours)) / scenarios
            for r, j in enumerate(indices):
                h = lines[slots[j]].split()[:3]
                lines[slots[j]] = " ".join(h + [format(x, ".15g") for x in new[r]])
    for i, line in enumerate(lines):
        if line.startswith("cost "):
            lines[i] = f"cost {value + change:.15g}"
    return value + change, lines


def blocks(text, name):
    """Read repeated named blocks from EDF's line-oriented data format."""
    pattern = rf"^begin {name}\s*\n(.*?)^end {name}\s*$"
    result = []
    for chunk in re.findall(pattern, text, re.MULTILINE | re.DOTALL):
        values = defaultdict(list)
        for row in chunk.splitlines():
            if row.strip():
                key, *rest = row.split()
                values[key].append(rest)
        result.append(values)
    return result


def floats(block, key):
    return np.array(block[key][0], dtype=float)


def choose_dates(units, windows, spacing, seed):
    """Place outages inside their weekly windows, respecting CT13 and CT14."""
    rng = Random(seed)
    dates = {i: [] for i in units}
    placed = []
    for (i, k), (lo, hi) in sorted(
        windows.items(), key=lambda item: (item[1][0], item[0])
    ):
        duration = int(units[i]["durations"][0][k])
        candidates = list(range(lo, hi + 1))
        if seed:
            rng.shuffle(candidates)
        chosen = None
        for start in candidates:
            if k != len(dates[i]) or (
                k and start < dates[i][-1] + int(units[i]["durations"][0][k - 1])
            ):
                continue
            if any(
                start < stop + gap and start + duration + gap > begin
                for j, begin, stop in placed
                if j != i
                for group, gap in spacing
                if i in group and j in group
            ):
                continue
            chosen = start
            break
        if chosen is None:
            return None
        placed.append((i, chosen, chosen + duration))
        dates[i].append(chosen)
    return dates


def trajectory(unit, dates, hours, weeks, fill):
    cap = floats(unit, "pmax")
    stock = float(unit["stock"][0][0])
    minimum = floats(unit, "min_refuel")
    reload = minimum + fill * (floats(unit, "max_refuel") - minimum)
    ratio = floats(unit, "refuel_ratio")
    thresholds = np.r_[
        floats(unit, "current_campaign_stock_threshold"),
        floats(unit, "stock_threshold"),
    ]
    profiles = [
        np.array(row, dtype=float).reshape(-1, 2)[::-1]
        for row in unit["decrease_profile"]
    ]
    stop_lengths = floats(unit, "durations")
    max_before = floats(unit, "max_stock_before_refueling")
    max_after = floats(unit, "max_stock_after_refueling")
    generation = np.zeros(len(hours))
    fuel = np.empty(len(hours))
    k = 0
    online_week = -1
    for t, (dt, week) in enumerate(zip(hours, weeks)):
        fuel[t] = stock
        if k < len(dates) and week == dates[k]:
            if stock > max_before[k]:
                return None
            stock = (
                (1 - 1 / ratio[k]) * (stock - thresholds[k])
                + reload[k]
                + thresholds[k + 1]
            )
            if stock > max_after[k] or stock < 0:
                return None
            online_week = week + stop_lengths[k]
            k += 1
        elif week >= online_week:
            power = cap[t]
            if stock < thresholds[k]:
                curve = profiles[k]
                power *= np.interp(stock, curve[:, 0], curve[:, 1])
                if stock < power * dt:
                    power = 0
            if power * dt > stock + 1e-6:
                return None
            generation[t] = power
            stock -= power * dt
    cost = np.dot(reload, floats(unit, "refueling_cost")) - stock * float(
        unit["fuel_price"][0][0]
    )
    return generation, fuel, stock, reload, cost


def numbers(values):
    return " ".join(format(x, ".16g") for x in values)


def construct(plan, deadline, main, thermal, units, windows, spacing, seed, name):
    dates = choose_dates(units, windows, spacing, seed // 3)
    if dates is None:
        return None
    hours = floats(main, "durations")
    weeks = ((np.cumsum(hours) - hours) / 168).astype(int)
    outages = ["begin outages"]
    type2 = ["begin type2_plants"]
    produced = np.zeros(len(hours))
    cost = 0.0
    for i, unit in units.items():
        if monotonic() >= deadline:
            return None
        curve = trajectory(unit, dates[i], hours, weeks, (1.0, 0.0, 0.5)[seed % 3])
        if curve is None:
            return None
        generation, fuel, stock, reload, expense = curve
        cost += expense
        produced += generation
        label = unit["name"][0][0]
        outages.extend(
            [
                f"name {label}",
                f"index {i}",
                "outage_dates " + numbers(dates[i]),
                "reloaded_fuel " + numbers(reload),
            ]
        )
        type2.extend(
            [
                f"name {label} {i} " + numbers(generation),
                "fuel_variation " + numbers(fuel),
                f"remaining_fuel_at_the_end {stock:.16g}",
            ]
        )
    schedules = []
    demands = main["demand"]
    periods = np.arange(len(hours))
    for s, demand in enumerate(demands):
        prices = np.array([u["cost"][s] for u in thermal], dtype=float)
        power = np.array([u["pmin"][s] for u in thermal], dtype=float)
        headroom = np.array([u["pmax"][s] for u in thermal], dtype=float) - power
        remaining = np.array(demand, dtype=float) - produced - power.sum(axis=0)
        if np.any(remaining < -0.000001):
            return None
        for row in np.argsort(prices, axis=0, kind="stable"):
            extra = np.minimum(remaining, headroom[row, periods])
            power[row, periods] += extra
            remaining -= extra
        if np.max(abs(remaining)) > 1e-6:
            return None
        cost += np.sum(prices * power * hours) / len(demands)
        schedules.extend([f"scenario {s}", "begin type1_plants"])
        schedules.extend(
            "name " + u["name"][0][0] + " " + u["index"][0][0] + " " + numbers(power[j])
            for j, u in enumerate(thermal)
        )
        schedules.extend(["end type1_plants", *type2, "end type2_plants"])
    lines = [
        "begin main",
        "team_identifier ShiftOpt",
        "solution_time_date "
        + datetime.now(timezone.utc).strftime("%d/%m/%y %H:%M:%S"),
        "solution_running_time 00:00:00",
        f"name_of_data_set_used_for_solution {name}",
        f"cost {cost:.16g}",
        "end main",
        *outages,
        "end outages",
        "begin power_output",
        *schedules,
        "end power_output",
    ]
    return float(cost), lines


def solve(path, seconds, seed=None):
    text = path.read_text()
    main = blocks(text, "main")[0]
    all_units = blocks(text, "powerplant")
    units = {int(u["index"][0][0]): u for u in all_units if u["type"][0] == ["2"]}
    thermal = [u for u in all_units if u["type"][0] == ["1"]]
    windows = {}
    spacing = []
    supported = True
    for rule in blocks(text, "constraint"):
        kind = int(rule["type"][0][0])
        if kind == 13:
            key = (int(rule["powerplant"][0][0]), int(rule["campaign"][0][0]))
            windows[key] = (
                int(rule["earliest_stop_time"][0][0]),
                int(rule["latest_stop_time"][0][0]),
            )
        elif kind == 14:
            spacing.append((set(map(int, rule["set"][0])), int(rule["spacing"][0][0])))
        else:
            supported = False
    expected = {
        (i, k) for i, u in units.items() for k in range(int(u["campaigns"][0][0]))
    }
    last_week = int(main["weeks"][0][0]) - 1
    supported = (
        supported
        and windows.keys() == expected
        and all(0 <= lo <= hi <= last_week for lo, hi in windows.values())
    )
    steps = []
    initial = None
    if seed is not None:
        hours = floats(main, "durations")
        plants = {
            int(u["index"][0][0]): {
                key: [np.array(v, dtype=float) for v in u[key]]
                for key in ("pmin", "pmax", "cost")
            }
            for u in thermal
        }
        lines = seed.read_text().splitlines()
        cost = float(
            next(line.split()[1] for line in lines if line.startswith("cost "))
        )
        initial = (cost, lines)
        steps.append(partial(redispatch, plants=plants, hours=hours))
    if supported and thermal:
        steps.extend(
            partial(
                construct,
                main=main,
                thermal=thermal,
                units=units,
                windows=windows,
                spacing=spacing,
                seed=i,
                name=path.name,
            )
            for i in range(300 if units else 1)
        )
    if not steps:
        raise ValueError(
            "provide --seed for constraints outside the outage constructor"
        )
    result = run_pipeline(steps, itemgetter(0), initial=initial, seconds=seconds)
    if result is None:
        raise ValueError("no feasible production schedule within budget")
    return result[0], "\n".join(result[1]) + "\n"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "input", type=Path, nargs="?", default=Path(__file__).with_name("data0.txt")
    )
    parser.add_argument("--seconds", type=float, default=5)
    parser.add_argument(
        "--seed", type=Path, help="feasible full solution for this instance"
    )
    args = parser.parse_args()
    print(solve(args.input, args.seconds, args.seed)[1], end="")
