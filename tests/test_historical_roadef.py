"""Check native schedules and objectives on the historical ROADEF examples."""

import re
import runpy
import unittest
from collections import Counter, defaultdict
from importlib.util import find_spec
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "demos" / "roadef"


def demo(year):
    return runpy.run_path(str(ROOT / str(year) / "solve.py"))


def records(text):
    for kind, fields in re.findall(r"(\w+)\(([^)]+)\)", text):
        yield kind, list(map(int, fields.split(",")))


def validate_inventory(path, score, plan):
    resources = {}
    orders = {}
    substitutes = set()
    for kind, (a, *fields) in records(path.read_text()):
        if kind == "resource":
            resources[a] = fields
        elif kind == "order":
            orders[a] = fields
        elif kind == "globals":
            begin, end, capacity = a, *fields
        elif kind == "substituable":
            substitutes.add((a, fields[0]))
    delivered = Counter()
    occupied = Counter()
    units = defaultdict(list)
    bought = {}
    cost = 0
    for kind, (r, second, third) in records(plan):
        (
            stock,
            _limit,
            service,
            need,
            rent,
            fixed,
            rate,
            purchase,
            holding,
            fee,
            _maxbuy,
        ) = resources[r]
        if kind == "buy":
            assert third > stock and (r, third) not in bought
            bought[r, third] = second
            cost += purchase + holding * (end - second)
        elif kind == "maint":
            units[r, second].append((third, third + service, kind))
            occupied.update({t: need for t in range(third, third + service)})
            cost += fee
        else:
            a, b, _qty, req = orders[second]
            assert r == req or (req, r) in substitutes
            if kind == "rent":
                delivered[second] += third
                cost += third * rent * (b - a)
            else:
                assert kind == "alloc"
                units[r, third].append((a, b, kind))
                delivered[second] += 1
                cost += fixed + rate * (b - a)
    for (r, i), events in units.items():
        assert 1 <= i <= resources[r][0] or (r, i) in bought
        free = bought.get((r, i), begin)
        wear = jobs = 0
        for a, b, kind in sorted(events):
            assert free <= a < b <= end
            free = b
            if kind == "maint":
                wear = jobs = 0
            else:
                jobs += 1
                wear += b - a
                assert jobs == 1 or wear <= resources[r][1]
    for r, row in resources.items():
        assert row[-1] < 0 or sum(i == r for i, _ in bought) <= row[-1]
    assert max(occupied.values(), default=0) <= capacity
    assert all(delivered[o] == v[2] for o, v in orders.items()) and cost == score


class HistoricalRoadefTests(unittest.TestCase):
    def test_inventory_workshop_and_objective(self):
        path = ROOT / "1999/I808nb.tes"
        score, plan = demo(1999)["solve"](path, 2)
        validate_inventory(path, score, plan)
        self.assertEqual(score, 1238300)

    def test_1999_worked_example(self):
        score, _ = demo(1999)["solve"](ROOT / "1999/example", 2)
        self.assertEqual(score, 3820)

    @unittest.skipUnless(find_spec("ortools"), "install the roadef extra")
    def test_frequency_assignment_reports_relaxed_interference(self):
        score, text = demo(2001)["solve"](ROOT / "2001/example", 3)
        self.assertEqual(score, (1, 1, 0))
        self.assertEqual(sum(line.startswith("AL") for line in text.splitlines()), 2)

    def test_car_reference_order(self):
        score, _ = demo(2005)["solve"](ROOT / "2005/example", 0)
        self.assertEqual(score, 284650)

    def test_flight_delay_crosses_midnight(self):
        self.assertEqual(demo(2009)["shift_clock"]("23:55", 20), "00:15+1")

    def test_edf_redispatch_preserves_load(self):
        solve = demo(2010)["solve"]
        value, text = solve(ROOT / "2010/example", 2)
        self.assertEqual(value, 10)
        self.assertIn("name A 0 10", text)
        self.assertIn("name B 1 0", text)

    def test_edf_improves_a_feasible_seed(self):
        path = ROOT / "2010/example"
        cost, _ = demo(2010)["solve"](path, 2, path.with_name("seed_example.txt"))
        self.assertEqual(cost, 10)

    def test_reassignment_keeps_incumbent_at_zero_budget(self):
        solve = demo(2012)["solve"]
        value, _ = solve(ROOT / "2012/model_a1_1.txt", 0)
        self.assertEqual(value, 49528750)
        self.assertEqual(solve(ROOT / "2012/model_example.txt", 2)[0], 1)

    def test_rail_yards_improve_empty_schedule(self):
        solve = demo(2014)["solve"]
        instance = ROOT / "2014/B1.zip"
        empty, _ = solve(instance, 0)
        value, plan = solve(instance, 2)
        self.assertEqual(value, 2555400)
        self.assertEqual(empty - value, 32000)
        self.assertEqual(plan.count("EnterSystem"), 32)
