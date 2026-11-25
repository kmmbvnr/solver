"""Read ITC event timetables and count student penalties."""

from functools import partial

import numpy as np

from demos.itc.timetable import Timetable, add_clique, day_delta


def event_cost(students, events, count, positions):
    busy = np.zeros((count, 45), dtype=bool)
    times = np.fromiter((time for time, _ in positions), dtype=int, count=len(positions))
    busy[students, times[events]] = True
    days = busy.reshape(-1, 5, 9)
    triples = days[:, :, :-2] & days[:, :, 1:-1] & days[:, :, 2:]
    return int(days[:, :, -1].sum() + (days.sum(axis=2) == 1).sum() + triples.sum())


def student_day_cost(slots):
    seen = repeated = triples = 0
    for i, busy in enumerate(slots):
        repeated |= seen & busy
        seen |= busy
        if i >= 2:
            triples += (busy & slots[i - 1] & slots[i - 2]).bit_count()
    return (seen ^ repeated).bit_count() + slots[-1].bit_count() + triples


def penalized_students(slots, offset):
    """Students paying a late, single-lecture or consecutive-lecture penalty here."""
    busy = slots[offset]
    if not busy or offset == 8:
        return busy
    others = 0
    for i, members in enumerate(slots):
        if i != offset:
            others |= members
    penalized = busy & ~others
    for start in range(max(0, offset - 2), min(offset, 6) + 1):
        penalized |= slots[start] & slots[start + 1] & slots[start + 2]
    return penalized


def penalty_event(state, rng):
    """Mix uniform moves with events sampled by affected student count."""
    if rng.randrange(2):
        slot = rng.randrange(45)
        start = slot - slot % 9
        penalized = penalized_students(state.members[start:start + 9], slot % 9)
        if penalized:
            draw = rng.randrange(penalized.bit_count())
            occupants = state.period[slot]
            while occupants:
                bit = occupants & -occupants
                occupants ^= bit
                event = bit.bit_length() - 1
                draw -= (state.problem.members[event] & penalized).bit_count()
                if draw < 0:
                    return event
    return rng.randrange(len(state.positions))


def event_delta(positions, state, previous):
    return day_delta(state, previous, 9, student_day_cost)


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
        members=[sum(1 << int(i) for i in np.flatnonzero(row)) for row in attendance.T],
        delta=event_delta,
    )


def write_events(path, positions):
    path.write_text("".join(f"{t} {r}\n" for t, r in positions))
