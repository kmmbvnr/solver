"""Keep compatible initial trains in available yard space throughout the horizon."""

import argparse
import csv
from functools import partial
from io import StringIO
from operator import itemgetter
from pathlib import Path
from time import monotonic
from zipfile import ZipFile

from shiftopt import run_pipeline


def table(path, name):
    if path.is_dir():
        data = (path / (name + ".csv")).read_text()
    else:
        with ZipFile(path) as archive:
            data = archive.read(name + ".csv").decode()
    return list(csv.DictReader(StringIO(data), delimiter=";"))


def park(plan, deadline, initial, capacity, allowed, params, base, reverse):
    remaining = capacity.copy()
    rows = ["train;time;event;resource;gate;complement;"]
    kept = 0
    for train in sorted(initial, key=itemgetter("idTrain"), reverse=reverse):
        if monotonic() >= deadline:
            return None
        r = train["resource"]
        if remaining.get(r, 0) <= 0 or (r, train["category"]) not in allowed:
            continue
        t = train["idTrain"]
        end = f"d{params['nbDays']} 23:59:59"
        for stamp, event in [
            ("d1 00:00:00", "EnterSystem"),
            ("d1 00:00:00", "EnterResource"),
            (end, "ExitResource"),
            (end, "ExitSystem"),
        ]:
            rows.append(f"{t};{stamp};{event};{r};;;")
        remaining[r] -= 1
        kept += 1
    return base - kept * float(params["uncovCost"]), "\n".join(rows) + "\n"


def solve(path, seconds):
    initial = table(path, "initialTrains")
    params = {r["parameterName"]: r["value"] for r in table(path, "parameters")}
    capacity = {r["idYard"]: int(r["capa"]) for r in table(path, "yards")}
    for r in table(path, "imposedConsumptions"):
        if r["resource"] in capacity:
            capacity[r["resource"]] = 0
    allowed = {
        (r["resource"], r["compatibleCategory"]) for r in table(path, "compCatRes")
    }
    count = len(initial) + len(table(path, "arrivals")) + len(table(path, "departures"))
    base = count * float(params["uncovCost"]) + len(table(path, "reuses")) * float(
        params["reuseCost"]
    )
    steps = [
        partial(
            park,
            initial=initial,
            capacity=capacity,
            allowed=allowed,
            params=params,
            base=base,
            reverse=r,
        )
        for r in (False, True)
    ]
    return run_pipeline(
        steps,
        itemgetter(0),
        initial=(base, "train;time;event;resource;gate;complement;\n"),
        seconds=seconds,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "input", type=Path, nargs="?", default=Path(__file__).with_name("B1.zip")
    )
    parser.add_argument("--seconds", type=float, default=5)
    args = parser.parse_args()
    print(solve(args.input, args.seconds)[1], end="")
