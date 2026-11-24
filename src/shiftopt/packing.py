"""Maximize the value of a compatible subset of candidates under resource caps."""
from dataclasses import dataclass
from math import isfinite
import time
import numpy as np
from scipy.optimize import Bounds, LinearConstraint, linprog, milp
from scipy.sparse import csc_matrix


@dataclass(frozen=True)
class Selection:
    selected: tuple[int,...]
    value: float
    upper_bound: float | None
    status: str
    elapsed: float


def select_candidates(values,usage,capacity,*,time_limit=60.,mip_gap=.0001,on_solution=None,
                      strategy="full",rank_candidates=None,price_oracle=None):
    start=time.monotonic()
    value=np.asarray(values,dtype=float)
    cap=np.asarray(capacity,dtype=float)
    A=csc_matrix(usage,dtype=float,copy=True)
    A.sum_duplicates()
    A.eliminate_zeros()
    if value.ndim!=1 or cap.ndim!=1 or A.shape!=(len(cap),len(value)):
        raise ValueError("usage must have shape (resources, candidates)")
    if not np.all(np.isfinite(value)) or not np.all(np.isfinite(cap)) or not np.all(np.isfinite(A.data)):
        raise ValueError("values, usage and capacity must be finite")
    if np.any(cap<0) or np.any(A.data<0) or not isfinite(time_limit) or time_limit<0 or not 0<=mip_gap<1:
        raise ValueError("invalid nonnegative resource quantities or solve limits")
    if strategy not in ("full","pricing") or ((rank_candidates is not None or price_oracle is not None) and strategy!="pricing"):
        raise ValueError("rank_candidates requires pricing; strategy must be full or pricing")
    remaining=cap.copy()
    chosen=[]
    for j in np.argsort(-value,kind='stable'):
        if value[j]<=0 or time.monotonic()-start>=time_limit:
            break
        sl=slice(A.indptr[j],A.indptr[j+1])
        idx=A.indices[sl]
        if np.all(remaining[idx]>=A.data[sl]):
            remaining[idx]-=A.data[sl]
            chosen.append(int(j))
    trivial_bound=float(value[value>0].sum())
    def result(ids,bound,status):
        return Selection(tuple(ids),float(value[list(ids)].sum()),bound,status,time.monotonic()-start)
    best=result(chosen,trivial_bound,"Feasible")
    if on_solution:
        on_solution(best)
    if best.value==trivial_bound:
        return result(chosen,trivial_bound,"Optimal")
    left=time_limit-(time.monotonic()-start)
    if left<=0:
        return result(chosen,trivial_bound,"TimeLimit")
    ids=np.arange(len(value))
    upper=trivial_bound
    restricted=False
    if strategy=="pricing" and chosen:
        active=np.zeros(len(value),dtype=bool)
        active[chosen]=True
        # Include free columns in the initial master. Binary upper bounds keep
        # the LP bounded for resources with no usage.
        active[(np.diff(A.indptr)==0)&(value>0)]=True
        if price_oracle is not None:
            from .oracle import assess_prices
            prices=price_oracle.prices(value,A,cap)
            reduced,predicted_bound=assess_prices(value,A,cap,prices)
            upper=min(upper,predicted_bound)
            count=max(32,int(np.sqrt(len(value))))
            active[np.argsort(-reduced,kind="stable")[:count]]=True
        pricing_end=start+time_limit*.5
        for _ in range(32):
            left=pricing_end-time.monotonic()
            if left<=0 or np.all(active):
                break
            lp=linprog(-value[active],A_ub=A[:,active],b_ub=cap,bounds=(0,1),
                       method='highs',options={'time_limit':left})
            if not lp.success:
                break
            prices=np.maximum(0,-lp.ineqlin.marginals)
            reduced=value-A.T@prices
            # Weak duality: each binary column contributes at most its
            # positive reduced benefit, also for columns outside the master.
            upper=min(upper,float(cap@prices+np.maximum(0,reduced).sum()))
            missing=np.flatnonzero((~active)&(reduced>1e-8))
            if not len(missing):
                break
            score=reduced if rank_candidates is None else np.asarray(rank_candidates(reduced.copy()),dtype=float)
            if score.shape!=value.shape or not np.all(np.isfinite(score)):
                raise ValueError("oracle must return one finite priority per candidate")
            take=max(32,int(np.sqrt(len(value))))
            order=missing[np.argsort(-score[missing],kind='stable')[:take]]
            active[order]=True
        ids=ids[active]
        restricted=len(ids)<len(value)
    left=time_limit-(time.monotonic()-start)
    if left<=0:
        return result(chosen,upper,"TimeLimit")
    res=milp(-value[ids],integrality=np.ones(len(ids)),bounds=Bounds(0,1),
             constraints=LinearConstraint(A[:,ids],-np.inf,cap),
             options={'time_limit':left,'mip_rel_gap':mip_gap})
    dual=getattr(res,'mip_dual_bound',None)
    if not restricted and dual is not None and np.isfinite(dual):
        upper=min(upper,-float(dual))
    if res.x is not None:
        proposed=ids[res.x>.5]
        if np.all(A[:,proposed].sum(axis=1).A1<=cap+1e-7) and sum(value[proposed])>best.value:
            chosen=tuple(map(int,proposed))
            if on_solution:
                on_solution(result(chosen,upper,"Feasible"))
    status={0:"Optimal",1:"Limit",4:"SolverError"}.get(res.status,"SolverError")
    if restricted:
        status="Feasible" if status=="Optimal" else status
        left=time_limit-(time.monotonic()-start)
        if left>0 and upper>float(value[list(chosen)].sum())+1e-7:
            # Zero reduced cost can hide useful integer columns. Spend any
            # remaining time searching the original model and retain the incumbent.
            full=milp(-value,integrality=np.ones(len(value)),bounds=Bounds(0,1),
                      constraints=LinearConstraint(A,-np.inf,cap),
                      options={'time_limit':left,'mip_rel_gap':mip_gap})
            bound=getattr(full,'mip_dual_bound',None)
            if bound is not None and np.isfinite(bound):
                upper=min(upper,-float(bound))
            if full.x is not None:
                proposed=np.flatnonzero(full.x>.5)
                if value[proposed].sum()>value[list(chosen)].sum() and np.all(A[:,proposed].sum(axis=1).A1<=cap+1e-7):
                    chosen=tuple(map(int,proposed))
                    if on_solution:
                        on_solution(result(chosen,upper,"Feasible"))
            if full.status==0:
                status="Optimal"
    return result(chosen,max(upper,float(value[list(chosen)].sum())),status)
