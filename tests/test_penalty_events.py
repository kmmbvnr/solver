import unittest
from demos.itc.events import penalized_students


class PenaltyEventTests(unittest.TestCase):
    def test_single_triples_and_late_overlap(self):
        # Student bits 1 and 2 attend triples, 4 attends once, 8 attends twice.
        slots = [9, 1, 1, 4, 8, 0, 2, 2, 2]
        self.assertEqual([penalized_students(slots, i) for i in range(9)],
                         [1, 1, 1, 4, 0, 0, 2, 2, 2])

    def test_last_period_includes_every_student(self):
        self.assertEqual(penalized_students([3] + [0] * 7 + [3], 8), 3)

    def test_target_draw_selects_event_with_penalized_student(self):
        from types import SimpleNamespace
        from unittest.mock import Mock
        from demos.itc.events import penalty_event

        # Two simultaneous events. Only the second student's lecture is isolated.
        state = SimpleNamespace(members=[3, 1] + [0] * 43, period=[3] + [0] * 44,
                                problem=SimpleNamespace(members=[1, 2]), positions=[(0, 0), (0, 1)])
        rng = Mock()
        rng.randrange.side_effect = [1, 0, 0]
        self.assertEqual(penalty_event(state, rng), 1)
