"""Low-rank feasible solutions for the DIMACS torus semidefinite relaxation."""
from time import monotonic

import numpy as np


def problem(stream):
    n, m = map(int, stream.readline().split())
    graph = [[] for _ in range(n)]
    edges = []
    for line in stream:
        if not line.strip():
            continue
        u, v, weight = map(int, line.split())
        a, b = u - 1, v - 1
        if not (0 <= a < n and 0 <= b < n and a != b):
            raise ValueError("invalid torus edge")
        graph[a].append((b, weight))
        graph[b].append((a, weight))
        edges.append((a, b, weight))
    if len(edges) != m:
        raise ValueError("edge count mismatch")

    def objective(factor):
        # DIMACS uses half the Laplacian as its objective matrix.
        return sum(w * (1 - np.dot(factor[a], factor[b])) for a, b, w in edges)

    def relax(plan, deadline):
        rng = np.random.default_rng(0)
        factor = rng.normal(size=(n, min(n, 8)))
        factor /= np.linalg.norm(factor, axis=1)[:, None]
        neighbors = [(np.array([v for v, w in row], dtype=int),
                      np.array([w for v, w in row])) for row in graph]
        previous = value = objective(factor)
        for _ in range(100):
            for i, (vertices, weights) in enumerate(neighbors):
                if monotonic() >= deadline:
                    break
                field = weights @ factor[vertices]
                norm = np.linalg.norm(field)
                if norm:
                    factor[i] = -field / norm
            value = objective(factor)
            if monotonic() >= deadline or value - previous <= 1e-8 * max(1, abs(value)):
                break
            previous = value
        return {"objective": value, "factor": factor.tolist()}

    return [relax], lambda plan: -plan["objective"]
