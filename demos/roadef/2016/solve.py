"""Build and improve a ROADEF inventory-routing schedule with one command."""

import argparse
import json
import shutil
import sys
import tempfile
import time
import xml.etree.ElementTree as ET
from collections import defaultdict
from itertools import pairwise
from pathlib import Path

from ortools.sat.python import cp_model

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
from roadef_calendar_search import search
from roadef_feasible import solve as assign_with_cp_sat
from instance_xml import table
from roadef_quantities import optimize as optimize_volumes
from roadef_route_pool import optimize as optimize_routes
from instance_xml import atomic_output


def retime(instance, incumbent, output, seconds):
    """Minimize paid shift duration with fixed visits, quantities and layover legs."""
    started = time.monotonic()
    root = ET.parse(instance).getroot()
    plan = ET.parse(incumbent)
    unit = int(root.findtext("unit"))
    travel = table(root, "timeMatrices").astype(int)
    drivers = list(root.find("drivers"))
    sites = {int(c.findtext("index")): c for c in root.find("customers")}
    setup = {
        int(c.findtext("index")): int(c.findtext("setupTime"))
        for group in ("customers", "sources")
        for c in root.find(group)
    }
    model = cp_model.CpModel()
    changes, durations = [], []
    visits = defaultdict(list)

    def minute(node, lo, hi):
        var = model.new_int_var(int(lo), int(hi), "")
        model.add_hint(var, int(node.text))
        changes.append((node, var))
        return var

    for shift in plan.getroot().find("Shifts"):
        driver = drivers[int(shift.findtext("driver"))]
        rest = int(driver.findtext("LayoverDuration"))
        rate = float(driver.findtext("TimeCost"))
        operations = list(shift.find("operations"))
        clock = shift.find("start")
        first, last = int(clock.text), int(operations[-1].findtext("arrival"))
        # Keep every shift inside its original interval. All driver/trailer
        # availability, inter-shift rests and trailer stock order then survive.
        departure = minute(clock, first, last)
        prev, ready, old_ready = 0, departure, first
        for op in operations:
            p = int(op.findtext("point"))
            node = op.find("arrival")
            old = int(node.text)
            lo, hi = first, last
            if p in sites:
                site = sites[p]
                for w in site.find("timewindows"):
                    a, b = int(w.findtext("start")), int(w.findtext("end")) - setup[p]
                    if a <= old <= b:
                        lo, hi = max(lo, a), min(hi, b)
                        break
                else:
                    raise ValueError(f"Arrival outside opening hours at point {p}")
                if int(site.findtext("callIn")):
                    for order in site.find("orders"):
                        a, b = (
                            int(order.findtext("earliestTime")),
                            int(order.findtext("latestTime")),
                        )
                        if old < a:
                            hi = min(hi, a - 1)
                        elif old > b:
                            lo = max(lo, b + 1)
                        else:
                            lo, hi = max(lo, a), min(hi, b)
                else:
                    bucket = old // unit * unit
                    lo, hi = max(lo, bucket), min(hi, bucket + unit - 1)
            at = minute(node, lo, hi)
            leg = int(travel[prev, p])
            waiting = at - ready - leg
            old_wait = old - old_ready - leg
            has_rest = rest > 0 and old_wait >= rest
            model.add(waiting >= (rest if has_rest else 0))
            if rest > 0 and not has_rest:
                model.add(waiting < rest)
            if p in sites:
                visits[p].append((old, at))
            prev, ready, old_ready = p, at + setup[p], old + setup[p]
        # The return leg, setups, distance and number of layovers are constant.
        durations.append((rate, ready - departure, old_ready - first))

    for p, entries in visits.items():
        ordered = sorted(entries, key=lambda row: row[0])
        for (a, u), (b, v) in pairwise(ordered):
            if a == b:
                model.add(u == v)
            else:
                model.add(v >= u + min(setup[p], b - a))
    model.minimize(sum(rate * duration for rate, duration, _ in durations))
    solver = cp_model.CpSolver()
    solver.parameters.num_search_workers = 1
    solver.parameters.random_seed = 7
    solver.parameters.max_time_in_seconds = seconds
    status = solver.solve(model)
    saving = 0.0
    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        saving = sum(
            rate * (old - solver.value(duration)) for rate, duration, old in durations
        )
    with atomic_output(output, "wb") as handle:
        if saving > 1e-7:
            for node, var in changes:
                node.text = str(solver.value(var))
            plan.write(handle, encoding="utf-8", xml_declaration=True)
        else:
            handle.write(Path(incumbent).read_bytes())
    return {
        "status": solver.status_name(status),
        "cost_saved": max(0.0, saving),
        "elapsed_s": round(time.monotonic() - started, 4),
    }


def solve(instance, output):
    """Solve an official input from scratch, publishing a plan after each stage."""
    instance, output = Path(instance), Path(output)
    if instance.resolve() == output.resolve():
        raise ValueError("Input and output paths must differ")

    def publish(candidate):
        with candidate.open("rb") as src, atomic_output(output, "wb") as dst:
            shutil.copyfileobj(src, dst)

    with tempfile.TemporaryDirectory() as tmp:
        candidate = Path(tmp) / "candidate.xml"
        if not search(instance, candidate, 150, 7, rotate=True, fleet_aware=True):
            print(json.dumps({"stage": "cp_sat_assignment"}), flush=True)
            if not assign_with_cp_sat(
                instance,
                candidate,
                seconds=150,
                step=720,
                fraction=0.8,
                seed=7,
                workers=1,
                max_stops=4,
                companions=True,
            ):
                raise RuntimeError(
                    "Neither constructor found a complete schedule within its budget"
                )
        publish(candidate)
        optimize_volumes(instance, output, candidate)
        publish(candidate)
        root = ET.parse(instance).getroot()
        horizon = int(root.findtext("horizon")) * int(root.findtext("unit"))
        if horizon >= 1440:
            optimize_routes(
                instance,
                [output],
                candidate,
                48,
                offsets=(-60, 60),
                cliques=True,
                window=(0, min(4, horizon // 1440)),
                extra_stops=4,
                replace_last=True,
            )
            publish(candidate)
        return retime(instance, output, output, 10)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("instance", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(solve(args.instance, args.output)), flush=True)
