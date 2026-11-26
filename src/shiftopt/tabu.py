"""Construct a conflict-free assignment of items to ordered slots and exclusive resources."""
from functools import partial
from math import isfinite
from operator import index
from time import monotonic

import numpy as np


def _domains(choices):
    rows = [tuple(dict.fromkeys(map(index, row))) for row in choices]
    labels = sorted({v for row in rows for v in row})
    indices = {v: i for i, v in enumerate(labels)}
    return labels, [[indices[v] for v in row] for row in rows]


def _neighbors(count, pairs, directed):
    forward = [set() for _ in range(count)]
    backward = [set() for _ in range(count)] if directed else forward
    for a, b in pairs:
        if not (0 <= a < count and 0 <= b < count):
            raise ValueError("constraint endpoint outside the item range")
        forward[a].add(b)
        backward[b].add(a)
    return [[np.array(sorted(row), dtype=int) for row in group] for group in (forward, backward)]


def tabu_assignment(periods, resources, clashes, precedences=(), *, seed=0):
    """Return a construction step for (period, resource) assignments.

    Each item has independent integer period and resource domains. A resource
    holds one item per period. Clashing pairs need different periods, and the
    first item of each precedence pair must occur strictly before the second.
    The step needs a finite deadline and returns only complete feasible tuples.
    """
    slots, times = _domains(periods)
    rooms, choices = _domains(resources)
    if len(times) != len(choices):
        raise ValueError("expected one resource domain per item")
    adjacent, _ = _neighbors(len(times), clashes, False)
    successors, predecessors = _neighbors(len(times), precedences, True)
    return partial(_search, slots, rooms, times, choices, adjacent, successors, predecessors, seed)


def _search(slots, rooms, times, choices, adjacent, successors, predecessors, seed, incumbent, deadline):
    if incumbent is not None:
        return incumbent
    if not isfinite(deadline):
        raise ValueError("tabu assignment requires a finite deadline")
    if not times:
        return ()
    if any(not ts or not rs for ts, rs in zip(times, choices)):
        return None
    if any(i in row for graph in (adjacent, successors) for i, row in enumerate(graph)):
        return None
    rng = np.random.default_rng(seed % (1 << 64))
    allowed = np.zeros((len(times), len(slots), len(rooms)), dtype=bool)
    for i, (ts, rs) in enumerate(zip(times, choices)):
        allowed[i][np.ix_(ts, rs)] = True
    while monotonic() < deadline:
        ts = np.array([rng.choice(row) for row in times])
        rs = np.array([rng.choice(row) for row in choices])
        if _walk(ts, rs, allowed, adjacent, successors, predecessors, rng, deadline):
            return tuple((slots[t], rooms[r]) for t, r in zip(ts, rs))
    return None


class _Penalties:
    def __init__(self, adjacent, successors, predecessors, shape):
        self.adjacent = adjacent
        self.successors = successors
        self.predecessors = predecessors
        # Store extra weights only for pairs penalized during this restart.
        self.extra_clash = [{} for _ in adjacent]
        self.extra_before = [{} for _ in adjacent]
        self.extra_after = [{} for _ in adjacent]
        self.room = np.ones(shape, dtype=np.int32)

    def update(self, costs, item, period, amount):
        """Adjust the other items' costs when placing or removing an item."""
        costs[self.adjacent[item], period] += amount
        if self.successors[item].size:
            costs[self.successors[item], :period + 1] += amount
        if self.predecessors[item].size:
            costs[self.predecessors[item], period:] += amount
        for j, extra in self.extra_clash[item].items():
            costs[j, period] += amount * extra
        for j, extra in self.extra_before[item].items():
            costs[j, :period + 1] += amount * extra
        for j, extra in self.extra_after[item].items():
            costs[j, period:] += amount * extra

    def raise_violated(self, costs, ts, occupancy, bad):
        for i in bad:
            t = ts[i]
            neighbors = self.adjacent[i]
            for j in neighbors[(neighbors > i) & (ts[neighbors] == t)]:
                extra = self.extra_clash[i].get(j, 0) + 1
                self.extra_clash[i][j] = self.extra_clash[j][i] = extra
                costs[i, t] += 1
                costs[j, t] += 1
            for j in self.successors[i]:
                if t >= ts[j]:
                    extra = self.extra_before[i].get(j, 0) + 1
                    self.extra_before[i][j] = self.extra_after[j][i] = extra
                    costs[i, ts[j]:] += 1
                    costs[j, :t + 1] += 1
        self.room[occupancy > 1] += 1


def _walk(ts, rs, allowed, adjacent, successors, predecessors, rng, deadline):
    n, periods, resources = allowed.shape
    items = np.arange(n)
    costs = np.zeros((n, periods), dtype=np.int32)
    occupancy = np.zeros((periods, resources), dtype=np.int32)
    np.add.at(occupancy, (ts, rs), 1)
    penalties = _Penalties(adjacent, successors, predecessors, occupancy.shape)
    for i, t in enumerate(ts):
        penalties.update(costs, i, t, 1)
    tabu_time = np.zeros_like(costs)
    tabu_place = np.zeros(allowed.shape, dtype=np.int32)
    best = float("inf")
    last_improvement = iteration = 0
    while iteration < 50000 and monotonic() < deadline:
        iteration += 1
        current = costs[items, ts] + (occupancy[ts, rs] - 1) * penalties.room[ts, rs]
        total = int(current.sum()) // 2  # Each conflicting pair is counted at both ends.
        if total == 0:
            return True
        if total < best:
            best, last_improvement = total, iteration
        bad = np.flatnonzero(current)
        if iteration - last_improvement > 120:
            penalties.raise_violated(costs, ts, occupancy, bad)
            best = float("inf")  # Compare subsequent moves on the new cost scale.
            continue
        old_times, old_rooms = ts[bad], rs[bad]
        delta = costs[bad, :, None] + occupancy * penalties.room - current[bad, None, None]
        valid = allowed[bad]
        # A room-only change must reduce crowding at the current time.
        valid[np.arange(len(bad)), old_times] &= occupancy[old_times] < occupancy[old_times, old_rooms, None] - 1
        valid &= ((tabu_time[bad, :, None] <= iteration) & (tabu_place[bad] <= iteration)) | (total + delta < best)
        delta[~valid] = np.iinfo(delta.dtype).max
        minimum = delta.min()
        if minimum == np.iinfo(delta.dtype).max:
            continue
        pick = rng.choice(np.flatnonzero(delta == minimum))
        row, t, r = np.unravel_index(pick, delta.shape)
        i = bad[row]
        old_t, old_r = ts[i], rs[i]
        expires = iteration + 1 + rng.integers(10) + len(bad) // 2
        if t != old_t:
            tabu_time[i, old_t] = expires
            penalties.update(costs, i, old_t, -1)
            penalties.update(costs, i, t, 1)
        tabu_place[i, old_t, old_r] = expires
        occupancy[old_t, old_r] -= 1
        occupancy[t, r] += 1
        ts[i], rs[i] = t, r
    return False
