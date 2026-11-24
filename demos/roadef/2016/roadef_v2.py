"""Select multi-source shifts for ROADEF V2 with call-in orders and opening hours."""
from dataclasses import dataclass
import itertools
import xml.etree.ElementTree as ET

from numba import njit
import numpy as np
from instance_xml import table


def read(path,fraction,spacing,allow_layovers=False,choose_trailers=False,day_drivers=0,align_windows=False,adaptive_parcels=False,stagger_daily=False):
    root=ET.parse(path).getroot()
    drivers=list(root.find('drivers'))
    trailers=list(root.find('trailers'))
    sources=list(root.find('sources'))
    clients=list(root.find('customers'))
    unit=int(root.findtext('unit'))
    H=int(root.findtext('horizon'))
    end=H*unit
    caps=np.array([float(t.findtext('Capacity')) for t in trailers])
    slots=[]
    def windows(obj):
        return [(int(w.findtext('start')),int(w.findtext('end'))) for w in obj.find('timewindows')]
    fixed={}
    if choose_trailers:
        from scipy.optimize import linear_sum_assignment
        copies=max(1,len(drivers))
        weights=np.full((len(drivers),len(trailers)*copies),1e12)
        access=np.zeros(len(trailers))
        for c in clients:
            permitted=[int(v.text) for v in c.find('allowedTrailers')]
            access[permitted]+=1./len(permitted)
        for d,driver in enumerate(drivers):
            for k in (int(v.text) for v in driver.find('trailer')):
                for j in range(copies):
                    weights[d,j*len(trailers)+k]=1e5*j-access[k]-caps[k]/1e5
        rows,cols=linear_sum_assignment(weights)
        fixed={int(d):int(c%len(trailers)) for d,c in zip(rows,cols)}
    for d,driver in enumerate(drivers):
        fleet=[int(v.text) for v in driver.find('trailer')]
        if d in fixed:
            fleet=[fixed[d]]
        if len(fleet)!=1:
            raise ValueError('this experiment requires a dedicated trailer per driver')
        k=fleet[0]
        rest=int(driver.findtext('minInterSHIFTDURATION'))
        interval=min(1440,spacing) if d<day_drivers else spacing
        if rest>=interval:
            raise ValueError('driver rest exceeds slot spacing')
        phase=d*interval//len(drivers)
        for left,right in windows(driver):
            initial_slot=left if align_windows else phase-interval
            if stagger_daily and d<day_drivers:
                initial_slot=left+d*interval//day_drivers-interval
            for t in range(initial_slot,right,interval):
                begin=max(left,t)
                finish=min(right,t+interval-rest)
                if finish-begin>0:
                    slots.append([begin,finish,d,k])
    slots.sort()
    for key in (2,3):
        for owner in set(s[key] for s in slots):
            assigned=[s for s in slots if s[key]==owner]
            for a,b in zip(assigned,assigned[1:]):
                rest=int(drivers[owner].findtext('minInterSHIFTDURATION')) if key==2 else 0
                a[1]=min(a[1],b[0]-rest)
    slots=np.array([s for s in slots if s[1]>s[0]],int)
    source_ok=np.zeros((len(sources),len(trailers)),dtype=bool)
    for s,src in enumerate(sources):
        if int(src.findtext('index'))!=s+1:
            raise ValueError('expected ordered source point IDs')
        source_ok[s,[int(v.text) for v in src.find('allowedTrailers')]]=True
    owners=[]
    needs=[]
    required=[]
    rooms=[]
    starts=[]
    compatibility=[]
    setups=[]
    nights=[]
    horizon=np.arange(end,dtype=np.int32)
    for c in clients:
        point=int(c.findtext('index'))
        night=bool(int(c.findtext('LayoverCustomer')))
        if night and not allow_layovers:
            raise ValueError('mandatory layovers require a different shift generator')
        setup=int(c.findtext('setupTime'))
        allow=[int(v.text) for v in c.find('allowedTrailers')]
        cap=float(c.findtext('Capacity'))
        safety=float(c.findtext('SafetyLevel'))
        opening=float(c.findtext('InitialTankQuantity'))
        forecast=np.array([float(v.text) for v in c.find('Forecast')])
        during=np.cumsum(forecast)
        before=np.r_[0.,during[:-1]]
        jobs=[]
        if int(c.findtext('callIn')):
            for order in c.find('orders'):
                q=float(order.findtext('Quantity'))
                minimum=q*float(order.findtext('orderQuantityFlexibility'))/100.
                pieces=max(1,int(np.ceil(minimum/max(caps[allow]))))
                for _ in range(pieces):
                    jobs.append((True,minimum/pieces,np.full(H,q/pieces),int(order.findtext('earliestTime')),
                                 int(order.findtext('latestTime')),H-1))
        else:
            min_op=float(c.findtext('MinOperationQuantity'))
            required_total=max(0.,during[-1]+safety-opening)
            payload=min(max(caps[allow]),cap-safety)
            pieces=max(1,int(np.ceil(required_total/(fraction*payload)))) if payload>0 else 1
            def parcels(count):
                lot=max(min_op,required_total/count)
                deliveries=[]
                for j in range(count):
                    prior=j*lot
                    short=np.flatnonzero(opening+prior-during<safety-1e-8)
                    deadline=int(short[0]) if len(short) else H-1
                    available=cap-opening+before-prior
                    if j+1<count:
                        available=np.minimum(available,lot)
                    deliveries.append((required_total>1e-6,lot,available,0,end,deadline))
                return deliveries
            jobs=parcels(pieces)
            if adaptive_parcels and required_total>1e-6:
                # Try nearby visit counts separately for this tank. Keep its full physical demand.
                # Favor broad legal service windows and avoid extra visits when the windows are ample.
                service=np.zeros(end,bool)
                for begin,finish in windows(c):
                    last=min(end-1,finish-setup)
                    if last>=max(0,begin):
                        service[max(0,begin):last+1]=True
                minutes=np.bincount((horizon//unit)[service],minlength=H)
                def rank_parcels(proposal):
                    slots_seen=[]
                    for _,q,room,_,_,last in proposal:
                        compatible_vehicle=np.any(caps[allow]+1e-7>=q)
                        valid=(room[:last+1]+1e-7>=q)
                        slots_seen.append(float(minutes[:last+1][valid].sum()) if compatible_vehicle else 0.)
                    worst=min(slots_seen)
                    return (worst>0,min(worst,1440.)/(1+.08*len(proposal)),
                            -abs(len(proposal)-pieces),np.mean(np.log1p(slots_seen)))
                for count in range(max(1,pieces-3),pieces+5):
                    proposal=parcels(count)
                    if rank_parcels(proposal)>rank_parcels(jobs):
                        jobs=proposal
        for must,q,room,earliest,latest,deadline in jobs:
            valid=np.zeros(end,dtype=bool)
            for begin,finish in windows(c):
                lo=max(begin,earliest,0)
                hi=min(finish,latest,end)-setup
                if hi>=lo:
                    valid[lo:hi+1]=True
            valid &= (horizon//unit<=deadline)&(room[horizon//unit]+1e-7>=q)
            starts.append(np.minimum.accumulate(np.where(valid,horizon,end+1)[::-1])[::-1])
            owners.append(point)
            needs.append(q)
            required.append(must)
            rooms.append(room)
            mask=np.zeros(len(trailers),dtype=bool)
            mask[allow]=True
            compatibility.append(mask)
            setups.append(setup)
            nights.append(night)
    return dict(n=len(owners),original=len(clients),unit=unit,horizon=H,slots=slots,windows=slots[:,:2],
        owner=np.array(owners),minimum=np.array(needs),need=np.where(required,np.array(needs),0.),
        earliest=np.array(starts,np.int32),room=np.array(rooms),setup=np.array(setups,dtype=int),
        night=np.array(nights,dtype=bool),rest_length=np.array([int(drivers[d].findtext('LayoverDuration')) for _,_,d,_ in slots]),
        rest_cost=np.array([float(drivers[d].findtext('LayoverCost')) for _,_,d,_ in slots]),
        compatible=np.array(compatibility).T,source_ok=source_ok,truck_caps=caps,
        fills=np.array([int(src.findtext('setupTime')) for src in sources]),
        travel=table(root,'timeMatrices').astype(int),dist=table(root,'DistMatrices'),
        opening=np.array([float(v.findtext('InitialQuantity')) for v in trailers]),
        maxdrive=np.array([int(drivers[d].findtext('maxDrivingDuration')) for _,_,d,k in slots]),
        time_cost=np.array([float(drivers[d].findtext('TimeCost')) for _,_,d,k in slots]),
        km_cost=np.array([float(trailers[k].findtext('DistanceCost')) for _,_,d,k in slots]))


@njit(cache=True)
def evaluate(groups,perms,slots,owner,qmin,room,setup,earliest,vehicle_ok,source_ok,fills,unit,
             travel,dist,capacity,maxdrive,time_cost,km_cost,ratio,delays,night,rest_length,rest_cost):
    W=len(slots)
    G=len(groups)
    cost=np.full((W,G),np.inf)
    choice=np.full((W,G),-1,np.int32)
    for w in range(W):
        begin,end,driver,k=slots[w]
        for g in range(G):
            row=groups[g]
            size=np.count_nonzero(row>=0)
            qty=0.
            valid=True
            for s in row[:size]:
                qty+=qmin[s]
                if not vehicle_ok[k,s]:
                    valid=False
            if not valid or qty>capacity[k]+1e-7:
                continue
            for src in range(len(fills)):
                if not source_ok[src,k]:
                    continue
                for off,delay in enumerate(delays):
                    start=begin+delay
                    if start>=end:
                        continue
                    for p in range((1,1,2,6,24)[size]):
                        night_route=False
                        for site in row[:size]:
                            night_route |= night[site]
                        for rest_at in range(0 if night_route else -1,size if night_route else 0):
                            prev=src+1
                            drv=travel[0,prev]
                            t=start+drv+fills[src]
                            km=dist[0,prev]
                            upper=0.
                            viable=drv<=maxdrive[w]
                            for pos in range(size):
                                s=row[perms[size,p,pos]]
                                node=owner[s]
                                leg=travel[prev,node]
                                reach=t+leg
                                pause=rest_length[w] if pos==rest_at else 0
                                at=reach+pause
                                drv=max(0,drv+leg-maxdrive[w]) if pos==rest_at else drv+leg
                                if at>=end or at>=earliest.shape[1] or drv>maxdrive[w]:
                                    viable=False
                                    break
                                at=earliest[s,at]
                                if at+setup[s]>end or (pos!=rest_at and at-reach>=rest_length[w]):
                                    viable=False
                                    break
                                upper+=room[s,at//unit]
                                km+=dist[prev,node]
                                prev=node
                                t=at+setup[s]
                            if viable and t+travel[prev,0]<=end and drv+travel[prev,0]<=maxdrive[w]:
                                kg=min(capacity[k],upper)
                                if kg<1e-8:
                                    continue
                                duration=t+travel[prev,0]-start
                                price=(km+dist[prev,0])*km_cost[w]+duration*time_cost[w]-ratio*kg
                                if night_route:
                                    price+=rest_cost[w]-rest_length[w]*time_cost[w]
                                if price<cost[w,g]:
                                    cost[w,g]=price
                                    choice[w,g]=((src*len(delays)+off)*24+p)*5+rest_at+1
    return cost,choice


@dataclass
class Tour:
    order: tuple
    arrival: list
    shipments: list
    cost: float
    kg: float
    start: int
    source: int


def build_oracles(x,groups,perms,delays):
    def block(rows,windows,ratio):
        return evaluate(rows,perms,x['slots'][windows],x['owner'],x['minimum'],x['room'],x['setup'],
             x['earliest'],x['compatible'],x['source_ok'],x['fills'],x['unit'],x['travel'],x['dist'],
             x['truck_caps'],x['maxdrive'][windows],x['time_cost'][windows],x['km_cost'][windows],ratio,delays,
             x['night'],x['rest_length'][windows],x['rest_cost'][windows])
    def score(ratio):
        if 'window_offsets' not in x:
            return block(groups,slice(None),ratio)
        offsets=x['window_offsets']
        cost=np.empty((1,len(groups)))
        order=np.empty((1,len(groups)),np.int32)
        for w,(begin,end) in enumerate(zip(offsets,offsets[1:])):
            if begin<end:
                cost[:,begin:end],order[:,begin:end]=block(groups[begin:end],slice(w,w+1),ratio)
        return cost,order
    def restore(w,row,code):
        travel_code,pause_code=divmod(int(code),5)
        rest_at=pause_code-1
        route_id,p=divmod(travel_code,24)
        src,off=divmod(route_id,len(delays))
        k=x['slots'][w,3]
        previous=src+1
        start=int(x['slots'][w,0]+delays[off])
        t=start+x['travel'][0,previous]+x['fills'][src]
        km=x['dist'][0,previous]
        length=np.count_nonzero(row>=0)
        route=tuple(int(i) for i in row[perms[length,p,:length]])
        at=[]
        room=[]
        for pos,s in enumerate(route):
            if pos==rest_at:
                t+=x['rest_length'][w]
            node=x['owner'][s]
            time_at=x['earliest'][s,t+x['travel'][previous,node]]
            at.append(int(time_at))
            room.append(x['room'][s,time_at//x['unit']])
            km+=x['dist'][previous,node]
            previous=node
            t=time_at+x['setup'][s]
        quantities=x['minimum'][list(route)].copy()
        extra=min(x['truck_caps'][k],sum(room))-quantities.sum()
        for i,r in enumerate(room):
            add=max(0,min(r-quantities[i],extra))
            quantities[i]+=add
            extra-=add
        cost=(km+x['dist'][previous,0])*x['km_cost'][w]+(t+x['travel'][previous,0]-start)*x['time_cost'][w]
        if rest_at>=0:
            cost+=x['rest_cost'][w]-x['rest_length'][w]*x['time_cost'][w]
        return Tour(route,at,quantities.tolist(),float(cost),float(quantities.sum()),start,src+1)
    return score,restore


def export(path,x,plan):
    root=ET.Element('IRP_Roadef_Challenge_Output')
    shifts=ET.SubElement(root,'Shifts')
    remaining=x['opening'].copy()
    for idx,(w,r) in enumerate(sorted(plan,key=lambda pair:pair[1].start)):
        _,_,d,k=x['slots'][w]
        shift=ET.SubElement(shifts,'IRP_Roadef_Challenge_Shift_')
        for name,value in [('index',idx),('driver',d),('trailer',k),('start',r.start)]:
            ET.SubElement(shift,name).text=str(value)
        ops=ET.SubElement(shift,'operations')
        load=remaining[k]-x['truck_caps'][k]
        seq=[(r.source,r.start+x['travel'][0,r.source],load)] if load < -1e-8 else []
        seq.extend((x['owner'][s],t,q) for s,t,q in zip(r.order,r.arrival,r.shipments))
        for point,at,q in seq:
            op=ET.SubElement(ops,'IRP_Roadef_Challenge_Operation_')
            for key,v in [('point',point),('arrival',at),('Quantity',q)]:
                ET.SubElement(op,key).text=str(v)
        remaining[k]=x['truck_caps'][k]-r.kg
    ET.indent(root)
    ET.ElementTree(root).write(path,encoding='utf-8',xml_declaration=True)


def subsets(sites,max_stops):
    blocks=[]
    permutations=np.full((max_stops+1,24,max_stops),-1,dtype=np.int8)
    for k in range(1,max_stops+1):
        group=np.array(list(itertools.combinations(sorted(sites),k)),dtype=np.int16).reshape(-1,k)
        blocks.append(np.pad(group,((0,0),(0,max_stops-k)),constant_values=-1))
        for i,order in enumerate(itertools.permutations(range(k))):
            permutations[k,i,:k]=order
    return np.vstack(blocks),permutations
