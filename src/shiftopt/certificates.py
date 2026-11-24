"""Group mutually exclusive columns to verify upper bounds supplied by any price oracle."""
import numpy as np
from scipy.sparse import csc_matrix


def exclusive_groups(usage,capacity,*,prefer_dense=False):
    A=csc_matrix(usage,copy=True,dtype=float)
    A.sum_duplicates()
    cap=np.asarray(capacity,float)
    if cap.shape!=(A.shape[0],) or np.any(cap<0) or not np.all(np.isfinite(cap)) or np.any(A.data<0) or not np.all(np.isfinite(A.data)):
        raise ValueError("expected finite nonnegative usage and capacities")
    # Two selected columns in the same group would exceed this row's cap.
    mask=A.data>cap[A.indices]/2
    degree=np.bincount(A.indices[mask],minlength=len(cap))
    groups=np.arange(A.shape[1])+len(cap)
    for j in range(A.shape[1]):
        sl=slice(A.indptr[j],A.indptr[j+1])
        rows=A.indices[sl][mask[sl]]
        if len(rows):
            groups[j]=rows[np.argmax(degree[rows]) if prefer_dense else 0]
    return np.unique(groups,return_inverse=True)[1]


def group_bound(values,usage,capacity,prices,groups):
    """Returns a global bound and a bound conditional on selecting each column.
    Groups must be obtained from exclusive_groups for this model.
    """
    p=np.asarray(prices,float)
    if p.shape!=np.shape(capacity) or np.any(p<0) or not np.all(np.isfinite(p)):
        raise ValueError("prices must be finite and nonnegative")
    rc=np.asarray(values)-usage.T@p
    maxima=np.zeros(np.max(groups,initial=-1)+1)
    np.maximum.at(maxima,groups,rc)
    upper=float(np.dot(capacity,p)+maxima.sum())
    return upper,upper-maxima[groups]+rc
