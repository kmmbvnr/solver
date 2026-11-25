"""Test period-specific deviations from our static route pool within a change budget."""
import argparse
import json
import time
from functools import partial
from pathlib import Path

import numpy as np
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import shortest_path
from shiftopt import run_pipeline
from solve import routing_table


def refine(folder, name, seed, out):
    started = time.monotonic()
    def read(k):
        return json.loads((folder/f"{name}-{k}.json").read_text())
    g, tm, scenario = map(read, ("net","tm","scenario"))
    a,b,metric,cap = (np.array([e[k] for e in g["links"]]) for k in ("from","to","metric","capacity"))
    s,d = (np.array([x[k] for x in tm["demands"]]) for k in ("s","t"))
    volumes = np.array([x["v"] for x in tm["demands"]]).T
    n = len(g["nodes"])
    base = s.copy()
    for route in json.loads(seed.read_text())["srpaths"]:
        if route["t"] == 0:
            base[route["d"]] = route["w"][0]
    budget = min(x["value"] for x in scenario["budget"])
    # A changed two-segment route can remove two segments and add two.
    # Two adjacent periods can have disjoint sets of modified demands.
    limit = budget//8
    def period_table(t):
        closed = next((x["links"] for x in scenario["interventions"] if x["t"]==t), [])
        use = ~np.isin([e["id"] for e in g["links"]],closed)
        dist = shortest_path(csr_matrix((metric[use],(a[use],b[use])),shape=(n,n)),directed=True)
        p = routing_table(dist,a,b,metric,use)
        return dist, p

    def static_seed(plan, deadline):
        loads = []
        for t, vol in enumerate(volumes):
            _, p = period_table(t)
            loads.append(vol @ (p[s, base] + p[base, d]) / cap)
            del p
        return [base] * len(volumes), loads

    def improve_period(plan, deadline, *, t):
        waypoints, loads = plan
        via = waypoints[t].copy()
        load = loads[t]
        vol = volumes[t]
        dist, p = period_table(t)
        used = set()
        for _ in range(limit):
            top = np.argsort(-load)
            best = None
            key = tuple(np.sort(load)[::-1].round(9))
            for edge in top[:12]:
                candidates = np.flatnonzero((vol>0) & ((p[s,via,edge]+p[via,d,edge])>0))
                if not len(candidates):
                    continue
                u,v = s[candidates],d[candidates]
                share = p[u,:,edge] + p[:,v,edge].T
                reachable = np.isfinite(dist[u,:]) & np.isfinite(dist[:,v]).T
                share[~reachable] = np.inf
                gain = (p[u,via[candidates],edge]+p[via[candidates],v,edge]-share.min(axis=1))*vol[candidates]
                for h in np.argsort(-gain)[:12]:
                    if gain[h] < 1e-10:
                        break
                    j = int(candidates[h])
                    if j in used:
                        continue
                    nodes = np.flatnonzero((share[h] <= share[h].min()+1e-8) & (np.arange(n)!=d[j]))
                    nodes = nodes[np.argsort(dist[s[j],nodes]+dist[nodes,d[j]],kind="stable")[:22]]
                    for k in nodes:
                        delta = (p[s[j],k]+p[k,d[j]]-p[s[j],via[j]]-p[via[j],d[j]])*vol[j]/cap
                        candidate = load+delta
                        if candidate.max()>key[0]+1e-9:
                            continue
                        trial = tuple(np.sort(candidate)[::-1].round(9))
                        if trial < key:
                            key, best = trial,(j,k,candidate)
                if best is not None:
                    break
            if best is None:
                break
            j,k,load = best
            used.add(j)
            via[j] = k
        print(json.dumps({"period":t,"changes":len(used),"peak":load.max()}),flush=True)
        if not used:
            return None
        next_via, next_loads = waypoints.copy(), loads.copy()
        next_via[t], next_loads[t] = via, load
        return next_via, next_loads

    def load_vector(plan):
        return tuple(np.sort(np.concatenate(plan[1]))[::-1].round(9))

    steps = [static_seed, *(partial(improve_period, t=t) for t in range(len(volumes)) if limit)]
    waypoints, _ = run_pipeline(steps, load_vector)
    routes = [{"d": int(j), "t": t, "w": [int(via[j])]}
              for t, via in enumerate(waypoints) for j in np.flatnonzero(via != s)]
    out.write_text(json.dumps({"srpaths":routes}))
    print(json.dumps({"seconds":round(time.monotonic()-started,3)}))


if __name__ == "__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folder",type=Path)
    parser.add_argument("instance")
    parser.add_argument("seed",type=Path)
    parser.add_argument("output",type=Path)
    args=parser.parse_args()
    refine(args.folder,args.instance,args.seed,args.output)
