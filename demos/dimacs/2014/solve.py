"""Build a terminal-spanning subtree of a shortest-path tree (SteinLib STP)."""
from heapq import heappop, heappush


def problem(stream):
    edges, terminals = [], []
    for line in stream:
        fields = line.split()
        if not fields:
            continue
        if fields[0] == "Nodes":
            n = int(fields[1])
        elif fields[0] == "E":
            a, b = map(int, fields[1:3])
            w = float(fields[3])
            if w < 0:
                raise ValueError("negative edge length")
            edges.append((a, b, w))
        elif fields[0] == "T":
            terminals.append(int(fields[1]))
    if not terminals:
        raise ValueError("expected an undirected STP graph with terminals")
    graph = [[] for _ in range(n + 1)]
    for i, (a, b, w) in enumerate(edges):
        graph[a].append((b, w, i))
        graph[b].append((a, w, i))

    def connect(root):
        dist = {root: 0}
        parent = {}
        queue = [(0, root)]
        while queue:
            value, a = heappop(queue)
            if value != dist[a]:
                continue
            for b, w, i in graph[a]:
                if value + w < dist.get(b, float("inf")):
                    dist[b] = value + w
                    parent[b] = (a, i)
                    heappush(queue, (dist[b], b))
        connected = {root}
        chosen = []
        for v in terminals:
            while v not in connected:
                if v not in parent:
                    raise ValueError("disconnected terminals")
                connected.add(v)
                v, i = parent[v]
                chosen.append(i)
        return {"cost": sum(edges[i][2] for i in chosen),
                "edges": [edges[i][:2] for i in chosen]}

    def first_root(plan, deadline):
        return connect(terminals[0])

    def last_root(plan, deadline):
        return connect(terminals[-1])

    return [first_root, last_root], lambda plan: plan["cost"]
