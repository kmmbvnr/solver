"""Read curriculum timetables and evaluate their four soft penalties."""

from collections import defaultdict
from functools import partial
from time import monotonic

from demos.itc.timetable import Timetable, add_clique, day_delta


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


def isolated_cost(slots):
    padded = [0, *slots, 0]
    return 2 * sum(
        (current & ~(left | right)).bit_count()
        for left, current, right in zip(padded, padded[1:], padded[2:])
    )


def curriculum_delta(courses, lectures, minimum, sizes, caps, per_day, old, state, previous):
    new = state.positions
    change = day_delta(state, previous, per_day, isolated_cost)
    for i, _, old_room in previous:
        size = sizes[courses[i]]
        change += max(0, size - caps[new[i][1]]) - max(0, size - caps[old_room])
    for course in {courses[i] for i, _, _ in previous}:
        for positions, sign in ((old, -1), (new, 1)):
            times, rooms = zip(*(positions[i] for i in lectures[course]))
            days = len({t // per_day for t in times})
            change += sign * (5 * max(0, minimum[course] - days) + len(set(rooms)))
    return change


def adjacent_groups(state, slot, per_day, exclude=-1):
    result = 0
    for neighbor in (slot - 1, slot + 1):
        if neighbor != exclude and neighbor // per_day == slot // per_day:
            result |= state.members[neighbor]
    return result


def compact_move(per_day, state, rng, deadline):
    """Move an isolated lecture next to another lecture in its curriculum."""
    problem = state.problem
    start = rng.randrange(problem.slots)
    for offset in range(problem.slots):
        if monotonic() >= deadline:
            break
        source = (start + offset) % problem.slots
        isolated = state.members[source] & ~adjacent_groups(state, source, per_day)
        if not isolated:
            continue
        events = state.period[source]
        while events:
            bit = events & -events
            events ^= bit
            i = bit.bit_length() - 1
            groups = isolated & problem.members[i]
            if not groups:
                continue
            targets = [
                t
                for t in problem.periods[i]
                if t != source and groups & adjacent_groups(state, t, per_day, exclude=source)
            ]
            rng.shuffle(targets)
            for target in targets:
                old_room = state.positions[i][1]
                rooms = sorted(problem.rooms[i], key=lambda r: r != old_room)
                for room in rooms:
                    if not state.blockers(i, target, room):
                        return [(i, target, room)]
    return []


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
    lectures = defaultdict(list)
    for i, course in enumerate(courses):
        lectures[course].append(i)
    group_bits = {name: 1 << i for i, (name, *_) in enumerate(sections["CURRICULA"])}
    members = [sum(group_bits[g] for g in curricula[c]) for c in courses]
    problem = Timetable(
        [[t for t in range(slots) if t not in forbidden[c]] for c in courses],
        [range(n)] * len(courses),
        clashes,
        [1] * n,
        [[1] * n] * len(courses),
        [[] for _ in courses],
        slots,
        cost,
        members=members,
        compact_move=partial(compact_move, per_day),
        delta=partial(curriculum_delta, courses, lectures, minimum, sizes, capacities, per_day),
    )
    return problem, partial(write_curriculum, courses, room_names, per_day)


def write_curriculum(courses, rooms, per_day, path, positions):
    path.write_text(
        "".join(
            f"{c} {rooms[r]} {t // per_day} {t % per_day}\n"
            for c, (t, r) in zip(courses, positions)
        )
    )
