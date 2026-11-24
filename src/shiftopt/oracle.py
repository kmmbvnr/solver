"""A portable resource-price network trained from LP labels on example models."""
import json
from dataclasses import dataclass
from pathlib import Path
import numpy as np
from scipy.sparse import csr_matrix
from scipy.optimize import linprog


def features(values,usage,capacity):
    value=np.asarray(values,float)
    cap=np.asarray(capacity,float)
    A=csr_matrix(usage,dtype=float,copy=True)
    A.sum_duplicates()
    A.eliminate_zeros()
    counts=np.diff(A.indptr)
    row=np.repeat(np.arange(len(cap)),counts)
    ratios=np.maximum(0,value[A.indices])/A.data
    max_ratio=np.zeros(len(cap))
    np.maximum.at(max_ratio,row,ratios)
    avg=np.bincount(row,weights=ratios,minlength=len(cap))/np.maximum(1,counts)
    total=A.sum(axis=1).A1
    stats=np.column_stack([cap,counts,total,total/np.maximum(cap,1e-9),max_ratio,avg,
                           total/np.maximum(1,counts)])
    return np.log1p(stats)


@dataclass
class PriceOracle:
    """Predict nonnegative prices; train or fine-tune on lists of packing models."""
    first: np.ndarray
    bias: np.ndarray
    last: np.ndarray
    offset: float
    center: np.ndarray
    scale: np.ndarray

    def prices(self,values,usage,capacity):
        x=(features(values,usage,capacity)-self.center)/self.scale
        predicted=np.tanh(x@self.first+self.bias)@self.last+self.offset
        return np.expm1(np.clip(predicted,0,20))

    def save(self,path):
        np.savez(path,version=1,first=self.first,bias=self.bias,last=self.last,
                 offset=self.offset,center=self.center,scale=self.scale)

    @classmethod
    def load(cls,path):
        with np.load(path,allow_pickle=False) as a:
            if int(a['version'])!=1:
                raise ValueError("unknown oracle version")
            return cls(*(a[key].copy() for key in ['first','bias','last','offset','center','scale']))

    @classmethod
    def fit(cls,cases,*,previous=None,epochs=100,seed=0):
        xs,ys=[],[]
        for value,A,cap in cases:
            lp=linprog(-np.asarray(value),A_ub=A,b_ub=cap,bounds=(0,1),method='highs')
            if not lp.success:
                raise ValueError(lp.message)
            xs.append(features(value,A,cap))
            ys.append(np.log1p(np.maximum(0,-lp.ineqlin.marginals)))
        if not xs or epochs<1:
            raise ValueError("provide training cases and a positive epoch count")
        x,y=np.vstack(xs),np.concatenate(ys)
        rng=np.random.default_rng(seed)
        if previous is None:
            net=cls(rng.normal(0,.15,(x.shape[1],24)),np.zeros(24),rng.normal(0,.1,24),
                    float(np.mean(y)),x.mean(axis=0),np.maximum(x.std(axis=0),.01))
        else:
            net=cls(*(np.copy(getattr(previous,k)) for k in ['first','bias','last','offset','center','scale']))
        x=(x-net.center)/net.scale
        for epoch in range(epochs):
            for batch in np.array_split(rng.permutation(len(x)),max(1,len(x)//128)):
                hidden=np.tanh(x[batch]@net.first+net.bias)
                delta=np.clip(hidden@net.last+net.offset-y[batch],-1,1)/len(batch)
                dh=delta[:,None]*net.last*(1-hidden**2)
                net.first-=.025*x[batch].T@dh
                net.bias-=.025*dh.sum(axis=0)
                net.last-=.025*hidden.T@delta
                net.offset-=.025*delta.sum()
        return net


    @classmethod
    def fit_dual(cls,cases,*,previous=None,epochs=40,seed=0,recalibrate=False):
        """Learn prices by minimizing a smoothed packing upper bound, without LP labels."""
        data=[]
        stats=[]
        starts=[]
        for values,usage,capacity in cases:
            A=csr_matrix(usage,dtype=float,copy=True)
            A.sum_duplicates()
            A.eliminate_zeros()
            v=np.asarray(values,dtype=float)
            b=np.asarray(capacity,dtype=float)
            if (v.ndim!=1 or b.ndim!=1 or A.shape!=(len(b),len(v)) or not len(b)
                or not np.all(np.isfinite(v)) or not np.all(np.isfinite(b))
                or np.any(b<0) or not np.all(np.isfinite(A.data)) or np.any(A.data<0)):
                raise ValueError('invalid packing training case')
            f=features(v,A,b)
            stats.append(f)
            data.append((A,v,b,f))
            if A.nnz:
                starts.append(np.median(np.maximum(v[A.indices],0)/A.data)/max(1.,A.nnz/max(1,len(v))))
        if not data or epochs<1:
            raise ValueError('provide training cases and a positive epoch count')
        rng=np.random.default_rng(seed)
        if previous is None:
            x=np.vstack(stats)
            net=cls(rng.normal(0,.08,(x.shape[1],24)),np.zeros(24),rng.normal(0,.03,24),
                    np.log1p(np.median(starts) if starts else .1),x.mean(axis=0),np.maximum(x.std(axis=0),.01))
        else:
            net=cls(*(np.copy(getattr(previous,k)) for k in ['first','bias','last','offset','center','scale']))
        if previous is not None and recalibrate:
            x=np.vstack(stats)
            net.center=x.mean(axis=0)
            net.scale=np.maximum(x.std(axis=0),.01)
            hidden=np.tanh(((x-net.center)/net.scale)@net.first+net.bias)
            net.offset=np.log1p(np.median(starts) if starts else .1)-np.median(hidden@net.last)
        dataset=[(A,v,b,(f-net.center)/net.scale) for A,v,b,f in data]
        weights=[net.first,net.bias,net.last,np.asarray(net.offset).copy()]
        first_moment=[np.zeros_like(w) for w in weights]
        second_moment=[np.zeros_like(w) for w in weights]
        step=0
        for epoch in range(epochs):
            for i in rng.permutation(len(dataset)):
                A,v,b,x=dataset[i]
                h=np.tanh(x@weights[0]+weights[1])
                z=h@weights[2]+weights[3]
                p=np.expm1(np.clip(z,0,20))
                reduced=v-A.T@p
                positive=v[v>0]
                scale=np.median(positive) if len(positive) else 1.
                temp=max(1e-8,scale*(.002+.04*(1-epoch/epochs)))
                active=1/(1+np.exp(-np.clip(reduced/temp,-40,40)))
                dp=(b-A@active)/max(1.,positive.sum())
                dz=dp*(1+p)*((z>0)&(z<20))
                dh=dz[:,None]*weights[2]*(1-h*h)
                grads=(x.T@dh,dh.sum(axis=0),h.T@dz,dz.sum())
                step+=1
                for w,m,s,g in zip(weights,first_moment,second_moment,grads):
                    m*=.9
                    m+=.1*g
                    s*=.999
                    s+=.001*g*g
                    w-=.003*(m/(1-.9**step))/(np.sqrt(s/(1-.999**step))+1e-8)
        net.offset=float(weights[3])
        return net


def assess_prices(value,A,cap,prices):
    """U = cap.p + sum positive(v - A.T p) bounds every binary feasible profit."""
    prices=np.asarray(prices,float)
    if prices.shape!=np.shape(cap) or not np.all(np.isfinite(prices)) or np.any(prices<0):
        raise ValueError("expected one finite nonnegative price per resource")
    reduced=np.asarray(value)-A.T@prices
    return reduced,float(prices@cap+np.maximum(0,reduced).sum())
