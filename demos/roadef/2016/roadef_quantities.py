"""Optimize all delivery quantities together on a timed multi-source ROADEF schedule."""
import argparse
from collections import defaultdict
import json
from pathlib import Path
import time
import xml.etree.ElementTree as ET

import numpy as np
from scipy.optimize import linprog
from scipy.sparse import coo_matrix


def optimize(instance, seed, output):
    begin=time.monotonic()
    problem=ET.parse(instance).getroot()
    plan=ET.parse(seed)
    unit=int(problem.findtext('unit'))
    sources={int(s.findtext('index')) for s in problem.find('sources')}
    customers={int(c.findtext('index')):c for c in problem.find('customers')}
    trailers=list(problem.find('trailers'))
    bounds=[]
    objective=[]
    quantities=[]
    events=defaultdict(list)
    by_vehicle=defaultdict(list)
    for shift in plan.getroot().find('Shifts'):
        k=int(shift.findtext('trailer'))
        for op in shift.find('operations'):
            point=int(op.findtext('point'))
            at=int(op.findtext('arrival'))
            old=float(op.findtext('Quantity'))
            j=len(quantities)
            quantities.append((op,old))
            by_vehicle[k].append((at,j))
            if point in sources:
                bounds.append((-float(trailers[k].findtext('Capacity')),0.))
                objective.append(0.)
            else:
                c=customers[point]
                events[point].append((at,j))
                floor=0. if int(c.findtext('callIn')) else float(c.findtext('MinOperationQuantity'))
                bounds.append((floor,None))
                objective.append(-1.)
    rows=[]
    cols=[]
    data=[]
    limits=[]

    def limit(ids,lo,hi):
        for sign,rhs in [(-1,-lo),(1,hi)]:
            rows.extend([len(limits)]*len(ids))
            cols.extend(ids)
            data.extend([sign]*len(ids))
            limits.append(rhs)

    for k,stops in by_vehicle.items():
        # A trailer can carry product across shifts, including shifts without a reload.
        opening=float(trailers[k].findtext('InitialQuantity'))
        cap=float(trailers[k].findtext('Capacity'))
        prefix=[]
        for _,j in sorted(stops):
            prefix.append(j)
            limit(prefix,opening-cap,opening)
    for point,c in customers.items():
        visits=sorted(events[point])
        if int(c.findtext('callIn')):
            used=[]
            for order in c.find('orders'):
                a=int(order.findtext('earliestTime'))
                b=int(order.findtext('latestTime'))
                ids=[j for at,j in visits if a<=at<=b]
                target=float(order.findtext('Quantity'))
                limit(ids,target*float(order.findtext('orderQuantityFlexibility'))/100.,target)
                used.extend(ids)
            if sorted(used)!=sorted(j for _,j in visits):
                raise ValueError('a call-in visit does not match exactly one order')
        else:
            cumulative=np.cumsum([float(v.text) for v in c.find('Forecast')])
            opening=float(c.findtext('InitialTankQuantity'))
            cap=float(c.findtext('Capacity'))
            floor=float(c.findtext('SafetyLevel'))
            by_tick=defaultdict(list)
            for at,j in visits:
                by_tick[at//unit].append(j)
            ticks=sorted(set([0,*by_tick]))
            prefix=[]
            for h,next_h in zip(ticks,ticks[1:]+[len(cumulative)]):
                prefix.extend(by_tick[h])
                # Inventory declines between visits. Endpoints bound every intermediate tick.
                limit(prefix,floor-opening+cumulative[next_h-1],cap-opening+cumulative[h])
    A=coo_matrix((data,(rows,cols)),shape=(len(limits),len(bounds))).tocsc()
    lp=linprog(objective,A_ub=A,b_ub=limits,bounds=bounds,method='highs')
    if not lp.success:
        raise ValueError(lp.message)
    baseline=-np.dot(objective,[v for _,v in quantities])
    if -lp.fun<baseline-1e-5:
        raise ValueError('warm schedule violates quantity model')
    for (op,_),v in zip(quantities,lp.x):
        op.find('Quantity').text=f'{v:.8f}'
    plan.write(output,encoding='utf-8',xml_declaration=True)
    return dict(start_kg=baseline,optimized_kg=-lp.fun,quantity_variables=len(bounds),
                inequalities=A.shape[0],seconds=time.monotonic()-begin)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('instance',type=Path)
    p.add_argument('seed',type=Path)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    print(json.dumps(optimize(a.instance,a.seed,a.output)))
