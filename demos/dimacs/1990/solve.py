"""Maximum flow on a directed capacitated network (DIMACS .max)."""
from shiftopt import bounded_max_flow


def problem(stream):
    edges = []
    terminals = {}
    for line in stream:
        fields = line.split()
        if not fields or fields[0] == "c":
            continue
        if fields[:2] == ["p", "max"]:
            n, m = map(int, fields[2:])
        elif fields[0] == "n":
            terminals[fields[2]] = int(fields[1]) - 1
        elif fields[0] == "a":
            a, b, capacity = map(int, fields[1:])
            edges.append((a - 1, b - 1, 0, capacity))
        else:
            raise ValueError(line)
    if len(edges) != m:
        raise ValueError("arc count mismatch")
    source, sink = terminals["s"], terminals["t"]

    def maximize(plan, deadline):
        flows = bounded_max_flow(n, edges, source, sink)
        value = sum(flow * ((a == source) - (b == source))
                    for (a, b, _, _), flow in zip(edges, flows))
        return {"value": value, "flows": flows}

    return [maximize], lambda plan: -plan["value"]
