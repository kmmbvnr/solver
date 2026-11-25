"""Read ITC event timetables and count student penalties."""

from functools import partial

import numpy as np

from demos.itc.timetable import Timetable, add_clique


def event_cost(students, events, count, positions):
    busy = np.zeros((count, 45), dtype=bool)
    times = np.fromiter((time for time, _ in positions), dtype=int, count=len(positions))
    busy[students, times[events]] = True
    days = busy.reshape(-1, 5, 9)
    triples = days[:, :, :-2] & days[:, :, 1:-1] & days[:, :, 2:]
    return int(days[:, :, -1].sum() + (days.sum(axis=2) == 1).sum() + triples.sum())


def read_events(path, post_enrolment):
    data = np.fromfile(path, dtype=int, sep=" ")
    events, rooms, features, students = map(int, data[:4])
    capacities = data[4 : 4 + rooms]
    data = data[4 + rooms :]
    attendance = data[: students * events].reshape(students, events).astype(bool)
    data = data[students * events :]
    equipped = data[: rooms * features].reshape(rooms, features)
    required = data[rooms * features : (rooms + events) * features].reshape(events, features)
    data = data[(rooms + events) * features :]
    sizes = attendance.sum(axis=0)
    allowed = [
        np.flatnonzero((capacities >= sizes[i]) & np.all(equipped >= required[i], axis=1)).tolist()
        for i in range(events)
    ]
    clashes = [0] * events
    for row in attendance:
        add_clique(clashes, np.flatnonzero(row))
    periods = [range(45)] * events
    relations = [[] for _ in range(events)]
    if post_enrolment:
        periods = [np.flatnonzero(row).tolist() for row in data[: events * 45].reshape(events, 45)]
        order = data[events * 45 :].reshape(events, events)
        for a, b in zip(*np.where(order == 1)):
            a, b = int(a), int(b)
            relations[a].append((b, "before"))
            relations[b].append((a, "after"))
    return Timetable(
        periods,
        allowed,
        clashes,
        [1] * rooms,
        [[1] * rooms] * events,
        relations,
        45,
        partial(event_cost, *np.nonzero(attendance), students),
    )


def write_events(path, positions):
    path.write_text("".join(f"{t} {r}\n" for t, r in positions))
