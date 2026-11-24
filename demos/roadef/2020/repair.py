"""Repair scheduling conflicts by trying every date of a conflicting intervention."""

from itertools import pairwise
from time import monotonic

import numpy as np
from numba import njit
from scipy.sparse import csr_matrix


def compile_options(data, names):
    jobs = data["Interventions"]
    ids = {name: i for i, name in enumerate(names)}
    opts = np.r_[0, np.cumsum([int(jobs[n]["tmax"]) for n in names])]
    begin = np.concatenate(
        [np.arange(opts[i + 1] - opts[i]) for i in range(len(names))]
    )
    end = begin + np.concatenate(
        [jobs[n]["Delta"][: int(jobs[n]["tmax"])] for n in names]
    )
    resources = list(data["Resources"])
    lo = np.array([data["Resources"][r]["min"] for r in resources]).ravel()
    hi = np.array([data["Resources"][r]["max"] for r in resources]).ravel()
    rows, cols, values = [], [], []
    risk_cost = np.zeros(opts[-1])
    for i, n in enumerate(names):
        for starts, vectors in jobs[n]["risk"].values():
            risk_cost[opts[i] + starts] += vectors.mean(axis=1)
        for r, table in jobs[n]["workload"].items():
            base = resources.index(r) * data["T"]
            for t, usage in table.items():
                for s, v in usage.items():
                    if v:
                        rows.append(opts[i] + int(s) - 1)
                        cols.append(base + int(t) - 1)
                        values.append(v)
        costs = risk_cost[opts[i] : opts[i + 1]]
        costs -= costs.min()
        costs /= max(1.0, costs.max())
    matrix = csr_matrix((values, (rows, cols)), shape=(opts[-1], len(lo)))
    seasons = np.zeros((len(data["Seasons"]), data["T"] + 1), dtype=np.int32)
    for k, days in enumerate(data["Seasons"].values()):
        seasons[k, np.asarray(days, dtype=int)] = 1
    arcs = [[] for n in names]
    for a, b, season in data["Exclusions"].values():
        tag = list(data["Seasons"]).index(season)
        arcs[ids[a]].append((ids[b], tag))
        arcs[ids[b]].append((ids[a], tag))
    adjacent = np.array(
        [pair for group in arcs for pair in group], dtype=np.int64
    ).reshape(-1, 2)
    neighbors = np.r_[0, np.cumsum([len(group) for group in arcs])]
    return (
        opts,
        begin,
        end,
        matrix.indptr,
        matrix.indices,
        matrix.data,
        lo,
        hi,
        neighbors,
        adjacent,
        seasons.cumsum(axis=1),
        risk_cost,
    )


@njit(cache=True)
def search(starts, arrays, seed, attempts, prices=None):
    (
        options,
        begin,
        end,
        ptr,
        idx,
        weight,
        lo,
        hi,
        neighbors,
        adj,
        seasons,
        risk_cost,
    ) = arrays
    np.random.seed(seed)
    loads = np.zeros(len(lo))
    scale = np.maximum(hi, 1.0)
    if prices is not None:
        scale /= prices
    for v in starts:
        for k in range(ptr[v], ptr[v + 1]):
            loads[idx[k]] += weight[k]
    total = 0.0
    for r in range(len(lo)):
        total += max(0.0, loads[r] - hi[r], lo[r] - loads[r]) / scale[r]
    for j, v in enumerate(starts):
        for e in range(neighbors[j], neighbors[j + 1]):
            other, season = adj[e]
            if other >= j:
                continue
            a = max(begin[v], begin[starts[other]])
            b = min(end[v], end[starts[other]])
            total += int(a < b and seasons[season, b] != seasons[season, a])
    best = starts.copy()
    record = total
    stale = 0
    for step in range(attempts):
        if record < 1e-8:
            break
        j = np.random.randint(len(starts))
        v = starts[j]
        in_conflict = False
        for k in range(ptr[v], ptr[v + 1]):
            r = idx[k]
            if loads[r] > hi[r] + 1e-8:
                in_conflict = True
                break
        for e in range(neighbors[j], neighbors[j + 1]):
            other, season = adj[e]
            a = max(begin[v], begin[starts[other]])
            b = min(end[v], end[starts[other]])
            if a < b and seasons[season, b] != seasons[season, a]:
                in_conflict = True
                break
        if not in_conflict and np.random.random() > 0.08:
            continue
        for k in range(ptr[v], ptr[v + 1]):
            loads[idx[k]] -= weight[k]
        selected = v
        lowest = np.inf
        before = 0.0
        after = 0.0
        noise = (
            0.00001 if stale < len(starts) // 2 else (0.05 if prices is None else 0.003)
        )
        for candidate in range(options[j], options[j + 1]):
            cost = 0.0
            for k in range(ptr[candidate], ptr[candidate + 1]):
                r = idx[k]
                old = loads[r]
                new = old + weight[k]
                cost += (
                    max(0.0, new - hi[r], lo[r] - new)
                    - max(0.0, old - hi[r], lo[r] - old)
                ) / scale[r]
            for e in range(neighbors[j], neighbors[j + 1]):
                other, season = adj[e]
                a = max(begin[candidate], begin[starts[other]])
                b = min(end[candidate], end[starts[other]])
                cost += int(a < b and seasons[season, b] != seasons[season, a])
            if candidate == v:
                before = cost
            rank = cost + noise * (risk_cost[candidate] + np.random.random())
            if rank < lowest:
                lowest = rank
                selected = candidate
                after = cost
        starts[j] = selected
        for k in range(ptr[selected], ptr[selected + 1]):
            loads[idx[k]] += weight[k]
        total += after - before
        stale += 1
        if total < record - 1e-9:
            best[:] = starts
            record = total
            stale = 0
    return best, record


def repair(data, seconds, margins=True):
    names = list(data["Interventions"])
    arrays = compile_options(data, names)
    options = arrays[0]
    rng = np.random.default_rng(7)
    best = np.array(
        [
            a + np.argmin(arrays[-1][a:b] + 0.08 * rng.random(b - a))
            for a, b in pairwise(options)
        ]
    )
    record = np.inf
    deadline = monotonic() + seconds
    attempt = 0
    prices = np.ones(len(arrays[7]))
    while monotonic() < deadline:
        state = best.copy()
        if attempt:
            chosen = rng.choice(len(names), max(1, len(names) // 20), replace=False)
            state[chosen] = rng.integers(options[chosen], options[chosen + 1])
        if margins:
            buffer = (0.025, 0.015, 0.008, 0.0)[attempt % 4]
            stricter = (
                *arrays[:7],
                np.maximum(arrays[6], arrays[7] * (1 - buffer)),
                *arrays[8:],
            )
            result, _ = search(state, stricter, 7 + attempt, 150 * len(names), prices)
            _, cost = search(result.copy(), arrays, 7, 0)
            _, _, _, ptr, idx, weight, lo, hi, *_ = arrays
            loads = np.zeros(len(lo))
            for opt in result:
                loads[idx[ptr[opt] : ptr[opt + 1]]] += weight[ptr[opt] : ptr[opt + 1]]
            prices *= 0.95
            prices[(loads > hi + 1e-7) | (loads < lo - 1e-7)] += 3
            np.maximum(prices, 1.0, out=prices)
        else:
            result, cost = search(state, arrays, 7 + attempt, 150 * len(names))
        if cost < record:
            best, record = result, cost
        if record < 1e-8:
            return dict(zip(names, best - options[:-1]))
        attempt += 1
    raise RuntimeError(f"Unresolved schedule conflicts: {record:g}")
