"""Undirected graphs in the DIMACS coloring edge-list format."""


def read_graph(stream):
    graph = None
    count = 0
    for line in stream:
        fields = line.split()
        if not fields or fields[0] == "c":
            continue
        if fields[:2] == ["p", "edge"]:
            n, m = map(int, fields[2:])
            graph = [set() for _ in range(n)]
        elif fields[0] == "e" and graph is not None:
            a, b = (int(v) - 1 for v in fields[1:])
            if not (0 <= a < n and 0 <= b < n and a != b):
                raise ValueError("invalid edge")
            graph[a].add(b)
            graph[b].add(a)
            count += 1
        else:
            raise ValueError(line)
    if graph is None or count != m:
        raise ValueError("missing header or edge count mismatch")
    return graph
