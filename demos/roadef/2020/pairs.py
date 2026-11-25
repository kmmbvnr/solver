"""Reassign two start dates together, keeping the rest of the schedule fixed."""
from functools import lru_cache
from time import monotonic
from typing import NamedTuple

import numpy as np

from repair import compile_options
from shiftopt import neighborhood_search, run_pipeline


class State(NamedTuple):
    starts: tuple
    loads: np.ndarray
    risks: list
    cost: float


def pair_search(data, schedule, deadline):
    jobs = data["Interventions"]
    names = list(jobs)
    if len(names) < 2:
        return schedule
    offsets, begin, end, ptr, idx, weights, lo, hi, edges, adj, season, _ = compile_options(data, names)
    alpha = data["Alpha"]
    sizes = data["Scenarios_number"]
    quantiles = np.ceil(np.array(sizes) * data["Quantile"]).astype(int) - 1

    def cost(t, values):
        avg = values.mean()
        excess = max(0., np.partition(values, quantiles[t])[quantiles[t]] - avg)
        return alpha * avg + (1 - alpha) * excess

    @lru_cache(maxsize=4096)
    def risks(job, start):
        values = {}
        for t, (options, vectors) in jobs[names[job]]["risk"].items():
            positions = np.flatnonzero(options == start)
            if len(positions):
                values[t] = vectors[positions[0]]
        return values

    def update_load(loads, option, sign):
        span = slice(ptr[option], ptr[option + 1])
        loads[idx[span]] += sign * weights[span]

    starts = tuple(schedule[n] for n in names)
    loads = np.zeros_like(hi, dtype=float)
    totals = [np.zeros(n) for n in sizes]
    for j, start in enumerate(starts):
        update_load(loads, offsets[j] + start, 1)
        for t, vec in risks(j, start).items():
            totals[t] += vec
    initial = State(starts, loads, totals, sum(cost(t, v) for t, v in enumerate(totals)))

    def destroy(state, rng):
        a, b = rng.sample(range(len(names)), 2)
        return state, a, b

    def repair(partial, rng, deadline):
        state, a, b = partial
        sa, sb = state.starts[a], state.starts[b]
        if sa == sb or sb >= offsets[a + 1] - offsets[a] or sa >= offsets[b + 1] - offsets[b]:
            return None
        proposed = list(state.starts)
        proposed[a], proposed[b] = sb, sa
        load = state.loads.copy()
        for j in (a, b):
            old, new = offsets[j] + state.starts[j], offsets[j] + proposed[j]
            update_load(load, old, -1)
            update_load(load, new, 1)
            for other, tag in adj[edges[j]:edges[j + 1]]:
                opt = offsets[other] + proposed[other]
                first, last = max(begin[new], begin[opt]), min(end[new], end[opt])
                if first < last and season[tag, last] > season[tag, first]:
                    return None
        if np.any(load < lo - 1e-7) or np.any(load > hi + 1e-7):
            return None
        changes = {}
        for j in (a, b):
            for start, sign in ((state.starts[j], -1), (proposed[j], 1)):
                for t, v in risks(j, start).items():
                    if t not in changes:
                        changes[t] = state.risks[t].copy()
                    changes[t] += sign * v
        total = state.cost
        risk = state.risks.copy()
        for t, v in changes.items():
            total += cost(t, v) - cost(t, risk[t])
            risk[t] = v
        return State(tuple(proposed), load, risk, total)

    step = neighborhood_search(destroy, repair, lambda s: s.cost, attempts=100_000, seed=7)
    best = run_pipeline([step], lambda s: s.cost, initial=initial, seconds=max(0, deadline - monotonic()))
    return dict(zip(names, best.starts))
