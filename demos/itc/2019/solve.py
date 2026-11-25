"""Construct a university timetable and exchange whole-course student assignments."""
import argparse
import os
import subprocess
from collections import defaultdict
from functools import partial
from itertools import combinations
from operator import itemgetter
from pathlib import Path
from tempfile import TemporaryDirectory
from time import monotonic
from xml.etree import ElementTree as ET

from shiftopt import run_pipeline


def construct(path, warm_start, seconds, incumbent, deadline):
    libs = Path(os.environ["ITC2019_LIB"]).resolve()
    with TemporaryDirectory() as tmp:
        output = Path(tmp) / "plan.xml"
        args = ["dotnet", "fsi", "--nologo",
                *[f"--reference:{libs}/Timetabling.{lib}.dll" for lib in ("Internal", "Common")],
                str(Path(__file__).with_name("construct.fsx").resolve()),
                str(path.resolve()), str(output), str(seconds), "1"]
        if warm_start:
            args.append(str(warm_start.resolve()))
        try:
            result = subprocess.run(args, cwd=tmp, check=True, stdout=subprocess.PIPE,
                                    text=True, timeout=max(0, deadline - monotonic()))
        except subprocess.TimeoutExpired:
            return None
        if output.exists():
            return int(result.stdout.split("COST ")[-1]), output.read_bytes()
    return None


def clash(a, b, travel):
    days, weeks, start, end, room = a
    days2, weeks2, start2, end2, room2 = b
    gap = travel.get((room, room2), 0)
    return bool(days & days2 and weeks & weeks2 and start < end2 + gap and start2 < end + gap)


def exchange_enrollments(problem, incumbent, deadline):
    if incumbent is None:
        return None
    cost, xml = incumbent
    solution = ET.fromstring(xml)
    travel = {}
    for room in problem.findall("rooms/room"):
        for trip in room.findall("travel"):
            a, b = room.get("id"), trip.get("room")
            travel[a, b] = travel[b, a] = int(trip.get("value"))
    domains = {c.get("id"): c for c in problem.findall(".//subpart/class")}
    by_course = defaultdict(lambda: defaultdict(set))
    course_of = {c.get("id"): course.get("id") for course in problem.findall("courses/course")
                 for c in course.findall(".//subpart/class")}
    slots, classes = {}, defaultdict(set)
    for entry in solution.findall("class"):
        cid = entry.get("id")
        time = next(t for t in domains[cid].findall("time")
                    if all(t.get(key) == entry.get(key) for key in ("days", "weeks", "start")))
        start = int(time.get("start"))
        slots[cid] = (int(time.get("days"), 2), int(time.get("weeks"), 2), start,
                      start + int(time.get("length")), entry.get("room"))
        for student in entry.findall("student"):
            sid = student.get("id")
            classes[sid].add(cid)
            by_course[course_of[cid]][sid].add(cid)
    weight = int(problem.find("optimization").get("student"))
    for assignments in by_course.values():
        for a, b in combinations(assignments, 2):
            if monotonic() >= deadline:
                break
            left, right = assignments[a], assignments[b]
            if left == right:
                continue
            outside_a, outside_b = classes[a] - left, classes[b] - right
            delta = sum(count_cross(x, y, slots, travel) for x, y in
                        ((left, outside_b), (right, outside_a)))
            delta -= count_cross(left, outside_a, slots, travel) + count_cross(right, outside_b, slots, travel)
            if delta < 0:
                assignments[a], assignments[b] = right, left
                classes[a], classes[b] = outside_a | right, outside_b | left
                cost += delta * weight
    for entry in solution.findall("class"):
        for student in entry.findall("student"):
            entry.remove(student)
        for sid, enrolled in classes.items():
            if entry.get("id") in enrolled:
                ET.SubElement(entry, "student", id=sid)
    return cost, ET.tostring(solution, encoding="utf-8")


def exchange_rooms(problem, incumbent, deadline):
    """Swap two equivalent room labels, preserving all clashes and travel times."""
    if incumbent is None:
        return None
    cost, xml = incumbent
    solution = ET.fromstring(xml)
    rooms = {r.get("id"): r for r in problem.findall("rooms/room")}
    travel = {}
    for a, room in rooms.items():
        for trip in room.findall("travel"):
            b = trip.get("room")
            travel[a, b] = travel[b, a] = int(trip.get("value"))
    attributes = {key: (room.get("capacity"), sorted(tuple(sorted(u.attrib.items()))
                                                     for u in room.findall("unavailable")))
                  for key, room in rooms.items()}
    domains = {c.get("id"): {r.get("id"): int(r.get("penalty")) for r in c.findall("room")}
               for c in problem.findall(".//subpart/class")}
    by_room = defaultdict(list)
    for entry in solution.findall("class"):
        by_room[entry.get("room")].append(entry)
    for a, b in combinations(rooms, 2):
        if monotonic() >= deadline:
            break
        if attributes[a] != attributes[b] or any(
            travel.get((a, r), 0) != travel.get((b, r), 0) for r in rooms if r not in (a, b)
        ):
            continue
        changes = [(c, b) for c in by_room[a]] + [(c, a) for c in by_room[b]]
        if any(target not in domains[c.get("id")] for c, target in changes):
            continue
        delta = sum(domains[c.get("id")][target] - domains[c.get("id")][c.get("room")]
                    for c, target in changes)
        if delta < 0:
            cost += delta * int(problem.find("optimization").get("room"))
            for c, target in changes:
                c.set("room", target)
            by_room[a], by_room[b] = by_room[b], by_room[a]
    return cost, ET.tostring(solution, encoding="utf-8")


def count_cross(left, right, slots, travel):
    return sum(clash(slots[a], slots[b], travel) for a in left for b in right)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--warm-start", type=Path, help="initialize room and time assignments from XML")
    parser.add_argument("--seconds", type=int, default=90)
    args = parser.parse_args()
    problem = ET.parse(args.input)
    steps = [partial(construct, args.input, args.warm_start, max(1, args.seconds * 2 // 3)),
             partial(exchange_rooms, problem), partial(exchange_enrollments, problem)]
    plan = run_pipeline(steps, itemgetter(0), seconds=args.seconds)
    if plan is None:
        parser.exit(1, "No complete feasible timetable found within the budget.\n")
    args.output.write_bytes(plan[1])
    print(plan[0])


if __name__ == "__main__":
    main()
