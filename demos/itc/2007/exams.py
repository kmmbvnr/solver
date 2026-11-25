"""ITC examination conflicts, shared rooms and institutional penalties."""

from collections import Counter, defaultdict
from functools import partial
from itertools import combinations

import numpy as np

from demos.itc.timetable import Timetable, add_clique


def exam_cost(days, periods, rooms, durations, pairs, weights, large, positions):
    time, room = np.asarray(positions).T
    a, b, students = pairs
    gap = np.abs(time[a] - time[b])
    same_day = days[time[a]] == days[time[b]]
    row, day = weights["TWOINAROW"][0], weights["TWOINADAY"][0]
    pair_cost = np.where(same_day, np.where(gap == 1, row, day), 0)
    pair_cost += gap <= weights["PERIODSPREAD"][0]
    mixed = defaultdict(set)
    for place, duration in zip(positions, durations):
        mixed[place].add(duration)
    _, last, front_cost = weights["FRONTLOAD"]
    return int(
        periods[time].sum()
        + rooms[room].sum()
        + students @ pair_cost
        + weights["NONMIXEDDURATIONS"][0] * sum(len(d) - 1 for d in mixed.values())
        + front_cost * np.count_nonzero(time[large] >= len(periods) - last)
    )


def read_exam(path):
    sections = defaultdict(list)
    for line in path.read_text().splitlines():
        if line.startswith("["):
            section = line.strip("[]").split(":")[0]
        elif line.strip():
            sections[section].append([x.strip() for x in line.split(",")])
    exams = [list(map(int, row)) for row in sections["Exams"]]
    periods = sections["Periods"]
    rooms = [list(map(int, row)) for row in sections["Rooms"]]
    sizes = [len(e) - 1 for e in exams]
    durations = [e[0] for e in exams]
    students = defaultdict(list)
    for i, exam in enumerate(exams):
        for student in exam[1:]:
            students[student].append(i)
    clashes = [0] * len(exams)
    joint = Counter()
    for enrolled in students.values():
        add_clique(clashes, enrolled)
        joint.update(combinations(enrolled, 2))
    relations = [[] for _ in exams]
    for a, mode, b in sections["PeriodHardConstraints"]:
        a, b = int(a), int(b)
        if mode == "AFTER":
            relations[a].append((b, "after"))
            relations[b].append((a, "before"))
        elif mode == "EXCLUSION":
            add_clique(clashes, [a, b])
        elif mode == "EXAM_COINCIDENCE":
            if not joint[min(a, b), max(a, b)]:
                relations[a].append((b, "same"))
                relations[b].append((a, "same"))
        else:
            raise ValueError(f"Unknown period constraint {mode}")
    exclusive = sum(
        1 << int(e) for e, mode in sections["RoomHardConstraints"] if mode == "ROOM_EXCLUSIVE"
    )
    weights = {k: list(map(int, values)) for k, *values in sections["InstitutionalWeightings"]}
    pairs = np.array([(a, b, w) for (a, b), w in joint.items()], dtype=int).reshape(-1, 3).T
    large = sorted(range(len(exams)), key=lambda i: -sizes[i])[: weights["FRONTLOAD"][0]]
    cost = partial(
        exam_cost,
        np.array([p[0] for p in periods]),
        np.array([int(p[3]) for p in periods]),
        np.array([r[1] for r in rooms]),
        durations,
        pairs,
        weights,
        large,
    )
    return Timetable(
        [[t for t, p in enumerate(periods) if int(p[2]) >= d] for d in durations],
        [[r for r, (cap, _) in enumerate(rooms) if cap >= n] for n in sizes],
        clashes,
        [r[0] for r in rooms],
        [[n] * len(rooms) for n in sizes],
        relations,
        len(periods),
        cost,
        exclusive,
    )


def write_exam(path, positions):
    path.write_text("".join(f"{t}, {r}\n" for t, r in positions))
