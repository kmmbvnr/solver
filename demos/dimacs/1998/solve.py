"""Batch exact Euclidean nearest-neighbor queries with a k-d tree."""
import numpy as np
from scipy.spatial import cKDTree


def problem(stream):
    n, q, dimensions = map(int, stream.readline().split())
    points = np.loadtxt(stream, ndmin=2)
    if n < 1 or q < 0 or points.shape != (n + q, dimensions):
        raise ValueError("expected n data points followed by q query points")

    def nearest(plan, deadline):
        distance, index = cKDTree(points[:n]).query(points[n:], workers=-1)
        return {"index": index.tolist(), "distance": distance.tolist()}

    return [nearest], lambda plan: 0
