"""Read ITC event timetables and count student penalties."""

from bisect import bisect_right
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


def event_draw(state, slot):
    """Cache the weighted event draw while the day's event assignments match."""
    draws = getattr(state, "penalty_draws", None)
    if draws is None:
        state.penalty_draws = draws = [None] * 45
    start = slot - slot % 9
    day = state.period[start:start + 9]
    cached = draws[slot]
    if cached is not None and cached[0] == day:
        return cached[1], cached[2]

    students = penalized_students(state.members[start:start + 9], slot % 9)
    events, totals = [], []
    total = 0
    occupants = state.period[slot]
    while students and occupants:
        bit = occupants & -occupants
        occupants ^= bit
        event = bit.bit_length() - 1
        weight = (state.problem.members[event] & students).bit_count()
        if weight:
            total += weight
            events.append(event)
            totals.append(total)
    draws[slot] = day, events, totals
    return events, totals


def penalty_event(state, rng):
    """Mix uniform moves with events sampled by affected student count."""
    if rng.randrange(2):
        events, totals = event_draw(state, rng.randrange(45))
        if totals:
            return events[bisect_right(totals, rng.randrange(totals[-1]))]
    return rng.randrange(len(state.positions))


def displace_event(state, event, target, rng):
    """Move into a period, then rehome at most one displaced event."""
    p = state.problem
    source = state.positions[event][0]
    if source == target:
        return []
    clashes = state.period[target] & p.clashes[event]
    if clashes.bit_count() > 1:
        return []
    rooms = p.rooms[event]
    offset = rng.randrange(len(rooms))
    best = None
    for k in range(len(rooms)):
        room = rooms[(k + offset) % len(rooms)]
        blocked = clashes | state.rooms[target][room]
        if not blocked:
            return [(event, target, room)]
        if best is None and blocked.bit_count() == 1:
            best = room, blocked.bit_length() - 1
    if best is None:
        return []
    room, other = best
    ignored = (1 << event) | (1 << other)
    for trial in range(6):
        t = source if trial == 0 else rng.choice(p.periods[other])
        if t not in p.periods[other] or state.period[t] & p.clashes[other] & ~ignored:
            continue
        if t == target and clashes:
            continue
        alternatives = p.rooms[other]
        start = rng.randrange(len(alternatives))
        for k in range(len(alternatives)):
            r = alternatives[(start + k) % len(alternatives)]
            if (t, r) != (target, room) and not state.rooms[t][r] & ~ignored:
                return [(event, target, room), (other, t, r)]
    return []


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
        displacement_move=displace_event,
    )


def write_events(path, positions):
    path.write_text("".join(f"{t} {r}\n" for t, r in positions))
