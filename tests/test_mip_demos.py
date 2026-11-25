"""Exercise the six independent MIP entry points and replay their bundled examples."""

import gzip
import json
import subprocess
import sys
import unittest
from importlib.util import find_spec
from pathlib import Path
from tempfile import TemporaryDirectory

import highspy as hs

from shiftopt.mip import LinearInstance, open_model

ROOT = Path(__file__).resolve().parents[1] / "demos" / "mip"


def run(year, *args):
    output = subprocess.check_output(
        [sys.executable, str(ROOT / str(year) / "solve.py"), *map(str, args)]
    )
    return json.loads(output)


class MipDemos(unittest.TestCase):
    def test_linear_and_reoptimization(self):
        with TemporaryDirectory() as tmp:
            r = run(2022, "--solutions", tmp)
            self.assertEqual(r["objective"], 4)
            self.assertEqual(r["solution"], {"A": 0, "B": 0, "C": 1})
            lines = (Path(tmp) / "solution-1.sol").read_text().splitlines()
            self.assertEqual(lines, ["=obj= 4.0", "C 1.0"])
        first, second = run(2023)
        self.assertEqual([first["objective"], second["objective"]], [4, 6])
        for record in (first, second):
            self.assertEqual(record["objective"], record["dual_bound"])
        self.assertEqual(second["solution"], {"A": 0, "B": 1, "C": 1})
        self.assertIsNone(run(2022, "--seconds", 0)["solution"])

    def test_binary_followed_by_fix_in_compressed_mps(self):
        text = (
            (ROOT / "2022" / "example.mps")
            .read_text()
            .replace(" BV BND1      B", " FX BND1      A         1\n BV BND1      B")
        )
        with TemporaryDirectory() as tmp:
            target = Path(tmp) / "fixed.mps.gz"
            with gzip.open(target, "wt") as f:
                f.write(text)
            instance = LinearInstance(target)
            a = instance.names.index("A")
            self.assertEqual((instance.lower[a], instance.upper[a]), (1, 1))
            self.assertIn(a, instance.integer)
            self.assertEqual(run(2022, target)["objective"], 5)

    def test_presolve_roundtrip(self):
        with TemporaryDirectory() as tmp:
            folder = Path(tmp)
            model = folder / "reduced.mps.gz"
            mapping = folder / "mapping.json"
            info = run(2024, "--reduced", model, "--mapping", mapping)
            self.assertEqual((info["rows"], info["columns"], info["fixed"]), (1, 1, 1))
            self.assertTrue(model.read_bytes().startswith(b"\x1f\x8b"))
            ins = open_model(model)
            ins.run()
            self.assertEqual(ins.getModelStatus(), hs.HighsModelStatus.kOptimal)
            self.assertEqual(ins.getObjectiveValue(), 8)
            assignments = folder / "reduced.json"
            assignments.write_text(
                json.dumps(
                    dict(zip(ins.getLp().col_names_, ins.getSolution().col_value))
                )
            )
            self.assertEqual(
                run(2024, "--postsolve", mapping, assignments)["solution"],
                {"F": 2, "X": 1},
            )

            sparse_solution = folder / "reduced.sol"
            sparse_solution.write_text("=obj= 8\nX 1\n")
            self.assertEqual(
                run(2024, "--postsolve", mapping, sparse_solution)["solution"],
                {"F": 2, "X": 1},
            )

    @unittest.skipUnless(find_spec("pyscipopt"), "requires mip-quadratic")
    def test_quadratic(self):
        r = run(2025)
        x, y = r["solution"]["X"], r["solution"]["Y"]
        self.assertEqual((x, y), (2, 1))
        self.assertLessEqual(x * x + y * y, 5)
        self.assertEqual(r["improvements"][-1]["objective"], -3 * x - 2 * y)

    @unittest.skipUnless(find_spec("torch"), "requires mip-gpu")
    def test_batched_moves(self):
        r = run(2026, "--device", "cpu")
        self.assertEqual(r["device"], "cpu")
        self.assertEqual(r["objective"], 6)
        self.assertEqual(r["solution"], {"A": 0, "B": 1, "C": 1})
        self.assertEqual(r["improvements"][-1]["objective"], 6)

    def test_infeasibility_witnesses(self):
        r = run(2027)
        row = r["rows"]["HALF"]
        integ = r["columns"]["X"]["integrality"]
        self.assertEqual(
            (row["action"], integ["action"], r["rows"]["EXTRA"]["action"]),
            ("keep", "keep", "relax"),
        )
        x = row["certificate"].get("X", 0)
        self.assertIn(x, (0, 1))
        self.assertNotEqual(2 * x, 1)
        self.assertEqual(integ["certificate"]["X"], 0.5)
