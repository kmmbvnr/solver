"""Temporarily release rooms while exchanging post-enrolment events."""

from functools import partial
from operator import itemgetter
from time import monotonic

import numpy as np
from scipy.optimize import linear_sum_assignment

from shiftopt import neighborhood_search


def release_rooms(problem, plan, rng):
    """Exchange a student-conflict component and release rooms in both periods."""
    positions = plan[1]
    event = rng.randrange(len(positions))
    source = positions[event][0]
    target = rng.choice(problem.periods[event])
    if source == target:
        return None
    affected = [i for i, (t, _) in enumerate(positions) if t in (source, target)]
    masks = {source: 0, target: 0}
    for i in affected:
        masks[positions[i][0]] |= 1 << i
    pending = moved = 1 << event
    changes = {}
    while pending:
        bit = pending & -pending
        pending ^= bit
        i = bit.bit_length() - 1
        new = target if positions[i][0] == source else source
        if new not in problem.periods[i]:
            return None
        changes[i] = new
        linked = problem.clashes[i] & masks[new] & ~moved
        pending |= linked
        moved |= linked
    for i, new in changes.items():
        for other, relation in problem.relations[i]:
            time = changes.get(other, positions[other][0])
            if (relation == "before" and new >= time) or (relation == "after" and new <= time):
                return None
    groups = {source: [], target: []}
    for i in affected:
        groups[changes.get(i, positions[i][0])].append(i)
    return positions, groups


def assign_rooms(problem, costs, partial_plan, rng, deadline):
    """Match each period's events to distinct eligible rooms or discard the move."""
    if partial_plan is None:
        return None
    positions, groups = partial_plan
    result = list(positions)
    for time, events in groups.items():
        if len(events) > len(problem.capacity) or monotonic() >= deadline:
            return None
        if not events:
            continue
        try:
            _, rooms = linear_sum_assignment(costs[events])
        except ValueError:  # No complete matching with finite costs.
            return None
        for event, room in zip(events, rooms):
            result[event] = time, int(room)
    positions = tuple(result)
    return problem.objective(positions), positions


def room_repair(problem, *, attempts, seed):
    """Build a pipeline step for single-event rooms in post-enrolment timetables."""
    costs = np.full((len(problem.rooms), len(problem.capacity)), np.inf)
    for i, rooms in enumerate(problem.rooms):
        costs[i, rooms] = 0
    return neighborhood_search(partial(release_rooms, problem), partial(assign_rooms, problem, costs),
                               itemgetter(0), attempts=attempts, seed=seed, temperature=2)
