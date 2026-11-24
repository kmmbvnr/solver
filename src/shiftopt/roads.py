"""Resolve terminal-to-terminal travel along directed roads for each vehicle type."""
from dataclasses import dataclass
import heapq
import math


@dataclass(frozen=True)
class Path:
    minutes: float
    km: float
    nodes: tuple[str,...]


class RoadNetwork:
    def __init__(self,nodes,edges,vehicle_types):
        self.nodes=tuple(nodes)
        self.vehicle_types=tuple(vehicle_types)
        if (not self.nodes or not self.vehicle_types or
            any(not isinstance(x,str) or not x for x in (*self.nodes,*self.vehicle_types)) or
            len(set(self.nodes))!=len(self.nodes) or len(set(self.vehicle_types))!=len(self.vehicle_types)):
            raise ValueError("nodes and vehicle_types must be unique nonempty strings")
        self._adj={kind:{n:[] for n in self.nodes} for kind in self.vehicle_types}
        for edge in edges:
            a,b=edge['from'],edge['to']
            minutes,km=float(edge['minutes']),float(edge['km'])
            if a not in self._adj[self.vehicle_types[0]] or b not in self._adj[self.vehicle_types[0]]:
                raise ValueError(f"unknown road endpoint {a} or {b}")
            if not (math.isfinite(minutes) and minutes>0 and math.isfinite(km) and km>=0):
                raise ValueError("expected a positive travel time and nonnegative distance")
            allowed=edge.get('vehicle_types',self.vehicle_types)
            if not isinstance(allowed,(list,tuple)) or not set(allowed)<=set(self.vehicle_types):
                raise ValueError("unknown vehicle type on road")
            for kind in allowed:
                self._adj[kind][a].append((b,minutes,km))

    def _search(self,start,kind):
        if kind not in self._adj or start not in self._adj[kind]:
            raise ValueError("unknown vehicle type or start node")
        best={start:(0.,0.)}
        previous={}
        queue=[(0.,0.,start)]
        while queue:
            minutes,km,node=heapq.heappop(queue)
            if best[node]!=(minutes,km):
                continue
            for other,dt,dk in self._adj[kind][node]:
                candidate=(minutes+dt,km+dk)
                if candidate<best.get(other,(math.inf,math.inf)):
                    best[other]=candidate
                    previous[other]=node
                    heapq.heappush(queue,(*candidate,other))
        return best,previous

    def path(self,start,end,kind):
        if end not in self.nodes:
            raise ValueError("unknown destination")
        best,parents=self._search(start,kind)
        if end not in best:
            return None
        reverse=[end]
        while reverse[-1]!=start:
            reverse.append(parents[reverse[-1]])
        return Path(*best[end],tuple(reversed(reverse)))

    def matrices(self,terminals,kind):
        import numpy as np
        if not set(terminals)<=set(self.nodes):
            raise ValueError("unknown terminal node")
        minutes=np.full((len(terminals),len(terminals)),np.inf)
        km=np.full_like(minutes,np.inf)
        cache={}
        for i,origin in enumerate(terminals):
            if origin not in cache:
                cache[origin]=self._search(origin,kind)[0]
            best=cache[origin]
            for j,dest in enumerate(terminals):
                if dest in best:
                    minutes[i,j],km[i,j]=best[dest]
        return minutes,km


@dataclass(frozen=True)
class TimedPath:
    departure: float
    arrival: float
    km: float
    nodes: tuple[str,...]
    entries: tuple[float,...]
    travel_minutes: tuple[float,...]
    edge_km: tuple[float,...]


class TimedRoadNetwork:
    """Earliest arrivals with known directed closure intervals and waiting at junctions."""

    def __init__(self,nodes,edges,vehicle_types,closures=()):
        road=RoadNetwork(nodes,edges,vehicle_types)
        self.nodes=road.nodes
        self.vehicle_types=road.vehicle_types
        self._adj=road._adj
        intervals={}
        for closure in closures:
            a,b=closure['from'],closure['to']
            begin,end=float(closure['begin']),float(closure['end'])
            if not (math.isfinite(begin) and math.isfinite(end) and 0<=begin<end):
                raise ValueError('a closure needs a finite nonempty interval')
            if a not in self.nodes or b not in self.nodes:
                raise ValueError('unknown closure endpoint')
            existing=[kind for kind in self.vehicle_types if any(v==b for v,_,_ in self._adj[kind][a])]
            allowed=closure.get('vehicle_types',existing)
            if not isinstance(allowed,(tuple,list)) or not allowed or not set(allowed)<=set(existing):
                raise ValueError('closure references an absent directed road or vehicle class')
            for kind in allowed:
                intervals.setdefault((kind,a,b),[]).append((begin,end))
        self._closures={}
        for key,windows in intervals.items():
            merged=[]
            for begin,end in sorted(windows):
                if merged and begin<=merged[-1][1]:
                    merged[-1]=(merged[-1][0],max(end,merged[-1][1]))
                else:
                    merged.append((begin,end))
            self._closures[key]=tuple(merged)

    def _arrival_search(self,start,kind,departure):
        if kind not in self._adj or start not in self._adj[kind]:
            raise ValueError('unknown start or vehicle class')
        if not math.isfinite(departure) or departure<0:
            raise ValueError('departure must be a finite nonnegative minute')
        best={start:(float(departure),0.)}
        previous={}
        queue=[(float(departure),0.,start)]
        while queue:
            at,km,node=heapq.heappop(queue)
            if best[node]!=(at,km):
                continue
            for other,minutes,distance in self._adj[kind][node]:
                entry=at
                for begin,end in self._closures.get((kind,node,other),()):
                    if entry+minutes<=begin:
                        break
                    if entry<end:
                        entry=end
                candidate=entry+minutes,km+distance
                if candidate<best.get(other,(math.inf,math.inf)):
                    best[other]=candidate
                    previous[other]=(node,entry,minutes,distance)
                    heapq.heappush(queue,(*candidate,other))
        return best,previous

    def path_at(self,start,end,kind,departure):
        if end not in self.nodes:
            raise ValueError('unknown destination')
        best,previous=self._arrival_search(start,kind,departure)
        if end not in best:
            return None
        nodes=[end]
        entries=[]
        minutes=[]
        distances=[]
        while nodes[-1]!=start:
            prev,entry,dt,dk=previous[nodes[-1]]
            entries.append(entry)
            minutes.append(dt)
            distances.append(dk)
            nodes.append(prev)
        arrival,km=best[end]
        return TimedPath(float(departure),arrival,km,tuple(reversed(nodes)),tuple(reversed(entries)),
                         tuple(reversed(minutes)),tuple(reversed(distances)))

    def arrivals_from(self,start,terminals,kind,departure):
        """Absolute arrival minute and distance of a fastest accessible path to each terminal."""
        import numpy as np
        if not set(terminals)<=set(self.nodes):
            raise ValueError('unknown terminal')
        best,_=self._arrival_search(start,kind,departure)
        return np.array([best.get(t,(np.inf,np.inf)) for t in terminals],dtype=float).reshape(-1,2)
