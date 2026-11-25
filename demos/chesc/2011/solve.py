"""Run the same selection hyper-heuristic independently on each CHeSC instance."""
import argparse
from itertools import chain, cycle

from demos.chesc.hyflex import DOMAINS, Search, instances, score
from shiftopt import bandit_policy, run_pipeline


def solve(domain, instance, seed, seconds, steps, policy):
    search = Search(domain, instance, seed)
    construct = search.construct
    if policy == "fixed":
        schedule = chain([construct], cycle(search.moves))
        choose = None
    else:
        schedule = [construct, *search.moves]
        choose = bandit_policy(search.moves, construct=construct)
    best = run_pipeline(schedule, score, seconds=seconds, max_steps=steps, policy=choose)
    if best is None:
        raise RuntimeError("Search budget expired before construction")
    return search.initial, best.cost


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--domain", choices=DOMAINS)
    parser.add_argument("--instance", type=int)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--seconds", type=float, default=10)
    parser.add_argument("--steps", type=int, default=10000)
    parser.add_argument("--policy", choices=("bandit", "fixed"), default="bandit")
    args = parser.parse_args()
    if not args.seconds > 0 or args.steps < 1:
        parser.error("seconds and steps must be positive")
    if args.instance is not None and not args.domain:
        parser.error("--instance requires --domain")
    jobs = instances()
    if args.domain:
        jobs = [(d, i) for d, i in jobs if d == args.domain]
        if args.instance is not None:
            if (args.domain, args.instance) not in jobs:
                parser.error(f"competition instance IDs: {DOMAINS[args.domain][1]}")
            jobs = [(args.domain, args.instance)]
    for domain, instance in jobs:
        initial, best = solve(domain, instance, args.seed, args.seconds, args.steps, args.policy)
        print(domain, instance, initial, best, flush=True)


if __name__ == "__main__":
    main()
