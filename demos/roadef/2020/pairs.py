"""Rotate start dates among interventions, keeping the rest of the schedule fixed."""
from functools import lru_cache
from time import monotonic
from typing import NamedTuple

import numpy as np

from repair import compile_options
from shiftopt import ejection_chain, neighborhood_search, run_pipeline


class State(NamedTuple):
    starts: tuple
    loads: np.ndarray
    risks: list
    cost: float


def pair_search(data, schedule, deadline, chain_length=2):
    if chain_length < 2:
        raise ValueError("chain length must be at least two")
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

    def start(state, rng):
        return tuple(rng.sample(range(len(names)), 2))

    def rotate(state, chain):
        proposed = list(state.starts)
        for i, job in enumerate(chain):
            start = state.starts[chain[(i + 1) % len(chain)]]
            if start >= offsets[job + 1] - offsets[job]:
                return None
            proposed[job] = start
        if proposed[chain[0]] == state.starts[chain[0]]:
            return None
        load = state.loads.copy()
        for j in chain:
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
        for j in chain:
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

    def extend(state, chain, rng):
        # Give the last displaced job a date currently assigned to another job.
        last = chain[-1]
        for other in rng.sample(range(len(names)), min(8, len(names))):
            if (other not in chain and state.starts[other] != state.starts[last]
                    and state.starts[other] < offsets[last + 1] - offsets[last]):
                yield (*chain, other)

    def score(state):
        return state.cost

    if chain_length == 2:
        def destroy(state, rng):
            return state, start(state, rng)
        def repair(partial, rng, deadline):
            return rotate(*partial)
        step = neighborhood_search(destroy, repair, score, attempts=100_000, seed=7)
    else:
        # Opening a pair displaces one job. Each extension displaces one more.
        step = ejection_chain(start, extend, rotate, score, max_depth=chain_length - 1,
                              max_nodes=16, attempts=100_000, seed=7)
    best = run_pipeline([step], score, initial=initial, seconds=max(0, deadline - monotonic()))
    return dict(zip(names, best.starts))
