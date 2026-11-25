import importlib
import unittest
from importlib.util import find_spec
from itertools import permutations
from pathlib import Path
from tempfile import TemporaryDirectory
from xml.etree import ElementTree as ET


class TimetableMovesTest(unittest.TestCase):
    def test_student_exchange_preserves_section_sizes_and_reduces_conflicts(self):
        demo = importlib.import_module("demos.itc.2019.solve")
        problem = ET.fromstring("""<problem><optimization student="10"/><courses>
          <course id="choice"><config><subpart>
            <class id="a"><time days="1" weeks="1" start="0" length="1"/></class>
            <class id="b"><time days="1" weeks="1" start="1" length="1"/></class>
          </subpart></config></course><course id="other"><config><subpart>
            <class id="c"><time days="1" weeks="1" start="0" length="1"/></class>
          </subpart></config></course></courses></problem>""")
        seed = b"""<solution>
          <class id="a" days="1" weeks="1" start="0"><student id="1"/></class>
          <class id="b" days="1" weeks="1" start="1"><student id="2"/></class>
          <class id="c" days="1" weeks="1" start="0"><student id="1"/></class>
          </solution>"""
        cost, xml = demo.exchange_enrollments(problem, (10, seed), float("inf"))
        self.assertEqual(cost, 0)
        self.assertEqual([(c.get("id"), c.find("student").get("id"))
                          for c in ET.fromstring(xml)], [("a", "2"), ("b", "1"), ("c", "1")])

    @unittest.skipUnless(find_spec("ortools"), "requires the ITC extra")
    def test_round_robin_schedule_and_incomplete_seed(self):
        demo = importlib.import_module("demos.itc.2021.solve")
        teams = list("abcd")
        slots = list("012345")
        games = demo.pairings(teams, slots)
        self.assertCountEqual([(h, a) for h, a, _ in games], permutations(teams, 2))
        for slot in slots:
            self.assertCountEqual([t for h, a, s in games if s == slot for t in (h, a)], teams)
        with TemporaryDirectory() as tmp:
            seed = Path(tmp) / "seed.xml"
            seed.write_bytes(demo.solution("test", games[:-1], 0))
            with self.assertRaisesRegex(ValueError, "every directed fixture"):
                demo.seed_schedule(None, teams, slots, seed, None, float("inf"))
