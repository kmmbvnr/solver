"""Run the setX-01 search with identical float32 values, sharing unchanged route rows."""
import argparse
from pathlib import Path
import numpy as np
import solve as original


class SharedRows:
    def __init__(self, first, current):
        self.first = first
        changed = np.any(current != first, axis=2)
        self.index = np.full(changed.shape, -1, dtype=np.int32)
        self.index[changed] = np.arange(np.count_nonzero(changed))
        self.patch = current[changed]

    def __getitem__(self, key):
        u, v, *edge = np.broadcast_arrays(*key)
        row = self.index[u, v]
        if row.ndim == 0:
            return self.patch[(row, *edge)] if row >= 0 else self.first[(u, v, *edge)]
        answer = self.first[(u, v, *edge)]
        mask = row >= 0
        answer[mask] = self.patch[(row[mask], *(e[mask] for e in edge))]
        return answer


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inputs", type=Path)
    parser.add_argument("instance")
    parser.add_argument("--seconds", type=float, default=120)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    dense = original.routing_table
    first = None

    def share(*args):
        nonlocal first
        table = dense(*args)
        if first is None:
            first = table
            return table
        return SharedRows(first, table)

    original.routing_table = share
    original.solve(args.inputs, args.instance, args.seconds, args.output)


if __name__ == "__main__":
    main()
