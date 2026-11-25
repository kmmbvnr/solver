import unittest
from importlib import import_module
from pathlib import Path
from random import Random
from tempfile import TemporaryDirectory

from demos.itc.events import read_events
from demos.itc.timetable import TimetableMoves


class TimetableDeltaTest(unittest.TestCase):
    def check_walk(self, problem, positions, operators):
        plan = problem.objective(positions), positions
        rng = Random(92)
        for op in operators:
            move = TimetableMoves(problem, [op])
            checked = 0
            for i in range(100):
                proposal = move(plan, rng, float("inf"))
                if proposal is not None:
                    self.assertEqual(proposal[0], problem.objective(proposal[1]), op)
                    checked += 1
                    if i % 2:
                        plan = proposal
            self.assertGreater(checked, 0, op)

    def test_event_delta_across_days_swaps_and_room_only_changes(self):
        # Each student attends two events. Several events share a period.
        with TemporaryDirectory() as tmp:
            f = Path(tmp) / "events.tim"
            f.write_text("4 2 0 3\n10 10\n1 1 0 0\n0 1 1 0\n1 0 0 1\n")
            p = read_events(f, False)
        self.check_walk(p, ((0, 0), (1, 0), (0, 1), (8, 0)), TimetableMoves.operators)

    def test_exam_delta_with_shared_students_rooms_and_mixed_durations(self):
        with TemporaryDirectory() as tmp:
            f = Path(tmp) / "tiny.exam"
            f.write_text("""[Exams:4]
60, 1, 2
90, 3
60, 1, 3
90, 2
[Periods:4]
mon, 08:00, 90, 2
mon, 10:00, 90, 0
tue, 08:00, 90, 4
tue, 10:00, 90, 1
[Rooms:2]
8, 0
8, 3
[InstitutionalWeightings]
TWOINAROW, 5
TWOINADAY, 2
PERIODSPREAD, 2
NONMIXEDDURATIONS, 7
FRONTLOAD, 2, 2, 10
""")
            p = import_module("demos.itc.2007.exams").read_exam(f)
        self.check_walk(p, ((0, 0), (0, 0), (1, 0), (2, 0)), TimetableMoves.operators)

    def test_compact_move_and_course_deltas(self):
        with TemporaryDirectory() as tmp:
            f = Path(tmp) / "tiny.ctt"
            f.write_text("""Days: 2
Periods_per_day: 4
COURSES:
A T1 2 2 20
B T2 1 1 5
C T3 1 1 12
ROOMS:
small 10
big 30
CURRICULA:
G 2 A B
H 2 A C
END.
""")
            p, _ = import_module("demos.itc.2007.curriculum").read_curriculum(f)
        positions = ((0, 0), (4, 1), (3, 0), (3, 1))
        plan = p.objective(positions), positions
        proposal = TimetableMoves(p, ["compact"])(plan, Random(1), float("inf"))
        self.assertIsNotNone(proposal)
        self.assertEqual(proposal[0], p.objective(proposal[1]))
        self.assertLess(proposal[0], plan[0])
        self.check_walk(p, positions, TimetableMoves.operators)
