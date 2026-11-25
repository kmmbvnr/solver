"""Run one isolated UniTime construction or restart for the 2002/2007 formats."""
import csv
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from time import monotonic


@dataclass(frozen=True)
class Plan:
    cost: tuple
    text: str


def score(plan):
    return plan.cost


def search(track, path, seed, seconds, incumbent, deadline):
    home = Path(os.environ["ITC2007_HOME"]).resolve()
    limit = min(seconds, int(deadline - monotonic()))
    if limit < 1:
        return None
    with TemporaryDirectory() as tmp:
        out = Path(tmp) / "plan.sln"
        cp = os.pathsep.join(str(home / name) for name in ("classes", "lib/*"))
        args = ["java", "-Duser.language=en", "-Duser.country=US", "-Xmx768m", "-cp", cp, "net.sf.cpsolver.itc.ItcTest",
                track, str(path.resolve()), str(out), str(limit), str(seed)]
        subprocess.run(args, check=True, cwd=tmp, stdout=subprocess.DEVNULL)
        report = out.with_name(path.stem + ".csv")
        if not out.exists() or not report.exists():
            return None
        with report.open() as stream:
            row = next(csv.DictReader(stream))
        if track == "exam" and (row["bv"] != "0" or row["dc"] != "0"):
            return None
        text = out.read_text()
        if track == "tim":
            if any(row[k] != "0" for k in ("df", "pv", "nr")) or "-1" in text.split():
                return None
            cost = int(row["df"]), sum(int(row[k]) for k in ("1d", "lt", "3+"))
        else:
            # The backend emits a CSV for these formats only with all variables assigned.
            cost = (int(float(row["total"])),)
        return Plan(cost, text)
