"""Single-waypoint route pool for the Orange multi-period traffic benchmark."""
import argparse
import json
import time
from pathlib import Path

import numpy as np
from numba import njit
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import shortest_path
from shiftopt import Model, MINIMIZE, quicksum


@njit
def routing_table(dist, a, b, metric, active):
    n = len(dist)
    frac = np.zeros((n, n, len(a)), np.float32)
    for target in range(n):
        for u in np.argsort(dist[:, target]):
            if u == target or not np.isfinite(dist[u, target]):
                continue
            count = 0
            for e in range(len(a)):
                if active[e] and a[e] == u and metric[e] + dist[b[e], target] == dist[u, target]:
                    frac[u, target] += frac[b[e], target]
                    frac[u, target, e] += 1.
                    count += 1
            if count:
                frac[u, target] /= count
    return frac


def solve(folder, name, seconds, out):
    start = time.monotonic()
    def read(kind):
        return json.loads((folder / f"{name}-{kind}.json").read_text())
    graph, traffic, scenario = (read(k) for k in ("net", "tm", "scenario"))
    links, jobs = graph["links"], traffic["demands"]
    n = len(graph["nodes"])
    a, b, metric, cap = (np.array([e[k] for e in links]) for k in ("from", "to", "metric", "capacity"))
    s, d = (np.array([j[k] for j in jobs]) for k in ("s", "t"))
    volume = np.array([j["v"] for j in jobs]).T
    periods = len(volume)
    closed = {i["t"]: i["links"] for i in scenario["interventions"]}
    path, distance, loads = [], [], []
    for t in range(periods):
        use = ~np.isin([e["id"] for e in links], closed.get(t, []))
        dist = shortest_path(csr_matrix((metric[use], (a[use], b[use])), shape=(n, n)), directed=True)
        p = routing_table(dist, a, b, metric, use)
        path.append(p)
        distance.append(dist)
        loads.append(volume[t] @ p[s,d] / cap)
    loads = np.asarray(loads)
    # Using the same waypoints in all periods incurs no reconfiguration cost.
    via = s.copy()
    rng = np.random.default_rng(7)
    def write():
        routes = [{"d":int(j), "t":t, "w":[int(via[j])]} for j in np.flatnonzero(via != s) for t in range(periods)]
        out.write_text(json.dumps({"srpaths":routes}))
    write()
    for iteration in range(100):
        if time.monotonic()-start >= seconds:
            break
        peak = loads.max()
        hot = np.argsort(loads, axis=1)[:, -7:]
        pressure = (loads[np.arange(periods)[:,None],hot]/peak)**8
        impact = np.zeros(len(jobs))
        for t,p in enumerate(path):
            for edge, weight in zip(hot[t], pressure[t]):
                impact += volume[t]/cap[edge]*weight*(p[s,via,edge]+p[via,d,edge])
        selected = np.argsort(-(impact*rng.uniform(.55,1.45,len(jobs))))[:165]
        options, deltas = [], []
        for j in selected:
            if impact[j] <= 0:
                continue
            u, v, old = s[j], d[j], via[j]
            nodes = np.unique(np.r_[u, rng.choice(n, min(n,64), replace=False)])
            nodes = nodes[(nodes != old) & (nodes != v)]
            score = np.zeros(len(nodes))
            for t,p in enumerate(path):
                reachable = np.isfinite(distance[t][u,nodes]) & np.isfinite(distance[t][nodes,v])
                score[~reachable] = np.inf
                edges = hot[t]
                shares = p[u,nodes[:,None],edges] + p[nodes[:,None],v,edges]
                score += (shares @ (pressure[t]/cap[edges])) * volume[t,j]
            score += rng.uniform(0., 1e-9, len(nodes))
            for pos in np.argsort(score)[:3]:
                if not np.isfinite(score[pos]):
                    continue
                k = nodes[pos]
                delta = np.array([volume[t,j]*(p[u,k]+p[k,v]-p[u,old]-p[old,v])/cap
                                  for t,p in enumerate(path)],dtype=np.float32)
                if delta.min() < -1e-8:
                    options.append((int(j),int(k)))
                    deltas.append(delta.ravel())
        if not options:
            break
        matrix = np.stack(deltas,axis=1)
        model = Model(threads=1)
        variables = [model.addVar(vtype="B") for _ in options]
        by_job = {}
        for (j,k),var in zip(options,variables):
            by_job.setdefault(j,[]).append(var)
        for group in by_job.values():
            model.addConstr(quicksum(group)<=1)
        worst = model.addVar(lb=0,ub=peak+1e-7)
        excess = []
        threshold = peak*.80
        base = loads.ravel()
        for i in np.flatnonzero(base + np.maximum(matrix,0).sum(axis=1) >= threshold):
            co = matrix[i]
            nz = np.flatnonzero(np.abs(co)>1e-11)
            load = float(base[i]) + quicksum(float(co[k])*variables[k] for k in nz)
            model.addConstr(worst >= load)
            over = model.addVar(lb=0)
            model.addConstr(over >= load-threshold)
            excess.append(over)
        model.setObjective(worst + .02*quicksum(excess), MINIMIZE)
        model.setStart(zip(variables, np.zeros(len(options))))
        left = seconds - (time.monotonic()-start)
        if left < .05:
            break
        res = model.optimize(time_limit=min(left, 5.),mip_gap=.001)
        if not res.has_solution:
            continue
        pick = [i for i,var in enumerate(variables) if res.value(var)>.5]
        trial = loads + matrix[:,pick].sum(axis=1,dtype=float).reshape(loads.shape)
        if tuple(np.sort(trial.ravel())[::-1].round(8)) < tuple(np.sort(base)[::-1].round(8)):
            for k in pick:
                j,w = options[k]
                via[j] = w
            loads = trial
            write()
        print(json.dumps(dict(iteration=iteration,initial=float(peak),peak=float(loads.max()),
                              detours=int(sum(via != s)),seconds=round(time.monotonic()-start,3))),flush=True)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("folder",type=Path)
    p.add_argument("instance")
    p.add_argument("--seconds",type=float,default=120)
    p.add_argument("--output",type=Path,required=True)
    args=p.parse_args()
    solve(args.folder,args.instance,args.seconds,args.output)
