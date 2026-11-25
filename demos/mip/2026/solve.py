"""Evaluate batches of integer moves on GPU and validate shortlisted points on CPU."""

import argparse
import json
from functools import partial
from pathlib import Path
from time import monotonic

import numpy as np
import torch

from shiftopt import run_pipeline
from shiftopt.mip import LinearInstance, MipTrace


def choose_device(name):
    if name != "auto":
        return torch.device(name)
    if torch.cuda.is_available():
        return torch.device("cuda")
    return torch.device("mps" if torch.backends.mps.is_available() else "cpu")


def batch_search(plan, deadline, instance, device):
    if instance.fractional is None and plan is None:
        return None
    base = instance.fractional if instance.fractional is not None else plan
    a = instance.matrix.tocoo()
    row = torch.as_tensor(a.row.astype(np.int64), device=device)
    col = torch.as_tensor(a.col.astype(np.int64), device=device)
    coeff = torch.as_tensor(a.data, dtype=torch.float32, device=device)
    lower = torch.as_tensor(instance.row_lower, dtype=torch.float32, device=device)
    upper = torch.as_tensor(instance.row_upper, dtype=torch.float32, device=device)
    cost = torch.as_tensor(
        instance.cost * instance.sign, dtype=torch.float32, device=device
    )
    rng = np.random.default_rng(26)
    best = plan
    ids = instance.integer
    if not len(ids):
        return best
    count = max(2, min(64, 1000000 // max(1, len(base), len(lower))))
    for iteration in range(32):
        if monotonic() >= deadline:
            break
        center = best if iteration % 2 and best is not None else base
        x = np.tile(center, (count, 1))
        x[:, ids] = np.floor(x[:, ids] + rng.random((count, len(ids))))
        for i in range(count):
            chosen = rng.choice(ids, size=min(1 + i % 4, len(ids)), replace=False)
            x[i, chosen] = np.clip(
                x[i, chosen] + rng.choice([-1, 1], size=len(chosen)),
                np.ceil(instance.lower[chosen]),
                np.floor(instance.upper[chosen]),
            )
        candidates = torch.as_tensor(x, dtype=torch.float32, device=device)
        activity = torch.zeros((count, len(lower)), device=device)
        chunk = max(1, 1000000 // count)
        for start in range(0, len(row), chunk):
            section = slice(start, start + chunk)
            activity.index_add_(
                1, row[section], candidates[:, col[section]] * coeff[section]
            )
        violations = (
            (torch.relu(lower - activity) + torch.relu(activity - upper))
            .sum(dim=1)
            .cpu()
            .numpy()
        )
        values = (candidates @ cost).cpu().numpy()
        for i in np.lexsort((values, violations))[:8]:
            if monotonic() >= deadline:
                break
            trial = instance.repair(x[i], deadline)
            if trial is not None and (
                best is None or instance.score(trial) < instance.score(best)
            ):
                best = trial
    return best


def solve(path, seconds=30, device="auto", output=None):
    instance = LinearInstance(path)
    device = choose_device(device)
    step = partial(batch_search, instance=instance, device=device)
    trace = MipTrace(instance.result, output)
    plan = run_pipeline(
        [instance.bound_start, instance.rounded, step, instance.improve_coordinates],
        instance.score,
        seconds=seconds,
        on_accept=trace,
    )
    return {
        **instance.result(plan),
        "device": str(device),
        "improvements": trace.history,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "instance",
        type=Path,
        nargs="?",
        default=Path(__file__).with_name("example.mps"),
    )
    parser.add_argument("--seconds", type=float, default=30)
    parser.add_argument(
        "--device", choices=["auto", "cpu", "cuda", "mps"], default="auto"
    )
    parser.add_argument(
        "--solutions", type=Path, help="directory for improving MIPLIB solution files"
    )
    args = parser.parse_args()
    print(
        json.dumps(
            solve(args.instance, args.seconds, args.device, output=args.solutions),
            allow_nan=False,
        )
    )
