"""Construct a complete assignment by reinserting displaced items."""
from functools import partial
from math import inf, isfinite
from random import Random
from time import monotonic


def assignment_constructor(start, *, moves_per_start, starts=1, seed=0, conflict_weight=0):
    """Build a pipeline step. Each start(rng) returns a fresh state and pending list.

    Items are nonnegative integer indices. The step pops pending items from the
    end. state.options(item, rng) yields (hashable choice, blocker bit mask) in
    tie-breaking order. Removing every blocker makes that choice feasible.
    state.remove(item), state.assign(item, choice) and state.finish() implement
    domain updates and export. Only a completed state reaches finish().

    Rank each choice by blocker count plus conflict_weight times the previous
    evictions of those blockers by that (item, choice). Memory lasts one step
    invocation, including restarts. Unlimited starts require a finite deadline.
    """
    if type(moves_per_start) is not int or moves_per_start < 1:
        raise ValueError("moves_per_start must be positive")
    if starts is not None and (type(starts) is not int or starts < 1):
        raise ValueError("starts must be positive or None")
    if not isfinite(conflict_weight) or conflict_weight < 0:
        raise ValueError("conflict_weight must be finite and nonnegative")
    return partial(_construct, start, moves_per_start, starts, seed, conflict_weight)


def _construct(start, moves, starts, seed, weight, incumbent, deadline):
    if starts is None and not isfinite(deadline):
        raise ValueError("unlimited starts require a finite deadline")
    rng = Random(seed)
    history = {}
    trials = 0
    while (starts is None or trials < starts) and monotonic() < deadline:
        trials += 1
        state, pending = start(rng)
        if not pending:
            return state.finish()
        for _ in range(moves):
            if monotonic() >= deadline:
                return None
            item = pending.pop()
            best_cost = inf
            for i, (choice, mask) in enumerate(state.options(item, rng)):
                if i % 256 == 0 and monotonic() >= deadline:
                    return None
                cost = mask.bit_count()
                if cost >= best_cost:
                    continue
                if weight and mask:
                    past = history.get((item, choice))
                    if past:
                        remaining = mask
                        while remaining:
                            bit = remaining & -remaining
                            cost += weight * past.get(bit, 0)
                            remaining ^= bit
                if cost < best_cost:
                    best_cost, selected, blocked = cost, choice, mask
                    if not cost:
                        break
            if best_cost == inf:
                break
            if weight and blocked:
                past = history.setdefault((item, selected), {})
            while blocked:
                bit = blocked & -blocked
                blocked ^= bit
                other = bit.bit_length() - 1
                if weight:
                    past[bit] = past.get(bit, 0) + 1
                state.remove(other)
                pending.insert(rng.randrange(len(pending) + 1), other)
            state.assign(item, selected)
            if not pending:
                return state.finish()
    return None
