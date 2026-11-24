"""Thin modelling interface to the native HiGHS LP/MIP solver."""
from dataclasses import dataclass, field
from math import inf, isfinite, isnan
import time
import numpy as np
import highspy as hs

MINIMIZE=hs.ObjSense.kMinimize
MAXIMIZE=hs.ObjSense.kMaximize
quicksum=hs.Highs.qsum


def _belongs_to(variable,model):
    try:
        return getattr(variable,'highs',None)==model
    except ReferenceError:
        # HiGHS handles keep only a weak reference to their originating model.
        return False


class InconsistentObjective(RuntimeError):
    """The reported objective does not match the returned linear solution."""


def _run_checked(highs, seconds):
    """Replay a linear objective before accepting a native solve certificate."""
    start=time.monotonic()
    if highs.run()==hs.HighsStatus.kError:
        raise RuntimeError("HiGHS failed to solve the model")
    if highs.getHessianNumNz() or highs.getNumLinearObjectives():
        return False
    def consistent():
        solution=highs.getSolution()
        if highs.getInfo().primal_solution_status!=hs.SolutionStatus.kSolutionStatusFeasible:
            return highs.getModelStatus()!=hs.HighsModelStatus.kOptimal
        model=highs.getLp()
        actual=np.dot(model.col_cost_,solution.col_value)+model.offset_
        return abs(actual-highs.getObjectiveValue())<=1e-5+1e-12*abs(actual)
    if consistent():
        return False
    remaining=seconds-(time.monotonic()-start)
    if remaining<=0:
        raise InconsistentObjective("HiGHS returned an inconsistent objective at timeout")
    # Reproduced with a valid start and presolve on a replenishment MIP.
    presolve=highs.getOptionValue("presolve")[1]
    limit=highs.getOptionValue("time_limit")[1]
    try:
        highs.clearSolver()
        highs.setOptionValue("presolve","off")
        highs.setOptionValue("time_limit",remaining)
        if highs.run()==hs.HighsStatus.kError:
            raise RuntimeError("HiGHS failed to solve the model")
        if not consistent():
            raise InconsistentObjective("HiGHS objective disagrees with the returned solution")
    finally:
        highs.setOptionValue("presolve",presolve)
        highs.setOptionValue("time_limit",limit)
    return True


@dataclass(frozen=True)
class Solution:
    status: str
    objective: float | None
    values: tuple[float,...]
    bound: float | None
    gap: float | None
    _owner: object = field(repr=False, compare=False)

    @property
    def has_solution(self):
        return self.objective is not None

    def value(self,var):
        if not self.has_solution:
            raise ValueError(f"No feasible solution ({self.status})")
        if not _belongs_to(var,self._owner):
            raise ValueError("Variable belongs to another model")
        return self.values[int(var)]


class Model:
    def __init__(self,*,threads=None):
        if threads is not None and (type(threads)!=int or not 1<=threads<=2147483647):
            raise ValueError('threads must be a positive integer')
        self._h=hs.Highs()
        if threads is not None:
            self._h.setOptionValue('threads',threads)
        self._h.setOptionValue("output_flag",False)

    def addVar(self,lb=0.,ub=inf,vtype="C",name=None):
        if vtype not in ("B","I","C"):
            raise ValueError("vtype must be B, I or C")
        if vtype=="B":
            lb,ub=max(lb,0.),min(ub,1.)
        if isnan(lb) or isnan(ub) or lb>ub:
            raise ValueError("invalid bounds")
        kind=hs.HighsVarType.kContinuous if vtype=="C" else hs.HighsVarType.kInteger
        return self._h.addVariable(lb=lb,ub=ub,type=kind,name=name)

    def getVars(self):
        """Return variables in model order, also after reading an LP or MPS file."""
        return self._h.getVariables()

    def getVarByName(self,name):
        """Return the named model variable, or None when the name is absent."""
        if not isinstance(name,str):
            raise TypeError('a variable name must be a string')
        status,index=self._h.getColByName(name)
        return hs.highs_var(index,self._h) if status==hs.HighsStatus.kOk else None

    def addConstr(self,expression,name=None):
        return self._h.addConstr(expression,name=name)

    def setObjective(self,expression,sense=MINIMIZE):
        self._h.setObjective(expression,sense)

    def _start_arrays(self,start):
        if isinstance(start,Solution):
            if start._owner!=self._h or not start.has_solution:
                raise ValueError('start must be a feasible solution from this model')
            indices=np.arange(len(start.values),dtype=np.int32)
            values=np.asarray(start.values,dtype=float)
        else:
            pairs=start.items() if hasattr(start,'items') else start
            data={}
            for var,value in pairs:
                if not _belongs_to(var,self._h):
                    raise ValueError('start variable belongs to another model')
                index=int(var)
                if index in data or not isfinite(value):
                    raise ValueError('start requires distinct variables and finite values')
                data[index]=float(value)
            indices=np.fromiter(data,np.int32)
            values=np.fromiter(data.values(),float)
        return indices,values

    def setStart(self,start):
        """Pass a previous result or partial variable-to-value assignment to HiGHS."""
        indices,values=self._start_arrays(start)
        if len(indices) and self._h.setSolution(len(indices),indices,values)==hs.HighsStatus.kError:
            raise ValueError('HiGHS rejected the supplied start')

    def optimize(self,*,time_limit=inf,mip_gap=.0001,on_incumbent=None):
        """Solve and optionally publish immutable feasible solutions as the objective improves."""
        if on_incumbent is not None and not callable(on_incumbent):
            raise TypeError('on_incumbent must be callable')
        if time_limit<0 or isnan(time_limit) or not 0<=mip_gap<inf:
            raise ValueError("invalid solve limit")
        self._h.setOptionValue("time_limit",time_limit)
        self._h.setOptionValue("mip_rel_gap",mip_gap)
        best=None
        direction=int(self._h.getObjectiveSense()[1]) if on_incumbent is not None else 1
        def publish(solution):
            nonlocal best
            if best is None or (solution.objective-best)*direction < -1e-9:
                on_incumbent(solution)
                best=solution.objective

        if on_incumbent is None:
            _run_checked(self._h,time_limit)
        else:
            self._run_with_incumbents(time_limit,publish)
        status=self._h.getModelStatus()
        info=self._h.getInfo()
        if info.primal_solution_status!=hs.SolutionStatus.kSolutionStatusFeasible:
            return Solution(status.name[1:],None,(),None,None,self._h)
        mip=bool(len(self._h.getLp().integrality_))
        objective=self._h.getObjectiveValue()
        bound=info.mip_dual_bound if mip else objective if status==hs.HighsModelStatus.kOptimal else None
        result=Solution(status.name[1:],objective,tuple(self._h.getSolution().col_value),bound,
                        info.mip_gap if mip else None,self._h)
        if on_incumbent is not None:
            publish(result)
        return result

    def _run_with_incumbents(self,seconds,publish):
        h=self._h
        lp=h.getLp()
        if not len(lp.integrality_) or h.getHessianNumNz() or h.getNumLinearObjectives():
            _run_checked(h,seconds)
            return
        from scipy.sparse import csc_matrix,csr_matrix
        matrix=lp.a_matrix_
        form=csc_matrix if matrix.format_==hs.MatrixFormat.kColwise else csr_matrix
        A=form((matrix.value_,matrix.index_,matrix.start_),shape=(lp.num_row_,lp.num_col_))
        costs=np.asarray(lp.col_cost_)
        lo,hi=np.asarray(lp.col_lower_),np.asarray(lp.col_upper_)
        row_lo,row_hi=np.asarray(lp.row_lower_),np.asarray(lp.row_upper_)
        types=np.asarray(lp.integrality_,dtype=int)
        semi=np.isin(types,[int(hs.HighsVarType.kSemiContinuous),int(hs.HighsVarType.kSemiInteger)])
        integer=np.isin(types,[int(hs.HighsVarType.kInteger),int(hs.HighsVarType.kSemiInteger),int(hs.HighsVarType.kImplicitInteger)])
        tol=h.getOptionValue('mip_feasibility_tolerance')[1]
        failure=[]
        def receive(event):
            if failure:
                return
            try:
                x=np.asarray(event.data_out.mip_solution)
                if len(x)!=len(costs) or not np.all(np.isfinite(x)):
                    return
                row=A@x
                exempt=semi & (np.abs(x)<=tol)
                if (np.any((x<lo-tol)&~exempt) or np.any((x>hi+tol)&~exempt) or np.any(row<row_lo-tol)
                    or np.any(row>row_hi+tol) or np.any(np.abs(x[integer]-np.rint(x[integer]))>tol)):
                    return
                value=float(costs@x+lp.offset_)
                publish(Solution('Feasible',value,tuple(x.tolist()),None,None,h))
            except BaseException as error:
                # Python exceptions may not escape through a native callback. Interrupt at its supported event.
                failure.append(error)
        def cancel(event):
            if failure:
                event.interrupt()
        h.cbMipImprovingSolution.subscribe(receive)
        h.cbMipInterrupt.subscribe(cancel)
        try:
            _run_checked(h,seconds)
        finally:
            h.cbMipImprovingSolution.unsubscribe(receive)
            h.cbMipInterrupt.unsubscribe(cancel)
            if failure:
                raise failure[0]

    def _local_copy(self,original):
        local=Model()
        local._h.passOptions(self._h.getOptions())
        if local._h.passModel(original)==hs.HighsStatus.kError:
            raise RuntimeError('HiGHS rejected the local model copy')
        return local

    def _solve_local(self,local,warm,time_limit,mip_gap,started):
        indices,values=warm
        if len(indices) and local._h.setSolution(len(indices),indices,values)==hs.HighsStatus.kError:
            raise ValueError('HiGHS rejected the local start')
        result=local.optimize(time_limit=max(0.,time_limit-(time.monotonic()-started)),mip_gap=mip_gap)
        return Solution('Local'+result.status,result.objective,result.values,None,None,self._h)

    def fixAndOptimize(self,fixed,*,time_limit=60.,mip_gap=0.,hint=None):
        """Optimize the remaining variables with specified decisions fixed to exact values."""
        started=time.monotonic()
        if isnan(time_limit) or time_limit<0 or not 0<=mip_gap<inf:
            raise ValueError('invalid time limit or MIP gap')
        ids,values=self._start_arrays(fixed)
        if np.any(ids<0) or np.any(ids>=self._h.numVariables):
            raise ValueError('fixed variable outside the current model')
        local=self._local_copy(self._h.getModel())
        if len(ids):
            # Equalities preserve all imported variable domains, including semi-continuous values.
            status=local._h.addRows(len(ids),values,values,len(ids),np.arange(len(ids)+1,dtype=np.int32),
                                    ids,np.ones(len(ids)))
            if status==hs.HighsStatus.kError:
                raise RuntimeError('HiGHS rejected fixed decisions')
        warm=(ids,values) if hint is None else self._start_arrays(hint)
        return self._solve_local(local,warm,time_limit,mip_gap,started)

    def localBranch(self,start,*,max_changes,time_limit=60.,mip_gap=0.,hint=None):
        """Optimize a copy with a Hamming-distance limit on supplied binary decisions."""
        started=time.monotonic()
        if (type(max_changes)!=int or max_changes<0 or isnan(time_limit) or time_limit<0
            or not 0<=mip_gap<inf):
            raise ValueError('invalid change count, time limit or MIP gap')
        indices,values=self._start_arrays(start)
        original=self._h.getModel()
        lp=original.lp_
        if np.any(indices>=lp.num_col_):
            raise ValueError('start contains a variable outside the current model')
        is_integer=np.array(lp.integrality_,dtype=int)
        binary=np.zeros(lp.num_col_,dtype=bool)
        if len(is_integer):
            binary=(is_integer==int(hs.HighsVarType.kInteger)) & (np.asarray(lp.col_lower_)>=0) & (np.asarray(lp.col_upper_)<=1)
        picked=binary[indices]
        ids=indices[picked]
        bits=np.rint(values[picked])
        if not len(ids) or np.any((bits<0)|(bits>1)) or np.any(np.abs(bits-values[picked])>1e-6):
            raise ValueError('start must specify binary decisions with zero or one values')
        local=self._local_copy(original)
        weights=1.-2.*bits
        if local._h.addRow(-inf,max_changes-bits.sum(),len(ids),ids,weights)==hs.HighsStatus.kError:
            raise RuntimeError('HiGHS rejected the change limit')
        warm=(indices,values) if hint is None else self._start_arrays(hint)
        return self._solve_local(local,warm,time_limit,mip_gap,started)

    def write(self,path):
        if self._h.writeModel(str(path))==hs.HighsStatus.kError:
            raise OSError(f"Cannot export model to {path}")

    def read(self,path):
        other=Model()
        other._h.passOptions(self._h.getOptions())
        if other._h.readModel(str(path))==hs.HighsStatus.kError:
            raise ValueError(f"Cannot read model from {path}")
        self._h=other._h
