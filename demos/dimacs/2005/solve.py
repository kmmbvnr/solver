"""Single-source shortest paths from vertex 1 on nonnegative DIMACS .gr graphs."""
from heapq import heappop, heappush


def problem(stream):
    count = 0
    for line in stream:
        fields = line.split()
        if not fields or fields[0] == "c":
            continue
        if fields[:2] == ["p", "sp"]:
            n, m = map(int, fields[2:])
            graph = [[] for _ in range(n)]
        elif fields[0] == "a":
            a, b, w = map(int, fields[1:])
            if w < 0 or not (1 <= a <= n and 1 <= b <= n):
                raise ValueError("invalid arc")
            graph[a - 1].append((b - 1, w))
            count += 1
        else:
            raise ValueError(line)
    if count != m:
        raise ValueError("arc count mismatch")

    def shortest_paths(plan, deadline):
        distances = [None] * n
        distances[0] = 0
        queue = [(0, 0)]
        while queue:
            cost, u = heappop(queue)
            if distances[u] != cost:
                continue
            for v, w in graph[u]:
                new = cost + w
                if distances[v] is None or new < distances[v]:
                    distances[v] = new
                    heappush(queue, (new, v))
        return distances

    return [shortest_paths], lambda plan: 0
