"""Color vertices by first fit in two vertex orders."""
from heapq import heappop, heappush
from time import monotonic

from graphs import read_graph


def problem(stream):
    graph = read_graph(stream)

    def color(order):
        colors = [0] * len(graph)
        for v in order:
            used = {colors[u] for u in graph[v]}
            k = 1
            while k in used:
                k += 1
            colors[v] = k
        return colors

    def by_degree(plan, deadline):
        return color(sorted(range(len(graph)), key=lambda v: -len(graph[v])))

    def saturation(plan, deadline):
        colors = [0] * len(graph)
        used = [set() for _ in graph]
        queue = []
        for v, row in enumerate(graph):
            heappush(queue, (0, -len(row), v))
        while queue:
            if monotonic() >= deadline:
                return None
            rank, _, v = heappop(queue)
            if colors[v] or -rank != len(used[v]):
                continue
            k = 1
            while k in used[v]:
                k += 1
            colors[v] = k
            for u in graph[v]:
                if not colors[u] and k not in used[u]:
                    used[u].add(k)
                    heappush(queue, (-len(used[u]), -len(graph[u]), u))
        return colors

    def by_color_class(plan, deadline):
        return color(sorted(range(len(graph)), key=lambda v: (-plan[v], -len(graph[v]))))

    return [by_degree, saturation, by_color_class], lambda plan: max(plan, default=0)
