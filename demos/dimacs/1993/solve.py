"""Find components of edge blocks concurrently and merge their spanning stars."""
from concurrent.futures import ThreadPoolExecutor

import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components

from graphs import read_graph


def labels(n, a, b):
    matrix = coo_matrix((np.ones(len(a), dtype=bool), (a, b)), shape=(n, n))
    return connected_components(matrix, directed=False)[1]


def spanning_stars(block):
    vertices, indices = np.unique(block.ravel(), return_inverse=True)
    pairs = indices.reshape(-1, 2)
    component = labels(len(vertices), pairs[:, 0], pairs[:, 1])
    roots = np.full(len(vertices), len(vertices))
    np.minimum.at(roots, component, np.arange(len(vertices)))
    return vertices, vertices[roots[component]]


def problem(stream):
    graph = read_graph(stream)
    edges = np.asarray([(a, b) for a, row in enumerate(graph) for b in row if a < b],
                       dtype=int).reshape(-1, 2)

    def merge_components(plan, deadline):
        if not len(edges):
            return list(range(len(graph)))
        blocks = np.array_split(edges, min(4, len(edges)))
        with ThreadPoolExecutor(max_workers=len(blocks)) as workers:
            starts, ends = zip(*workers.map(spanning_stars, blocks))
        return labels(len(graph), np.concatenate(starts), np.concatenate(ends)).tolist()

    return [merge_components], lambda plan: 0
