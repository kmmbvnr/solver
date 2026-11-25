"""Optimize the contest quantile objective by moving one maintenance start at a time."""

from collections import defaultdict
from time import monotonic

import numpy as np
from shiftopt.restart import restart_strength


def refine(data, schedule, deadline, adaptive=False):
    jobs = data["Interventions"]
    starts = dict(schedule)
    sizes = data["Scenarios_number"]
    quantiles = np.ceil(np.array(sizes) * data["Quantile"]).astype(int) - 1
    alpha = data["Alpha"]
    totals = [np.zeros(n) for n in sizes]
    resources = list(data["Resources"])
    lo = np.array([data["Resources"][r]["min"] for r in resources]).ravel()
    hi = np.array([data["Resources"][r]["max"] for r in resources]).ravel()
    loads = np.zeros_like(hi, dtype=float)
    conflicts = defaultdict(list)
    for a, b, tag in data["Exclusions"].values():
        times = np.array([int(t) - 1 for t in data["Seasons"][tag]], dtype=int)
        conflicts[a].append((b, times))
        conflicts[b].append((a, times))

    columns = {}
    for name, job in jobs.items():
        start = starts[name]
        count = int(job["tmax"])
        risks = []
        for t, (options, vectors) in job["risk"].items():
            risks.append((t, options, vectors))
            pos = np.flatnonzero(options == start)
            if len(pos):
                totals[t] += vectors[pos[0]]
        indices, usage = [], []
        for resource, periods in job["workload"].items():
            offset = resources.index(resource) * len(sizes)
            for period, values in periods.items():
                indices.append(offset + int(period) - 1)
                row = np.zeros(count)
                for s, v in values.items():
                    row[int(s) - 1] = v
                usage.append(row)
        idx = np.array(indices, dtype=int)
        work = np.array(usage).reshape(len(idx), count)
        loads[idx] += work[:, start]
        columns[name] = risks, idx, work

    def cost(samples, k):
        avg = samples.mean(axis=-1)
        q = np.partition(samples, k, axis=-1)[..., k]
        return alpha * avg + (1 - alpha) * np.maximum(q - avg, 0)

    rng = np.random.default_rng(7)
    best = starts.copy()
    delta = best_delta = 0.0
    shake = False
    strength = max(2, len(jobs) // 12)
    adjust = restart_strength(2, max(2, len(jobs) // 4)) if adaptive else None
    previous_restart = float("inf")
    while monotonic() < deadline:
        improved = False
        for name in rng.permutation(list(jobs)):
            if monotonic() >= deadline:
                break
            old = starts[name]
            job = jobs[name]
            ends = np.arange(int(job["tmax"])) + np.array(
                job["Delta"][: int(job["tmax"])]
            )
            options = np.arange(len(ends))
            risks, idx, work = columns[name]
            trial_load = (loads[idx] - work[:, old])[:, None] + work
            ok = np.all(
                (trial_load >= lo[idx, None] - 1e-7)
                & (trial_load <= hi[idx, None] + 1e-7),
                axis=0,
            )
            for other, times in conflicts[name]:
                begin = starts[other]
                occupied = times[
                    (times >= begin) & (times < begin + jobs[other]["Delta"][begin])
                ]
                for t in occupied:
                    ok &= (ends <= t) | (options > t)
            if ok.sum() <= 1:
                continue
            scores = np.zeros(len(ends))
            for t, ids, vectors in risks:
                pos = np.flatnonzero(ids == old)
                base = totals[t] - vectors[pos[0]] if len(pos) else totals[t]
                valid = ok[ids]
                if np.any(valid):
                    scores[ids[valid]] += cost(
                        base + vectors[valid], quantiles[t]
                    ) - cost(base, quantiles[t])
            scores[~ok] = np.inf
            new = int(np.argmin(scores))
            if shake:
                shortlist = np.flatnonzero(ok & (options != old))
                shortlist = shortlist[np.argsort(scores[shortlist])[:4]]
                new = int(rng.choice(shortlist))
            elif scores[new] >= scores[old] - 1e-7:
                continue
            for t, ids, vectors in risks:
                for s, sign in ((old, -1), (new, 1)):
                    pos = np.flatnonzero(ids == s)
                    if len(pos):
                        totals[t] += sign * vectors[pos[0]]
            loads[idx] = trial_load[:, new]
            starts[name] = new
            delta += scores[new] - scores[old]
            if delta < best_delta - 1e-7:
                best_delta = delta
                best = starts.copy()
            improved = True
            if shake:
                strength -= 1
                if strength <= 0:
                    break
        if shake:
            shake = False
        elif not improved:
            shake = True
            strength = adjust(best_delta < previous_restart - 1e-7) if adjust else max(2, len(jobs) // 12)
            previous_restart = best_delta
    return best


def objective_value(data, starts):
    totals = [np.zeros(n) for n in data["Scenarios_number"]]
    for name, s in starts.items():
        for t, (ids, vectors) in data["Interventions"][name]["risk"].items():
            pos = np.flatnonzero(ids == s)
            if len(pos):
                totals[t] += vectors[pos[0]]
    alpha = data["Alpha"]
    result = 0.0
    for samples in totals:
        mean = samples.mean()
        k = int(np.ceil(data["Quantile"] * len(samples))) - 1
        result += alpha * mean + (1 - alpha) * max(
            0.0, np.partition(samples, k)[k] - mean
        )
    return result / len(totals)
