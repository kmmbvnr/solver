"""Build and improve a ROADEF inventory-routing schedule with one command."""

import argparse
import json
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
from shiftopt import run_pipeline
from route_search import RouteSearch
from roadef_route_pool import export, load_plans, optimize as optimize_routes
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


def pooled_routes(instance, work, left, right, deadline):
    paths = [work / "left.xml", work / "right.xml"]
    for path, parent in zip(paths, (left, right)):
        export(path, parent)
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        return None
    child = work / "pool.xml"
    optimize_routes(instance, paths, child, remaining, cliques=True)
    return load_plans([child])[0]


def solve(instance, output, *, route_mip=False, recombine_seconds=0):
    """Solve an official input from scratch, publishing a plan after each stage."""
    instance, output = Path(instance), Path(output)
    if instance.resolve() == output.resolve():
        raise ValueError("Input and output paths must differ")

    if recombine_seconds < 0:
        raise ValueError("recombination time must be nonnegative")
    problem = ET.parse(instance).getroot()
    routes = RouteSearch(problem)

    with tempfile.TemporaryDirectory() as tmp:
        candidate = Path(tmp) / "candidate.xml"
        def calendar(plan, deadline):
            seconds = min(150, deadline - time.monotonic())
            if search(instance, candidate, seconds, 7, rotate=True, fleet_aware=True):
                return load_plans([candidate])[0]
            return None

        def assignment_fallback(plan, deadline):
            if plan is not None:
                return None
            print(json.dumps({"stage": "cp_sat_assignment"}), flush=True)
            if not assign_with_cp_sat(instance, candidate, seconds=min(150, deadline - time.monotonic()),
                                      step=720, fraction=0.8, seed=7, workers=1,
                                      max_stops=4, companions=True):
                raise RuntimeError("Neither constructor found a complete schedule within its budget")
            return load_plans([candidate])[0]

        def volumes(plan, deadline):
            export(candidate, plan)
            optimize_volumes(instance, candidate, candidate)
            return load_plans([candidate])[0]

        def route_step(plan, deadline):
            if routes.horizon < 1440:
                return None
            limit = min(deadline, time.monotonic() + 48)
            if not route_mip:
                return routes.improve(plan, limit)
            export(candidate, plan)
            optimize_routes(instance, [candidate], candidate, min(48, deadline - time.monotonic()), offsets=(-60, 60),
                            cliques=True, window=(0, min(4, routes.horizon // 1440)),
                            extra_stops=4, replace_last=True)
            return load_plans([candidate])[0]

        timing = {}
        def timing_step(plan, deadline):
            export(candidate, plan)
            timing.update(retime(instance, candidate, candidate, min(10, deadline - time.monotonic())))
            return load_plans([candidate])[0]

        steps = [calendar, assignment_fallback, volumes, route_step, timing_step]
        if recombine_seconds > 0:
            def alternate_calendar(plan, deadline):
                if search(instance, candidate, min(8, deadline - time.monotonic()), 17,
                          rotate=True, fleet_aware=True):
                    return load_plans([candidate])[0]
                return None

            def mix_routes(plan, deadline):
                def assemble(left, right, limit):
                    return pooled_routes(instance, Path(tmp), left, right,
                                         min(limit, time.monotonic() + recombine_seconds))
                return run_pipeline([alternate_calendar], routes.score, initial=plan,
                                    seconds=max(0., deadline - time.monotonic()), recombine=assemble)

            steps.append(mix_routes)
        run_pipeline(steps, routes.score, on_accept=lambda plan: export(output, plan))
        return timing


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("instance", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--route-mip", action="store_true", help="use the benchmark mixed-integer route pool")
    parser.add_argument("--recombine-seconds", type=float, default=0, help="pool routes with a second calendar plan and set the pool solve budget")
    args = parser.parse_args()
    print(json.dumps(solve(args.instance, args.output, route_mip=args.route_mip, recombine_seconds=args.recombine_seconds)), flush=True)
