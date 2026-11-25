"""Run one pyhailing 0.0.9 day against a ShiftOpt worker in a separate environment."""

import argparse
import json
import subprocess
from pathlib import Path

import numpy as np
from pyhailing import RidehailEnv


def episode(python, vehicles, requests, seed):
    env = RidehailEnv(
        num_vehicles=vehicles,
        num_requests=requests,
        seed=seed,
        stochastic=True,
        max_interdecision_time=60,
    )
    observation = env.reset()
    lots = env.lots[["x", "y"]].to_numpy().tolist()
    command = [python, str(Path(__file__).with_name("solve.py")), "--epochs"]
    with subprocess.Popen(
        command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True
    ) as worker:
        total = 0.0
        done = False
        try:
            while not done:
                fields = {
                    k: np.asarray(observation[k]).tolist()
                    for k in ("request_locs", "v_locs", "v_jobs")
                }
                if len(fields["request_locs"]):
                    pickup = env._geom.travel_time(
                        observation["v_locs"],
                        observation["request_locs"][:, 0],
                        time=env._get_curr_tod_s(),
                        mean=True,
                        pairwise=True,
                    )
                    fields["pickup_seconds"] = pickup.reshape(
                        len(fields["v_locs"]), len(fields["request_locs"])
                    ).T.tolist()
                worker.stdin.write(
                    json.dumps({"observation": fields, "lots": lots}) + "\n"
                )
                worker.stdin.flush()
                action = {
                    k: np.asarray(v, dtype=int)
                    for k, v in json.loads(worker.stdout.readline()).items()
                }
                observation, reward, done, _ = env.step(action)
                total += reward
        finally:
            worker.stdin.close()
            env.close()
    if worker.returncode:
        raise RuntimeError("dispatch worker failed")
    return total


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "solver_python", help="Python environment with ShiftOpt installed"
    )
    parser.add_argument("--vehicles", type=int, default=14)
    parser.add_argument("--requests", type=int, default=1400)
    parser.add_argument("--seed", type=int, default=7)
    args = parser.parse_args()
    print(
        json.dumps(
            {
                "profit": episode(
                    args.solver_python, args.vehicles, args.requests, args.seed
                )
            }
        )
    )
