"""Room and period assignments shared by the 2002 and 2007 demos."""

from collections.abc import Callable
from dataclasses import dataclass
from itertools import combinations
from random import Random
from time import monotonic


@dataclass
class Timetable:
    periods: list
    rooms: list
    clashes: list
    capacity: list
    demand: list
    relations: list
    slots: int
    objective: Callable
    exclusive: int = 0
    members: list | None = None
    delta: Callable | None = None
    compact_move: Callable | None = None


class TimetableMoves:
    """Reuse occupancy across accepted moves and undo rejected proposals."""

    operators = ("chain", "room", "swap", "time", "relocate")

    def __init__(self, problem, operators=operators, *, select_event=None):
        self.select_event = select_event
        self.operators = tuple(operators)
        available = set(TimetableMoves.operators)
        if problem.compact_move is not None:
            available.add("compact")
        if not self.operators or not set(self.operators) <= available:
            raise ValueError("choose at least one known timetable move")
        self.problem = problem
        self.base = self.candidate = self.state = None
        self.undo = []

    def __call__(self, plan, rng, deadline):
        problem = self.problem
        positions = plan[1]
        if positions is self.base and self.undo:
            self.state.restore(self.undo)
        elif positions is not self.candidate:
            self.state = Occupancy(problem, positions)
        self.base, self.candidate, self.undo = positions, None, []
        for _ in range(12):
            event = (rng.randrange(len(positions)) if self.select_event is None
                     else self.select_event(self.state, rng))
            time, room = positions[event]
            kind = rng.choice(self.operators)
            target = rng.choice(problem.periods[event])
            if kind == "compact":
                changes = problem.compact_move(self.state, rng, deadline)
                if not changes and self.operators == ("compact",):
                    return None
            elif kind == "chain":
                changes = self.state.period_chain(event, target) if target != time else []
            elif kind == "room":
                changes = [(event, time, rng.choice(problem.rooms[event]))]
            elif kind == "swap":
                other = rng.randrange(len(positions))
                t, r = positions[other]
                if (
                    event == other
                    or t not in problem.periods[event]
                    or time not in problem.periods[other]
                    or r not in problem.rooms[event]
                    or room not in problem.rooms[other]
                ):
                    continue
                changes = [(event, t, r), (other, time, room)]
            else:
                changes = [
                    (event, target, room if kind == "time" else rng.choice(problem.rooms[event]))
                ]
            if changes:
                self.undo = self.state.apply(changes)
                if self.undo:
                    self.candidate = tuple(self.state.positions)
                    if problem.delta is None:
                        cost = problem.objective(self.candidate)
                    else:
                        cost = plan[0] + problem.delta(positions, self.state, self.undo)
                    return cost, self.candidate
        return None


class Occupancy:
    def __init__(self, problem, positions):
        self.problem = problem
        self.positions = [None] * len(problem.periods)
        self.members = [0] * problem.slots
        self.period = [0] * problem.slots
        self.rooms = [[0] * len(problem.capacity) for _ in self.period]
        self.used = [[0] * len(problem.capacity) for _ in self.period]
        for event, position in enumerate(positions):
            self.place(event, *position)

    def period_chain(self, event, target):
        """Exchange a connected component of clashes between two periods."""
        source = self.positions[event][0]
        pending = 1 << event
        seen = pending
        changes = []
        while pending:
            bit = pending & -pending
            pending ^= bit
            i = bit.bit_length() - 1
            time, room = self.positions[i]
            other = target if time == source else source
            if other not in self.problem.periods[i]:
                return []
            changes.append((i, other, room))
            linked = (
                (self.problem.clashes[i] & self.period[other]) | self.rooms[other][room]
            ) & ~seen
            pending |= linked
            seen |= linked
        return changes

    def apply(self, changes):
        previous = [(i, *self.positions[i]) for i, _, _ in changes]
        if previous == changes:
            return []
        for i, _, _ in previous:
            self.remove(i)
        for count, (i, time, room) in enumerate(changes):
            if self.blockers(i, time, room):
                for j, _, _ in changes[:count]:
                    self.remove(j)
                for entry in previous:
                    self.place(*entry)
                return []
            self.place(i, time, room)
        return previous

    def restore(self, previous):
        for i, _, _ in previous:
            self.remove(i)
        for entry in previous:
            self.place(*entry)

    def place(self, event, time, room):
        self.positions[event] = (time, room)
        if self.problem.members is not None:
            self.members[time] |= self.problem.members[event]
        self.period[time] |= 1 << event
        self.rooms[time][room] |= 1 << event
        self.used[time][room] += self.problem.demand[event][room]

    def remove(self, event):
        time, room = self.positions[event]
        self.positions[event] = None
        if self.problem.members is not None:
            self.members[time] ^= self.problem.members[event]
        self.period[time] ^= 1 << event
        self.rooms[time][room] ^= 1 << event
        self.used[time][room] -= self.problem.demand[event][room]

    def blockers(self, event, time, room):
        p = self.problem
        conflicts = self.period[time] & p.clashes[event]
        occupied = self.rooms[time][room]
        if p.exclusive & (1 << event):
            conflicts |= occupied
        else:
            conflicts |= occupied & p.exclusive
        if self.used[time][room] + p.demand[event][room] > p.capacity[room]:
            conflicts |= self.rooms[time][room]
        for other, relation in p.relations[event]:
            placed = self.positions[other]
            if placed is None:
                continue
            other_time = placed[0]
            if (
                (relation == "before" and time >= other_time)
                or (relation == "after" and time <= other_time)
                or (relation == "same" and time != other_time)
            ):
                conflicts |= 1 << other
        return conflicts


def add_clique(clashes, group):
    group = list(group)
    mask = sum(1 << int(event) for event in group)
    for event in group:
        clashes[event] |= mask ^ (1 << int(event))


def construct(problem, seed, seconds, incumbent, deadline):
    """Insert difficult events first and reinsert events displaced by conflicts."""
    if any(not times or not rooms for times, rooms in zip(problem.periods, problem.rooms)):
        return None
    rng = Random(seed)
    stop = min(deadline, monotonic() + seconds)
    n = len(problem.periods)
    difficulty = [
        problem.clashes[i].bit_count() / (len(problem.periods[i]) * len(problem.rooms[i]))
        for i in range(n)
    ]
    while monotonic() < stop:
        state = Occupancy(problem, ())
        pending = sorted(range(n), key=lambda i: difficulty[i] * rng.uniform(0.8, 1.2))
        for _ in range(n * 8):
            if monotonic() >= stop:
                return None
            event = pending.pop()
            best = None
            best_count = n + 1
            times = list(problem.periods[event])
            rooms = list(problem.rooms[event])
            rng.shuffle(times)
            rng.shuffle(rooms)
            for time in times:
                for room in rooms:
                    blocked = state.blockers(event, time, room)
                    count = blocked.bit_count()
                    if count < best_count:
                        best = time, room, blocked
                        best_count = count
                    if count == 0:
                        break
                if best_count == 0:
                    break
            time, room, blocked = best
            while blocked:
                bit = blocked & -blocked
                other = bit.bit_length() - 1
                state.remove(other)
                pending.insert(rng.randrange(len(pending) + 1), other)
                blocked ^= bit
            state.place(event, time, room)
            if not pending:
                positions = tuple(state.positions)
                return problem.objective(positions), positions
    return None


def exchange_labels(problem, axis, incumbent, deadline):
    """Polish interchangeable periods (2002) or room labels (curriculum)."""
    if incumbent is None:
        return None
    best, positions = incumbent
    count = problem.slots if axis == 0 else len(problem.capacity)
    for a, b in combinations(range(count), 2):
        if monotonic() >= deadline:
            break
        swap = {a: b, b: a}
        if axis == 0:
            candidate = tuple((swap.get(t, t), r) for t, r in positions)
        else:
            candidate = tuple((t, swap.get(r, r)) for t, r in positions)
        cost = problem.objective(candidate)
        if cost < best:
            best, positions = cost, candidate
    return best, positions


def day_delta(state, previous, per_day, day_cost):
    """Score affected days using student or curriculum occupancy bitsets."""
    toggles = {}
    for event, old, _ in previous:
        new = state.positions[event][0]
        if old != new:
            mask = state.problem.members[event]
            for slot in (old, new):
                toggles[slot] = toggles.get(slot, 0) ^ mask
    delta = 0
    for day in {slot // per_day for slot in toggles}:
        start = day * per_day
        after = state.members[start : start + per_day]
        before = [mask ^ toggles.get(start + i, 0) for i, mask in enumerate(after)]
        delta += day_cost(after) - day_cost(before)
    return delta
