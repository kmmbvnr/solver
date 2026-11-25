"""Compare complete XHSTT schedules produced by diversified KHE constructions."""
import argparse
import os
import subprocess
from collections import defaultdict
from functools import partial
from operator import itemgetter
from pathlib import Path
from tempfile import TemporaryDirectory
from time import monotonic
from xml.etree import ElementTree as ET

from ortools.sat.python import cp_model

from shiftopt import run_pipeline


def construct(path, variant, incumbent, deadline):
    with TemporaryDirectory() as work:
        out = Path(work) / "result.xml"
        try:
            result = subprocess.run([os.environ["KHE_STEP"], path, out, str(variant)],
                                    capture_output=True, text=True, check=True,
                                    timeout=max(0, deadline - monotonic()))
        except subprocess.TimeoutExpired:
            return None
        hard, soft = map(int, result.stdout.splitlines()[-1].split()[1:])
        if hard:
            return None
        return soft, out.read_bytes()


def fixed_resources(path, prefer_pairs, seed, workers, incumbent, deadline):
    """Place fixed-resource lessons in single or double periods and verify with KHE."""
    tree = ET.parse(path)
    instance = tree.find("Instances/Instance")
    times = instance.findall("Times/Time")
    events = instance.findall("Events/Event")
    if any(t.find("Day") is None for t in times):
        return None
    days = [t.find("Day").get("Reference") for t in times]
    forbidden = defaultdict(set)
    for rule in instance.findall("Constraints/AvoidUnavailableTimesConstraint"):
        if rule.findtext("Required") == "true":
            for resource in rule.findall("AppliesTo/Resources/Resource"):
                forbidden[resource.get("Reference")].update(
                    t.get("Reference") for t in rule.findall("Times/Time"))
    model = cp_model.CpModel()
    occupied, choices = defaultdict(list), []
    doubles = []
    for event in events:
        resources = [r.get("Reference") for r in event.findall("Resources/Resource")]
        if None in resources or event.find("Time") is not None:
            return None
        duration = int(event.findtext("Duration"))
        pieces, by_day = [], defaultdict(list)
        for start, time in enumerate(times):
            for length in range(1, min(2, duration) + 1):
                stop = start + length
                if stop > len(times) or days[start] != days[stop - 1]:
                    continue
                if any(times[t].get("Id") in forbidden[r]
                       for t in range(start, stop) for r in resources):
                    continue
                x = model.new_bool_var("")
                pieces.append(length * x)
                by_day[days[start]].append(x)
                choices.append((event.get("Id"), time.get("Id"), length, x))
                for t in range(start, stop):
                    for resource in resources:
                        occupied[resource, t].append(x)
                if length == 2:
                    doubles.append(x)
        model.add(sum(pieces) == duration)
        for sessions in by_day.values():
            model.add_at_most_one(sessions)
    for sessions in occupied.values():
        model.add_at_most_one(sessions)
    if prefer_pairs:
        model.maximize(sum(doubles))
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = min(5, max(0, deadline - monotonic()))
    solver.parameters.num_search_workers = workers
    solver.parameters.random_seed = seed
    if solver.solve(model) not in (cp_model.FEASIBLE, cp_model.OPTIMAL):
        return None
    group = ET.SubElement(ET.SubElement(tree.getroot(), "SolutionGroups"),
                          "SolutionGroup", Id="ShiftOpt")
    meta = ET.SubElement(group, "MetaData")
    for key, value in (("Contributor", "ShiftOpt"), ("Date", "2026"),
                       ("Description", "Fixed-resource construction")):
        ET.SubElement(meta, key).text = value
    sol = ET.SubElement(group, "Solution", Reference=instance.get("Id"))
    assigned = ET.SubElement(sol, "Events")
    for event, time, length, x in choices:
        if solver.value(x):
            entry = ET.SubElement(assigned, "Event", Reference=event)
            ET.SubElement(entry, "Duration").text = str(length)
            ET.SubElement(entry, "Time", Reference=time)
    with TemporaryDirectory() as tmp:
        candidate = Path(tmp) / "schedule.xml"
        tree.write(candidate, encoding="utf-8")
        result = subprocess.run([os.environ["KHE_STEP"], candidate, candidate, "-1"],
                                check=True, capture_output=True, text=True)
        hard, soft = map(int, result.stdout.splitlines()[-1].split()[1:])
        if hard == 0:
            return soft, candidate.read_bytes()
    return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--variants", type=int, default=16)
    parser.add_argument("--seconds", type=float, default=60)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    root = ET.parse(args.input)
    for groups in root.findall("SolutionGroups"):
        root.getroot().remove(groups)
    with TemporaryDirectory() as tmp:
        path = Path(tmp) / "instance.xml"
        root.write(path, encoding="utf-8")
        steps = [partial(fixed_resources, path, pairs, args.seed, args.workers) for pairs in (False, True)]
        steps.extend(partial(construct, path, (args.seed + i) % 2147483647) for i in range(args.variants))
        plan = run_pipeline(steps, itemgetter(0), seconds=args.seconds)
    if plan is None:
        parser.exit(1, "No schedule with zero hard cost found within the budget.\n")
    # KHE can change resource group references when it serializes the instance.
    root.getroot().append(ET.fromstring(plan[1]).find("SolutionGroups"))
    root.write(args.output, encoding="utf-8", xml_declaration=True)
    print(plan[0])


if __name__ == "__main__":
    main()
