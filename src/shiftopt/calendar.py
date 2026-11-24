"""Filter starts of interval jobs against a fixed partial schedule."""
import ctypes
from pathlib import Path
import operator
import numpy as np


def _integers(values,dtype,name):
    raw=np.asarray(values)
    limit=np.iinfo(dtype).max
    if raw.size and (raw.dtype.kind not in 'iu' or np.any(raw<0) or np.any(raw>limit)):
        raise ValueError(f'{name} must contain nonnegative integers within {dtype}')
    return np.ascontiguousarray(raw,dtype=dtype)


class Calendar:
    """A template reserves (resource, start, end, units) intervals and optional supplies.

    Intervals are half-open and relative to a candidate's departure. eligible() returns
    original indices of candidates that can each be added to the fixed assignments.
    """

    def __init__(self,capacity,templates,candidate_templates,starts,*,stock=(),consumption=None,library=None):
        self.capacity=_integers(capacity,np.int32,'capacity').copy()
        if self.capacity.ndim!=2 or self.capacity.shape[1]<1:
            raise ValueError('capacity must be resources by time, with at least one time slot')
        resources,self.horizon=self.capacity.shape
        self.stock=np.array(stock,dtype=float,copy=True,order='C')
        if self.stock.ndim!=1 or not np.isfinite(self.stock).all() or (self.stock<0).any():
            raise ValueError('stock must be a nonnegative finite vector')
        templates=list(templates)
        if consumption is None:
            consumption=[()] * len(templates)
        if len(consumption)!=len(templates):
            raise ValueError('consumption must have one list of (stock index, amount) per template')
        windows={}
        segments=[]
        lengths=[]
        segment_offsets=[0]
        stock_offsets=[0]
        stock_ids=[]
        amounts=[]
        for intervals,usage in zip(templates,consumption):
            events={}
            length=0
            for row in intervals:
                resource,begin,end,units=map(operator.index,row)
                if not (0<=resource<resources and 0<=begin<end<=self.horizon and 0<units<=2**31-1):
                    raise ValueError('invalid interval')
                changes=events.setdefault(resource,{})
                changes[begin]=changes.get(begin,0)+units
                changes[end]=changes.get(end,0)-units
                length=max(length,end)
            for resource,changes in sorted(events.items()):
                occupied=first=0
                for tick,delta in sorted(changes.items()):
                    if not delta:
                        continue
                    if occupied:
                        if occupied>2**31-1:
                            raise ValueError('overlapping demands exceed supported range')
                        key=(resource,tick-first,occupied)
                        segments.append((windows.setdefault(key,len(windows)),first))
                    occupied+=delta
                    first=tick
            totals={}
            for i,amount in usage:
                i=operator.index(i)
                if not 0<=i<len(self.stock) or not np.isfinite(amount) or amount<0:
                    raise ValueError('invalid consumable resource demand')
                totals[i]=totals.get(i,0.)+float(amount)
                if not np.isfinite(totals[i]):
                    raise ValueError('consumable resource demand exceeds supported range')
            for i,q in sorted(totals.items()):
                if q:
                    stock_ids.append(i)
                    amounts.append(q)
            lengths.append(length)
            segment_offsets.append(len(segments))
            stock_offsets.append(len(stock_ids))
        self.windows=np.array(list(windows),np.int32).reshape(-1,3)
        self.segments=np.array(segments,np.int32).reshape(-1,2)
        self.segment_offsets=np.array(segment_offsets,np.int64)
        self.stock_offsets=np.array(stock_offsets,np.int64)
        self.stock_ids=np.array(stock_ids,np.int32)
        self.amounts=np.array(amounts,float)
        types=_integers(candidate_templates,np.int32,'candidate templates')
        times=_integers(starts,np.int32,'starts')
        if (types.ndim!=1 or times.shape!=types.shape or np.any(types>=len(templates)) or
            np.any(times>=self.horizon) or np.any(times.astype(np.int64)+np.array(lengths,np.int64)[types]>self.horizon)):
            raise ValueError('invalid candidate, or interval outside calendar')
        self.order=None
        if np.any(types[1:]<types[:-1]):
            self.order=np.argsort(types,kind='stable')
            self.inverse=np.empty_like(self.order)
            self.inverse[self.order]=np.arange(len(types))
            types,times=types[self.order],times[self.order]
        self.types=types.copy()
        self.starts=times.copy()
        self.offsets=np.searchsorted(types,np.arange(len(templates)+1)).astype(np.int64)
        self.kernel=None
        if library is not None:
            self.lib=ctypes.CDLL(str(Path(library).resolve()))
            self.kernel=self.lib.filter_calendar
            i32=np.ctypeslib.ndpointer(dtype=np.int32,flags='C_CONTIGUOUS')
            i64=np.ctypeslib.ndpointer(dtype=np.int64,flags='C_CONTIGUOUS')
            f64=np.ctypeslib.ndpointer(dtype=np.float64,flags='C_CONTIGUOUS')
            self.kernel.argtypes=[*[ctypes.c_size_t]*8,i32,i32,i64,i32,i64,i32,f64,f64,i64,i32,i32,i64,i32]
            self.kernel.restype=ctypes.c_int64
            if self.horizon>128:
                # Early libraries implemented one 128-bit word. An empty schedule is always feasible.
                i=np.empty(0,np.int32)
                offsets=np.zeros(1,np.int64)
                f=np.empty(0,np.float64)
                supports=self.kernel(0,self.horizon,0,0,0,0,0,0,i,i,offsets,i,offsets,i,f,f,offsets,i,i,offsets,i)
                if supports<0:
                    self.kernel=None

    @property
    def backend(self):
        return 'rust' if self.kernel is not None else 'python'

    def eligible(self,locked=(),*,include_locked=False):
        fixed=_integers(locked,np.int64,'locked candidates')
        if fixed.ndim!=1 or np.any(fixed>=len(self.types)) or len(fixed)!=len(np.unique(fixed)):
            raise ValueError('locked candidate indices must be valid and distinct')
        if self.order is not None:
            fixed=self.inverse[fixed]
        if self.kernel is None:
            ids=self._portable(fixed)
        else:
            out=np.empty(len(self.types),np.int32)
            count=self.kernel(len(self.capacity),self.horizon,len(self.offsets)-1,len(self.types),
                              len(self.windows),len(self.stock),len(fixed),int(include_locked),
                              self.capacity,self.windows,self.segment_offsets,self.segments,self.stock_offsets,
                              self.stock_ids,self.amounts,self.stock,self.offsets,self.types,self.starts,fixed,out)
            if count<0:
                raise ValueError('locked schedule exceeds capacity or stock')
            ids=out[:count]
        if self.kernel is None:
            ids=(np.union1d(ids,fixed) if include_locked else np.setdiff1d(ids,fixed,assume_unique=True))
        return ids if self.order is None else np.sort(self.order[ids])

    def _portable(self,fixed):
        remaining=self.capacity.astype(np.int64)
        stock=self.stock.copy()
        for j in fixed:
            a,t=self.types[j],self.starts[j]
            for w,b in self.segments[self.segment_offsets[a]:self.segment_offsets[a+1]]:
                r,d,u=self.windows[w]
                remaining[r,t+b:t+b+d]-=u
            sl=slice(self.stock_offsets[a],self.stock_offsets[a+1])
            stock[self.stock_ids[sl]]-=self.amounts[sl]
        if np.any(remaining<0) or np.any(stock < -1e-9):
            raise ValueError('locked schedule exceeds capacity or stock')
        masks=[]
        for r,d,u in self.windows:
            available=int.from_bytes(np.packbits(remaining[r]>=u,bitorder='little').tobytes(),'little')
            valid=available
            for i in range(1,d):
                valid &= available>>i
            masks.append(valid)
        possible=[]
        for a,(first,last) in enumerate(zip(self.offsets,self.offsets[1:])):
            sl=slice(self.stock_offsets[a],self.stock_offsets[a+1])
            if np.any(self.amounts[sl]>stock[self.stock_ids[sl]]+1e-9):
                continue
            bits=(1<<self.horizon)-1
            for w,b in self.segments[self.segment_offsets[a]:self.segment_offsets[a+1]]:
                bits &= masks[w]>>int(b)
            if bits:
                possible.extend(j for j in range(first,last) if bits>>int(self.starts[j])&1)
        return np.asarray(possible,np.int64)
