"""Close three-event displacement chains on complete post-enrolment schedules."""
from operator import itemgetter
from sys import maxsize
from time import monotonic

from demos.itc.events import penalty_event
from demos.itc.timetable import Occupancy
from shiftopt import ejection_chain


class ThreeEventChains:
    """Keep occupancy for the incumbent and score only complete, feasible chains."""

    def __init__(self, problem, seed, *, attempts=maxsize):
        self.problem = problem
        self.base = None
        self.feasible = self.improved = 0
        self.search = ejection_chain(self.start, self.extend, self.close, itemgetter(0),
                                     max_depth=3, max_nodes=13, attempts=attempts, seed=seed)

    def __call__(self, plan, deadline):
        self.deadline = deadline
        return self.search(plan, deadline)

    def start(self, plan, rng):
        self.rng = rng
        if self.base is not plan[1]:
            self.base = plan[1]
            self.state = Occupancy(self.problem, self.base)
        return (), penalty_event(self.state, rng)

    def options(self, path, event, rng, deadline):
        """Propose new periods, ignoring vacated assignments of earlier events."""
        p = self.problem
        moved = sum(1 << i for i, _, _ in path)
        periods = list(p.periods[event])
        rng.shuffle(periods)
        rooms = list(p.rooms[event])
        rng.shuffle(rooms)
        for time in periods:
            if monotonic() >= deadline:
                return
            if time == self.base[event][0]:
                continue
            for room in rooms:
                if any(t == time and (r == room or p.clashes[event] & (1 << i))
                       for i, t, r in path):
                    continue
                blockers = self.state.blockers(event, time, room) & ~moved
                yield (event, time, room), blockers

    def extend(self, plan, chain, rng):
        path, event = chain
        seen = set()
        for placement, blockers in self.options(path, event, rng, self.deadline):
            if blockers.bit_count() != 1:
                continue
            key = placement[1], blockers
            if key in seen:
                continue
            seen.add(key)
            yield (*path, placement), blockers.bit_length() - 1
            if len(seen) == 3:
                return

    def close(self, plan, chain):
        path, event = chain
        if len(path) != 2:
            return None
        checked = set()
        for placement, blockers in self.options(path, event, self.rng, self.deadline):
            if blockers or placement[1] in checked:
                continue
            changes = [*path, placement]
            previous = self.state.apply(changes)
            if not previous:
                continue
            checked.add(placement[1])
            try:
                self.feasible += 1
                delta = self.problem.delta(self.base, self.state, previous)
                if delta < 0:
                    self.improved += 1
                    return plan[0] + delta, tuple(self.state.positions)
            finally:
                self.state.restore(previous)
        return None
