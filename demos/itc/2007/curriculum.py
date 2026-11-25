"""Read curriculum timetables and evaluate their four soft penalties."""

from collections import defaultdict
from functools import partial

from demos.itc.timetable import Timetable, add_clique


def curriculum_cost(courses, minimum, sizes, capacities, curricula, per_day, positions):
    days, rooms, busy = defaultdict(set), defaultdict(set), defaultdict(set)
    cost = 0
    for course, (slot, room) in zip(courses, positions):
        cost += max(0, sizes[course] - capacities[room])
        days[course].add(slot // per_day)
        rooms[course].add(room)
        for group in curricula[course]:
            busy[group, slot // per_day].add(slot % per_day)
    cost += sum(5 * max(0, minimum[c] - len(days[c])) + len(rooms[c]) - 1 for c in days)
    return cost + 2 * sum(
        t - 1 not in times and t + 1 not in times for times in busy.values() for t in times
    )


def read_curriculum(path):
    sections = defaultdict(list)
    headers = {}
    section = None
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line == "END.":
            continue
        if line.endswith(":"):
            section = line[:-1]
        elif section is None:
            k, v = line.split(":", 1)
            headers[k] = v.strip()
        else:
            sections[section].append(line.split())
    per_day = int(headers["Periods_per_day"])
    slots = int(headers["Days"]) * per_day
    curricula, groups, forbidden = defaultdict(list), defaultdict(list), defaultdict(set)
    for group, _, *members in sections["CURRICULA"]:
        for c in members:
            curricula[c].append(group)
    for c, d, t in sections["UNAVAILABILITY_CONSTRAINTS"]:
        forbidden[c].add(int(d) * per_day + int(t))
    courses, minimum, sizes = [], {}, {}
    for c, teacher, count, days, size in sections["COURSES"]:
        ids = range(len(courses), len(courses) + int(count))
        groups["teacher", teacher].extend(ids)
        for group in curricula[c]:
            groups["curriculum", group].extend(ids)
        courses.extend([c] * int(count))
        minimum[c], sizes[c] = int(days), int(size)
    clashes = [0] * len(courses)
    for members in groups.values():
        add_clique(clashes, members)
    room_names = [r for r, _ in sections["ROOMS"]]
    capacities = [int(cap) for _, cap in sections["ROOMS"]]
    n = len(room_names)
    cost = partial(curriculum_cost, courses, minimum, sizes, capacities, curricula, per_day)
    problem = Timetable(
        [[t for t in range(slots) if t not in forbidden[c]] for c in courses],
        [range(n)] * len(courses),
        clashes,
        [1] * n,
        [[1] * n] * len(courses),
        [[] for _ in courses],
        slots,
        cost,
    )
    return problem, partial(write_curriculum, courses, room_names, per_day)


def write_curriculum(courses, rooms, per_day, path, positions):
    path.write_text(
        "".join(
            f"{c} {rooms[r]} {t // per_day} {t % per_day}\n"
            for c, (t, r) in zip(courses, positions)
        )
    )
