"""Run single-solver or multiple-solver CHeSC-style batches on public HyFlex data."""
import argparse
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from multiprocessing import get_context
from time import monotonic

from demos.chesc.hyflex import Move, Search, instances, score
from shiftopt import bandit_policy, run_pipeline


class Experience:
    def __init__(self):
        self.trials = Counter()
        self.wins = Counter()

    def priority(self, move):
        family = move.family
        return (1 + self.wins[family]) / (2 + self.trials[family])

    def observe(self, step, previous, proposed, elapsed):
        if isinstance(step, Move):
            self.trials[step.family] += 1
            self.wins[step.family] += proposed < previous


def solve_lane(jobs, deadline, seed, steps):
    experience = Experience()
    results = []
    for index, (domain, instance) in enumerate(jobs):
        started = monotonic()
        share = (deadline - started) / (len(jobs) - index)
        if share <= 0:
            raise RuntimeError(f"Batch deadline expired before {domain} {instance}")
        search = Search(domain, instance, seed)
        construct = search.construct
        moves = sorted(search.moves, key=experience.priority, reverse=True)
        best = run_pipeline(
            [construct, *moves], score,
            seconds=max(0, started + share - monotonic()), max_steps=steps,
            policy=bandit_policy(moves, construct=construct), on_step=experience.observe,
        )
        if best is None:
            raise RuntimeError(f"Insufficient batch budget to construct {domain} {instance}")
        results.append((domain, instance, float(search.initial), float(best.cost)))
    return results


def solve_batch(jobs, workers, seconds, seed, steps):
    lanes = [jobs[i::workers] for i in range(min(workers, len(jobs)))]
    deadline = monotonic() + seconds
    if len(lanes) == 1:
        return solve_lane(lanes[0], deadline, seed, steps)
    # Independent JVMs isolate domain implementations with process-wide state.
    with ProcessPoolExecutor(len(lanes), mp_context=get_context("spawn")) as pool:
        tasks = [pool.submit(solve_lane, lane, deadline, seed, steps) for lane in lanes]
        results = {row[:2]: row for task in tasks for row in task.result()}
    return [results[job] for job in jobs]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--seconds", type=float, default=300)
    parser.add_argument("--steps", type=int, default=10000)
    parser.add_argument("--seed", type=int, default=1)
    args = parser.parse_args()
    if min(args.steps, args.workers) < 1 or not args.seconds > 0:
        parser.error("workers, steps and seconds must be positive")
    for result in solve_batch(instances(), args.workers, args.seconds, args.seed, args.steps):
        print(*result)


if __name__ == "__main__":
    main()
