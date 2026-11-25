"""Linear MPS input, feasibility checks and LP-based rounding for primal search."""

import gzip
from pathlib import Path
from tempfile import TemporaryDirectory
from time import monotonic

import highspy as hs
import numpy as np
from scipy.sparse import csc_matrix


class QuietHighs(hs.Highs):
    def enableCallbacks(self):
        self.silent()
        super().enableCallbacks()


def open_model(path):
    model = QuietHighs()
    status = model.readModel(str(path))
    if status == hs.HighsStatus.kWarning:
        # Some MIPcc23 series declare a binary domain and later fix that same variable.
        # HiGHS ignores the second bound. Encode the intersection as integer bounds.
        opener = gzip.open if str(path).endswith(".gz") else open
        with opener(path, "rt") as f:
            lines = f.readlines()
        binary = {}
        fixed = {}
        section = ""
        for i, line in enumerate(lines):
            fields = line.split()
            if not fields or line.startswith("*"):
                continue
            if not line[0].isspace():
                section = fields[0]
            elif section == "BOUNDS" and fields[0] == "BV":
                binary[tuple(fields[1:3])] = i
            elif section == "BOUNDS" and fields[0] == "FX":
                fixed[tuple(fields[1:3])] = (i, float(fields[3]))
        for key in binary.keys() & fixed.keys():
            i, value = fixed[key]
            if value not in (0, 1):
                raise ValueError("invalid fixed binary value")
            group, name = key
            lines[binary[key]] = f" LI {group} {name} {int(value)}\n"
            lines[i] = f" UI {group} {name} {int(value)}\n"
        with TemporaryDirectory() as directory:
            normalized = Path(directory) / "normalized.mps"
            normalized.write_text("".join(lines))
            model = QuietHighs()
            status = model.readModel(str(normalized))
    if status != hs.HighsStatus.kOk:
        raise ValueError(f"could not read {path} without discarded records")
    if model.getHessianNumNz():
        raise ValueError("expected a linear objective")
    model.setOptionValue("threads", 1)
    return model


class LinearInstance:
    def __init__(self, path):
        self.model = open_model(path)
        lp = self.model.getLp()
        self.names = list(lp.col_names_)
        self.cost = np.asarray(lp.col_cost_)
        self.offset = lp.offset_
        self.sign = int(lp.sense_)
        self.lower = np.asarray(lp.col_lower_)
        self.upper = np.asarray(lp.col_upper_)
        self.row_lower = np.asarray(lp.row_lower_)
        self.row_upper = np.asarray(lp.row_upper_)
        types = lp.integrality_
        if any(
            t not in (hs.HighsVarType.kContinuous, hs.HighsVarType.kInteger)
            for t in types
        ):
            raise ValueError("expected continuous and ordinary integer variables")
        self.integer = np.array(
            [i for i, t in enumerate(types) if t == hs.HighsVarType.kInteger],
            dtype=np.int32,
        )
        a = lp.a_matrix_
        self.matrix = csc_matrix(
            (a.value_, a.index_, a.start_), shape=(lp.num_row_, lp.num_col_)
        )
        self.matrix.sum_duplicates()
        self.matrix.eliminate_zeros()
        self.fractional = None

    def score(self, x):
        return self.sign * float(self.cost @ x + self.offset)

    def valid(self, x, tol=1e-6):
        if x is None:
            return False
        x = np.asarray(x)
        if x.shape != self.cost.shape or not np.all(np.isfinite(x)):
            return False
        activity = self.matrix @ x
        return (
            np.all(x >= self.lower - tol)
            and np.all(x <= self.upper + tol)
            and np.all(activity >= self.row_lower - tol)
            and np.all(activity <= self.row_upper + tol)
            and np.all(np.abs(x[self.integer] - np.rint(x[self.integer])) <= tol)
        )

    def lp_point(self, deadline, fixed=None):
        model = QuietHighs()
        model.silent()
        model.setOptionValue("threads", 1)
        model.passModel(self.model.getLp())
        if len(self.integer):
            model.changeColsIntegrality(
                len(self.integer),
                self.integer,
                np.zeros(len(self.integer), dtype=np.uint8),
            )
        if fixed is not None:
            values = np.asarray(fixed)[self.integer]
            model.changeColsBounds(len(values), self.integer, values, values)
        remaining = deadline - monotonic()
        if remaining <= 0:
            return None
        model.setOptionValue("time_limit", remaining)
        model.run()
        solution = model.getSolution()
        if (
            model.getModelStatus() != hs.HighsModelStatus.kOptimal
            or not solution.value_valid
        ):
            return None
        return np.asarray(solution.col_value)

    def rounded(self, plan, deadline):
        self.fractional = self.lp_point(
            monotonic() + max(0.0, deadline - monotonic()) * 0.5
        )
        if self.fractional is None:
            return None
        x = self.fractional.copy()
        x[self.integer] = np.rint(x[self.integer])
        return self.repair(x, deadline)

    def repair(self, x, deadline):
        if self.valid(x):
            return x
        if len(self.integer) == len(self.names):
            return None
        point = self.lp_point(deadline, x)
        return point if self.valid(point) else None

    def bound_start(self, plan, deadline):
        best = plan
        for bound in (self.lower, self.upper):
            x = np.where(np.isfinite(bound), bound, 0.0).clip(self.lower, self.upper)
            if monotonic() >= deadline:
                break
            if self.valid(x) and (best is None or self.score(x) < self.score(best)):
                best = x
        return best

    def improve_coordinates(self, plan, deadline):
        if plan is None:
            return None
        x = np.array(plan, dtype=float)
        activity = self.matrix @ x
        for j in np.argsort(-np.abs(self.cost[self.integer] * self.sign)):
            if monotonic() >= deadline:
                break
            col = self.integer[j]
            direction = -np.sign(self.cost[col] * self.sign)
            if not direction:
                continue
            room = (
                self.upper[col] - x[col] if direction > 0 else x[col] - self.lower[col]
            )
            lo, hi = self.matrix.indptr[col : col + 2]
            rows = self.matrix.indices[lo:hi]
            delta = direction * self.matrix.data[lo:hi]
            up = delta > 0
            down = delta < 0
            room = min(
                room,
                np.min(
                    (self.row_upper[rows[up]] - activity[rows[up]]) / delta[up],
                    initial=np.inf,
                ),
                np.min(
                    (self.row_lower[rows[down]] - activity[rows[down]]) / delta[down],
                    initial=np.inf,
                ),
            )
            if np.isfinite(room) and room >= 1:
                step = np.floor(room)
                x[col] += step * direction
                activity[rows] += step * delta
        return x if self.valid(x) else None

    def trials(self, plan, deadline, attempts=128):
        if self.fractional is None:
            return None
        rng = np.random.default_rng(19)
        best = plan
        idx = self.integer
        for i in range(attempts):
            if monotonic() >= deadline:
                break
            x = self.fractional.copy()
            x[idx] = np.floor(x[idx] + rng.random(len(idx)))
            if i % 2 and len(idx):
                if best is not None:
                    x = best.copy()
                cells = rng.choice(idx, size=min(1 + i % 3, len(idx)), replace=False)
                x[cells] = np.clip(
                    x[cells] + rng.choice([-1, 1], size=len(cells)),
                    np.ceil(self.lower[cells]),
                    np.floor(self.upper[cells]),
                )
            trial = self.repair(x, deadline)
            if trial is not None and (
                best is None or self.score(trial) < self.score(best)
            ):
                best = trial
        return best

    def result(self, plan):
        if plan is None:
            return {"solution": None, "objective": None}
        return {
            "solution": dict(zip(self.names, map(float, plan))),
            "objective": self.sign * self.score(plan),
        }


class MipTrace:
    """Record improving primal solutions and optionally write MIPLIB witnesses."""

    def __init__(self, decode, directory=None):
        self.decode = decode
        self.directory = directory
        self.history = []
        self.start = monotonic()
        if directory is not None:
            directory.mkdir(parents=True, exist_ok=True)

    def __call__(self, plan):
        result = self.decode(plan)
        self.history.append(
            {"seconds": monotonic() - self.start, "objective": result["objective"]}
        )
        if self.directory is not None:
            file = self.directory / f"solution-{len(self.history)}.sol"
            with file.open("w") as stream:
                print("=obj=", result["objective"], file=stream)
                for name, value in result["solution"].items():
                    if value:
                        print(name, value, file=stream)
