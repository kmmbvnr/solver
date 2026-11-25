"""Maximum flow with lower and upper bounds on directed edges."""
from collections import deque
from math import inf, isfinite


def bounded_max_flow(node_count, edges, source, sink):
    """Return flows in input order, or None if the lower bounds are infeasible."""
    if not (0 <= source < node_count and 0 <= sink < node_count and source != sink):
        raise ValueError("expected distinct source and sink nodes")
    origin, target = node_count, node_count + 1
    graph = [[] for _ in range(node_count + 2)]
    residual = []
    destinations = []
    balance = [0.] * node_count
    tolerance = 1e-9

    def add(a, b, capacity):
        index = len(residual)
        graph[a].append(index)
        graph[b].append(index + 1)
        residual.extend((capacity, 0.))
        destinations.extend((b, a))
        return index

    def augment(a, b):
        while True:
            parent = [-1] * len(graph)
            parent[a] = -2
            queue = deque([a])
            while queue and parent[b] == -1:
                node = queue.popleft()
                for edge in graph[node]:
                    other = destinations[edge]
                    if residual[edge] > tolerance and parent[other] == -1:
                        parent[other] = edge
                        queue.append(other)
            if parent[b] == -1:
                return
            path = []
            node = b
            while node != a:
                edge = parent[node]
                path.append(edge)
                node = destinations[edge ^ 1]
            amount = min(residual[edge] for edge in path)
            for edge in path:
                residual[edge] -= amount
                residual[edge ^ 1] += amount

    original = []
    for a, b, low, high in edges:
        if not (0 <= a < node_count and 0 <= b < node_count and
                isfinite(low) and isfinite(high) and 0 <= low <= high):
            raise ValueError("invalid bounded edge")
        original.append((add(a, b, high - low), low))
        balance[a] -= low
        balance[b] += low
    auxiliary = add(sink, source, inf)
    for node, demand in enumerate(balance):
        if demand > 0:
            add(origin, node, demand)
        elif demand < 0:
            add(node, target, -demand)
    augment(origin, target)
    if any(residual[e] > tolerance for e in graph[origin]):
        return None
    for e in range(auxiliary, len(residual)):
        residual[e] = 0.
    augment(source, sink)
    return [low + residual[e ^ 1] for e, low in original]
