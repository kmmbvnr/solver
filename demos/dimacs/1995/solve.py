"""Replay an integer minimum-priority queue trace."""
from heapq import heappop, heappush


def problem(stream):
    commands = [line.split() for line in stream if line.strip()]

    def replay(plan, deadline):
        heap = []
        extracted = []
        for command in commands:
            if command[0] == "insert" and len(command) == 2:
                heappush(heap, int(command[1]))
            elif command == ["extract"] and heap:
                extracted.append(heappop(heap))
            else:
                raise ValueError(f"invalid queue operation: {command}")
        return extracted

    return [replay], lambda plan: 0
