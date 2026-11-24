"""Mix timed routes from complete ROADEF schedules, with continuous trailer and customer stocks."""
import argparse
from collections import defaultdict
from dataclasses import dataclass
import json
import os
from pathlib import Path
import time
import xml.etree.ElementTree as ET

import numpy as np
import highspy as hs
from scipy.sparse import csc_matrix,csr_matrix
from shiftopt import Model,quicksum
from shiftopt.model import InconsistentObjective
from instance_xml import table
from instance_xml import atomic_output


@dataclass(frozen=True)
class Route:
    driver: int
    trailer: int
    start: int
    ops: tuple


def load_plans(paths):
    plans=[]
    for path in paths:
        plan={}
        for row in ET.parse(path).getroot().find('Shifts'):
            ops=list(row.find('operations'))
            route=Route(int(row.findtext('driver')),int(row.findtext('trailer')),int(row.findtext('start')),
                        tuple((int(e.findtext('point')),int(e.findtext('arrival'))) for e in ops))
            if route in plan:
                raise ValueError('duplicate route in schedule')
            plan[route]=tuple(float(e.findtext('Quantity')) for e in ops)
        plans.append(plan)
    return plans


def export(path,plan):
    root=ET.Element('IRP_Roadef_Challenge_Output')
    parent=ET.SubElement(root,'Shifts')
    for i,(r,quantities) in enumerate(sorted(plan.items(),key=lambda entry:(entry[0].start,entry[0].driver))):
        shift=ET.SubElement(parent,'IRP_Roadef_Challenge_Shift_')
        for key,val in [('index',i),('driver',r.driver),('trailer',r.trailer),('start',r.start)]:
            ET.SubElement(shift,key).text=str(val)
        ops=ET.SubElement(shift,'operations')
        for (point,at),q in zip(r.ops,quantities,strict=True):
            node=ET.SubElement(ops,'IRP_Roadef_Challenge_Operation_')
            for key,val in [('point',point),('arrival',at),('Quantity',f'{q:.8f}')]:
                ET.SubElement(node,key).text=str(val)
    ET.indent(root)
    with atomic_output(path,'wb') as handle:
        ET.ElementTree(root).write(handle,encoding='utf-8',xml_declaration=True)


def interval_cliques(routes,finish,resource,rest):
    sets=set()
    groups=defaultdict(list)
    for r in routes:
        groups[resource(r)].append(r)
    for group in groups.values():
        active=[]
        starts=defaultdict(list)
        for r in group:
            starts[r.start].append(r)
        for at,adding in sorted(starts.items()):
            remaining=[r for r in active if finish[r]+rest(r)>at]
            if len(remaining)<len(active) and len(active)>1:
                sets.add(frozenset(active))
            active=remaining+adding
        if len(active)>1:
            sets.add(frozenset(active))
    return sets


def variations(routes,offsets,drivers,sites,setup,travel,horizon):
    def windows(node):
        return [(int(w.findtext('start')),int(w.findtext('end'))) for w in node.find('timewindows')]
    availability=[windows(d) for d in drivers]
    open_at={p:windows(c) for p,c in sites.items()}
    orders={p:[(int(o.findtext('earliestTime')),int(o.findtext('latestTime'))) for o in c.find('orders')]
            for p,c in sites.items() if int(c.findtext('callIn'))}
    seen=set(routes)
    result=list(routes)
    for r in routes:
        p,arrival=r.ops[-1]
        finish=arrival+setup[p]+travel[p,0]
        for offset in offsets:
            begin=r.start+offset
            end=finish+offset
            if begin<0 or end>horizon or not any(a<=begin and end<=b for a,b in availability[r.driver]):
                continue
            ops=tuple((p,t+offset) for p,t in r.ops)
            if any(not any(a<=t and t+setup[p]<=b for a,b in open_at[p]) for p,t in ops if p in sites):
                continue
            if any(sum(a<=t<=b for a,b in orders[p])!=1 for p,t in ops if p in orders):
                continue
            shifted=Route(r.driver,r.trailer,begin,ops)
            if shifted not in seen:
                result.append(shifted)
                seen.add(shifted)
    return result


def terminal_stops(routes, count, drivers, trailers, sites, setup, travel, km, horizon, replace_last=False):
    # Preserve the driver's complete schedule up to the last original unloading event.
    eligible = []
    for point, site in sites.items():
        if int(site.findtext("callIn")):
            continue
        windows = [(int(w.findtext("start")), int(w.findtext("end"))) for w in site.find("timewindows")]
        allowed = {int(k.text) for k in site.find("allowedTrailers")}
        room = float(site.findtext("Capacity")) - float(site.findtext("SafetyLevel"))
        eligible.append((point, windows, allowed, room))
    result = dict.fromkeys(routes)
    prefixes = set()
    for r in routes:
        last, at = r.ops[-1]
        if last not in sites:
            continue
        driver = drivers[r.driver]
        begin_end = [(int(w.findtext("start")), int(w.findtext("end"))) for w in driver.find("timewindows")]
        maximum = int(driver.findtext("maxDrivingDuration"))
        nodes = [0, *(p for p, _ in r.ops)]
        driving = sum(travel[a,b] for a,b in zip(nodes,nodes[1:]))
        capacity = float(trailers[r.trailer].findtext("Capacity"))
        if len(r.ops)>2 and not int(sites[last].findtext("callIn")):
            prior, previous_arrival = r.ops[-2]
            direct_drive = driving-travel[prior,last]+travel[prior,0]
            direct_finish = previous_arrival+setup[prior]+travel[prior,0]
            if (direct_drive<=maximum and direct_finish<=horizon
                and any(a<=r.start and direct_finish<=b for a,b in begin_end)):
                shortened = Route(r.driver,r.trailer,r.start,r.ops[:-1])
                result[shortened] = None
                prefixes.add(shortened)
        offers = []
        for p, windows, allowed, room in eligible:
            if p in nodes or r.trailer not in allowed or room<=0:
                continue
            arrive = int(at+setup[last]+travel[last,p])
            leave = arrive+setup[p]
            finish = leave+travel[p,0]
            if (driving+travel[last,p]+travel[p,0]>maximum or finish>horizon
                or not any(a<=arrive and leave<=b for a,b in windows)
                or not any(a<=r.start and finish<=b for a,b in begin_end)):
                continue
            detour = (km[last,p]+km[p,0]-km[last,0])*float(trailers[r.trailer].findtext("DistanceCost"))
            detour += (finish-at-setup[last]-travel[last,0])*float(driver.findtext("TimeCost"))
            offers.append((detour/min(room,capacity),p,arrive))
        for _,p,arrive in sorted(offers)[:count]:
            result[Route(r.driver,r.trailer,r.start,(*r.ops,(p,arrive)))] = None
    if replace_last and prefixes:
        frozen_prefixes = sorted(prefixes,key=lambda r:(r.driver,r.trailer,r.start,r.ops))
        proposals = terminal_stops(frozen_prefixes,count,drivers,trailers,sites,setup,travel,km,horizon)
        for candidate in proposals:
            if Route(candidate.driver,candidate.trailer,candidate.start,candidate.ops[:-1]) in prefixes:
                result[candidate] = None
    return list(result)


def exchange_stops(routes,limit,drivers,trailers,sites,setup,travel,km,horizon):
    """Offer both sides of a customer exchange between two incumbent shifts."""
    from functools import lru_cache
    from itertools import combinations

    def windows(node):
        return [(int(w.findtext('start')),int(w.findtext('end'))) for w in node.find('timewindows')]
    available=[windows(d) for d in drivers]
    opening={p:windows(site) for p,site in sites.items()}
    allowed={p:{int(t.text) for t in site.find('allowedTrailers')} for p,site in sites.items()}
    layover={p:bool(int(site.findtext('LayoverCustomer'))) for p,site in sites.items()}
    orders={p:[(int(o.findtext('earliestTime')),int(o.findtext('latestTime'))) for o in site.find('orders')]
            for p,site in sites.items() if int(site.findtext('callIn'))}
    costs=[float(t.findtext('DistanceCost')) for t in trailers]
    info={}
    for r in routes:
        driver=drivers[r.driver]
        rest=int(driver.findtext("LayoverDuration"))
        prev,at=0,r.start
        pauses=[]
        for p,t in r.ops:
            pauses.append(rest if rest and t-at-travel[prev,p]>=rest else 0)
            prev,at=p,t+setup[p]
        info[r]=(pauses,int(driver.findtext('maxDrivingDuration')),float(driver.findtext('TimeCost')))

    @lru_cache(maxsize=None)
    def retime(r,position,new):
        points=[p for p,_ in r.ops]
        if new in points or r.trailer not in allowed[new]:
            return None
        points[position]=new
        pauses,drive_limit,rate=info[r]
        if any(layover.get(p,False) for p in points) and not any(pauses):
            return None
        ops=[]
        prev=0
        at=r.start
        driving=distance=0
        for i,p in enumerate(points):
            leg=int(travel[prev,p])
            driving+=leg
            if pauses[i]:
                driving=max(0,driving-drive_limit)
            if driving>drive_limit:
                return None
            reach=at+leg+pauses[i]
            if p in sites:
                t=next((max(a,reach) for a,b in opening[p] if max(a,reach)+setup[p]<=b),None)
                if t is None or (p in orders and sum(a<=t<=b for a,b in orders[p])!=1):
                    return None
                rest=int(drivers[r.driver].findtext("LayoverDuration"))
                if not pauses[i] and rest and t-reach>=rest:
                    return None
            else:
                # All generated tours start at their assigned source and retain its original time.
                if i!=0: return None
                t=r.ops[i][1]
            ops.append((p,int(t)))
            distance+=km[prev,p]
            prev,at=p,t+setup[p]
        finish=at+travel[prev,0]
        if (driving+travel[prev,0]>drive_limit or finish>horizon
                or not any(a<=r.start and finish<=b for a,b in available[r.driver])):
            return None
        return Route(r.driver,r.trailer,r.start,tuple(ops)), (distance+km[prev,0])*costs[r.trailer]+(finish-r.start)*rate

    old_cost={}
    for r in routes:
        nodes=[0,*[p for p,_ in r.ops],0]
        p,at=r.ops[-1]
        finish=at+setup[p]+travel[p,0]
        old_cost[r]=sum(km[a,b] for a,b in zip(nodes,nodes[1:]))*costs[r.trailer]+(finish-r.start)*info[r][2]
    by_route=defaultdict(list)
    for r,s in combinations(routes,2):
        for i,(p,_) in enumerate(r.ops):
            for j,(q,_) in enumerate(s.ops):
                if p not in sites or q not in sites or p==q:
                    continue
                x,y=retime(r,i,q),retime(s,j,p)
                if x and y:
                    gain=old_cost[r]+old_cost[s]-x[1]-y[1]
                    for key in (r,s):
                        by_route[key].append((gain,x[0],y[0]))
    proposals={}
    for options in by_route.values():
        for _,a,b in sorted(options,key=lambda opt:-opt[0])[:limit]:
            proposals[a]=proposals[b]=None
    return list(proposals)


def optimize(instance,paths,out,budget,offsets=(),cliques=False,journal=None,window=None,extra_stops=0,replace_last=False,pair_exchanges=0):
    start=time.monotonic()
    root=ET.parse(instance).getroot()
    trailers=list(root.find('trailers'))
    drivers=list(root.find('drivers'))
    sites={int(c.findtext('index')):c for c in root.find('customers')}
    sources={int(s.findtext('index')):s for s in root.find('sources')}
    setup={p:int(e.findtext('setupTime')) for p,e in {**sites,**sources}.items()}
    km=table(root,'DistMatrices')
    travel=table(root,'timeMatrices')
    unit=int(root.findtext('unit'))
    plans=load_plans(paths)
    routes=list(dict.fromkeys(r for plan in plans for r in plan))
    original_count=len(routes)
    horizon=unit*int(root.findtext("horizon"))
    frozen=[]
    swappable=routes if window is None else [r for r in routes if window[0]*1440<=r.start<window[1]*1440]
    exchanged=exchange_stops(swappable,pair_exchanges,drivers,trailers,sites,setup,travel,km,horizon) if pair_exchanges else []
    if window is None:
        if extra_stops:
            routes=terminal_stops(routes,extra_stops,drivers,trailers,sites,setup,travel,km,horizon,replace_last)
        routes=variations(routes,offsets,drivers,sites,setup,travel,horizon)
    else:
        begin,end_minute=(day*1440 for day in window)
        if len(plans)!=1 or not 0<=begin<end_minute<=horizon:
            raise ValueError('window requires one incumbent and an interval inside its horizon')
        frozen=[r for r in routes if not begin<=r.start<end_minute]
        active=[r for r in routes if begin<=r.start<end_minute]
        if extra_stops:
            active=terminal_stops(active,extra_stops,drivers,trailers,sites,setup,travel,km,horizon,replace_last)
        candidates=variations(active,offsets,drivers,sites,setup,travel,horizon)
        routes=frozen+[r for r in candidates if begin<=r.start<end_minute]
    if exchanged:
        routes=list(dict.fromkeys([*routes,*exchanged]))
    model=Model(threads=1)
    selected={}
    quantities={}
    costs={}
    end={}
    by_trailer=defaultdict(list)
    by_site=defaultdict(list)
    for r in routes:
        y=selected[r]=model.addVar(vtype='B')
        cap=float(trailers[r.trailer].findtext('Capacity'))
        dur=int(drivers[r.driver].findtext('LayoverDuration'))
        driver_cost=float(drivers[r.driver].findtext('TimeCost'))
        fixed_rest=float(drivers[r.driver].findtext('LayoverCost'))
        distance=0.
        rests=0
        prev=0
        at=r.start
        amounts=[]
        for j,(p,t) in enumerate(r.ops):
            leg=travel[prev,p]
            if t-at-leg>=dur and dur>0:
                rests+=1
            distance+=km[prev,p]
            at=t+setup[p]
            prev=p
            if p in sources:
                q=model.addVar(lb=-cap,ub=0)
                model.addConstr(q>=-cap*y)
            else:
                q=model.addVar(ub=cap)
                model.addConstr(q<=cap*y)
                minimum=0 if int(sites[p].findtext('callIn')) else float(sites[p].findtext('MinOperationQuantity'))
                if minimum:
                    model.addConstr(q>=minimum*y)
                by_site[p].append((t,q))
            by_trailer[r.trailer].append((t,len(by_trailer[r.trailer]),q))
            amounts.append(q)
        quantities[r]=amounts
        end[r]=int(at+travel[prev,0])
        costs[r]=(distance+km[prev,0])*float(trailers[r.trailer].findtext('DistanceCost'))+(end[r]-r.start)*driver_cost+rests*(fixed_rest-dur*driver_cost)
    for route in frozen:
        model.addConstr(selected[route]==1)
    if cliques:
        exclusive=interval_cliques(routes,end,lambda r:r.driver,lambda r:int(drivers[r.driver].findtext('minInterSHIFTDURATION')))
        exclusive.update(interval_cliques(routes,end,lambda r:r.trailer,lambda r:0))
        # Deterministic row and column order for independent repeat runs.
        order={r:i for i,r in enumerate(routes)}
        groups=sorted(tuple(sorted(order[r] for r in group)) for group in exclusive)
        for group in groups:
            model.addConstr(quicksum(selected[routes[i]] for i in group)<=1)
    else:
        for i,r in enumerate(routes):
            for s in routes[:i]:
                same_driver=r.driver==s.driver
                if not same_driver and r.trailer!=s.trailer:
                    continue
                rest=int(drivers[r.driver].findtext('minInterSHIFTDURATION')) if same_driver else 0
                if r.start<end[s]+rest and s.start<end[r]+rest:
                    model.addConstr(selected[r]+selected[s]<=1)
    def between(terms,low,high):
        if not terms:
            if not low-1e-6<=0<=high+1e-6:
                raise ValueError('empty group cannot meet demand')
            return
        expr=quicksum(terms)
        model.addConstr(expr>=low)
        model.addConstr(expr<=high)
    stock_links=[]
    for k,visits in by_trailer.items():
        opening=float(trailers[k].findtext('InitialQuantity'))
        cap=float(trailers[k].findtext('Capacity'))
        if cliques:
            by_time=defaultdict(list)
            for t,_,q in visits:
                by_time[t].append(q)
            prev=opening
            links=[]
            for t,amounts in sorted(by_time.items()):
                stock=model.addVar(ub=cap)
                model.addConstr(stock+quicksum(amounts)==prev)
                links.append((int(stock),[int(q) for q in amounts]))
                prev=stock
            stock_links.append((opening,links))
        else:
            prefix=[]
            for _,_,q in sorted(visits):
                prefix.append(q)
                between(prefix,opening-cap,opening)
    for p,site in sites.items():
        visits=by_site[p]
        if int(site.findtext('callIn')):
            matched=0
            for order in site.find('orders'):
                a,b=int(order.findtext('earliestTime')),int(order.findtext('latestTime'))
                quantities_due=[q for t,q in visits if a<=t<=b]
                target=float(order.findtext('Quantity'))
                between(quantities_due,target*float(order.findtext('orderQuantityFlexibility'))/100.,target)
                matched+=len(quantities_due)
            if matched!=len(visits):
                raise ValueError('ambiguous order or visit outside call-in windows')
        else:
            cumulative=np.cumsum([float(q.text) for q in site.find('Forecast')])
            opening=float(site.findtext('InitialTankQuantity'))
            cap=float(site.findtext('Capacity'))
            floor=float(site.findtext('SafetyLevel'))
            by_tick=defaultdict(list)
            for t,q in visits:
                by_tick[t//unit].append(q)
            ticks=sorted({0,*by_tick})
            prefix=[]
            for tick,following in zip(ticks,ticks[1:]+[len(cumulative)]):
                prefix.extend(by_tick[tick])
                between(prefix,floor-opening+cumulative[following-1],cap-opening+cumulative[tick])
    def totals(plan):
        delivered=sum(q for r,qs in plan.items() for (p,_),q in zip(r.ops,qs) if p in sites)
        cost=sum(costs[r] for r in plan)
        return dict(delivered=delivered,cost=cost,ratio=cost/delivered)

    def vector(plan):
        v=np.zeros(model._h.getNumCol())
        for r,qs in plan.items():
            v[int(selected[r])]=1.
            v[[int(q) for q in quantities[r]]]=qs
        for opening,links in stock_links:
            level=opening
            for index,amounts in links:
                level-=v[amounts].sum()
                v[index]=level
        return v
    lp=model._h.getLp()
    data=lp.a_matrix_
    make_matrix=csc_matrix if data.format_==hs.MatrixFormat.kColwise else csr_matrix
    matrix=make_matrix((data.value_,data.index_,data.start_),shape=(lp.num_row_,lp.num_col_))
    audit=[]
    for path,plan in zip(paths,plans):
        v=vector(plan)
        ax=matrix@v
        residual=max(0.,max(np.asarray(lp.row_lower_)-ax),max(ax-np.asarray(lp.row_upper_)),max(np.asarray(lp.col_lower_)-v),max(v-np.asarray(lp.col_upper_)))
        if residual>1e-5:
            raise ValueError(f'original schedule fails pooled constraints by {residual} in {path}')
        audit.append(dict(source=path.name,max_violation=residual,**totals(plan)))
    best=plans[min(range(len(plans)),key=lambda i:audit[i]['ratio'])]
    def record(plan,stage):
        export(out,plan)
        if journal:
            with journal.open('a') as f:
                f.write(json.dumps(dict(stage=stage,elapsed_s=time.monotonic()-start,**totals(plan)))+'\n')
                f.flush()
                os.fsync(f.fileno())
    def accept(result):
        nonlocal best
        candidate={r:tuple(result.value(q) for q in quantities[r]) for r in routes if result.value(selected[r])>.5}
        if totals(candidate)['ratio']<totals(best)['ratio']-1e-12:
            best=candidate
            record(best,'improvement')
        return candidate
    record(best,'input')
    model.setStart(zip(model.getVars(),vector(best)))
    cost=quicksum(selected[r]*costs[r] for r in routes)
    amount=quicksum(q for visits in by_site.values() for _,q in visits)
    history=[]
    for _ in range(8):
        left=budget-(time.monotonic()-start)
        if left<=0:
            break
        ratio=totals(best)['ratio']
        model.setObjective(cost-ratio*amount)
        try:
            result=model.optimize(time_limit=left,mip_gap=0.,on_incumbent=accept if journal else None)
        except InconsistentObjective:
            history.append(dict(status='InconsistentObjectiveFallback'))
            break
        if not result.has_solution:
            break
        accept(result)
        score=totals(best)
        history.append(dict(status=result.status,seconds=time.monotonic()-start,**score))
        if ratio-score['ratio']<1e-10:
            break
        model.setStart(result)
    return dict(source_plans=audit,exchange_routes=len(exchanged),original_routes=original_count,window=window,extra_stops=extra_stops,replace_last=replace_last,frozen_routes=len(frozen),route_count=len(routes),nnz=matrix.nnz,cliques=cliques,offsets=list(offsets),rows=lp.num_row_,columns=lp.num_col_,
                **totals(best),history=history,wall_s=time.monotonic()-start)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('instance',type=Path)
    p.add_argument('plans',type=Path,nargs='+')
    p.add_argument('--seconds',type=float,default=120)
    p.add_argument('--offsets',type=int,nargs='*',default=[])
    p.add_argument('--cliques',action='store_true',help='use interval cliques plus event-indexed onboard inventory')
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--journal',type=Path,help='save improving native incumbents atomically during the search')
    p.add_argument('--window-days',type=int,nargs=2,metavar=('BEGIN','END'),help='freeze route times outside zero-based half-open day interval, with one complete input schedule')
    p.add_argument("--extra-stops",type=int,default=0,help="offer up to K nearby compatible additional final customers per original route and a shorter variant")
    p.add_argument("--replace-last",action="store_true",help="also offer a different compatible final unloading point for each removable final stop")
    p.add_argument("--pair-exchanges",type=int,default=0,help="retain K complete two-shift customer swaps per original shift")
    a=p.parse_args()
    if a.pair_exchanges<0:
        p.error("pair exchanges must be nonnegative")
    if a.replace_last and not a.extra_stops:
        p.error("last-stop replacement requires a positive candidate count")
    if a.extra_stops<0:
        p.error("extra stops must be nonnegative")
    print(json.dumps(optimize(a.instance,a.plans,a.output,a.seconds,a.offsets,a.cliques,a.journal,a.window_days,a.extra_stops,a.replace_last,a.pair_exchanges)))
