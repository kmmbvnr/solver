"""Construct chordal completions and tree decompositions by vertex elimination."""

from itertools import combinations
from time import monotonic


def eliminate(graph, deadline, *, min_fill=False, reverse=False):
    """Return elimination bags and added edges, or None on timeout."""
    neighbors = {v: set(row) - {v} for v, row in graph.items()}
    bags = []
    fill = []
    order = {v: i for i, v in enumerate(reversed(graph) if reverse else graph)}
    while neighbors:
        if monotonic() >= deadline:
            return None
        minimum = min(map(len, neighbors.values()))
        shortlist = [v for v, row in neighbors.items() if len(row) == minimum]
        if min_fill:
            # Limit the quadratic fill calculation to low-degree candidates.
            shortlist = sorted(neighbors, key=lambda v: (len(neighbors[v]), order[v]))[
                :16
            ]
        v = min(
            shortlist,
            key=lambda u: (
                sum(b not in neighbors[a] for a, b in combinations(neighbors[u], 2))
                if min_fill
                else 0,
                order[u],
            ),
        )
        row = neighbors.pop(v)
        bags.append((v, sorted(row)))
        for a, b in combinations(row, 2):
            if b not in neighbors[a]:
                neighbors[a].add(b)
                neighbors[b].add(a)
                fill.append((a, b))
        for u in row:
            neighbors[u].remove(v)
    return bags, fill
