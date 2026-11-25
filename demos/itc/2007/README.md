# ITC 2007 — all three tracks

Each pipeline compares two independently seeded UniTime searches. On the curriculum track it also exchanges room labels to reduce capacity penalties while preserving room stability and feasibility. The demo accepts schedules with every exam, event or lecture placed.

Complete the [Java setup](../2002/README.md#setup-for-2002-and-2007), then run from the repository root:

```sh
python -m demos.itc.2007.solve exam demos/itc/2007/exam_comp_set1.exam /tmp/exam.sln
python -m demos.itc.2007.solve tim demos/itc/2007/comp-2007-2-5.tim /tmp/events.sln
python -m demos.itc.2007.solve ctt demos/itc/2007/comp01.ctt /tmp/courses.out
```

| Track and instance | Verified result at 60 seconds | Published comparison |
| --- | --- | --- |
| Examination, set 1 | All 607 exams placed, penalty 4,496. Independently recomputed constraints and cost. | Winning solver 4,370 |
| Post-enrolment, set 5 | Validator confirmed zero unplaced events, distance 0 and penalty 7. | Müller reported distance 0, penalty 0 |
| Curriculum, comp01 | Validator confirmed zero hard violations, penalty 5. | Müller reported 5 |

[Input archive and validator source](https://github.com/tomas-muller/cpsolver-itc2007) · [Competition standings](https://www.eeecs.qub.ac.uk/itc2007/winner/finalorder.htm) · [Müller's results](https://www.unitime.org/present/patat08itc.pdf)
