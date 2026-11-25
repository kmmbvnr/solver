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

## Full competition set

Each instance received ten runs with a local 60-second pipeline budget. The 2007 Mac calibration program is a 32-bit Intel executable, so the time limit on this Apple Silicon machine is a local choice. The ten run seeds were 1, 3, …, 19. Each run used two consecutive UniTime seeds. Every returned schedule passed a separate constraint and cost check.

| Track | Instances solved at least once | Verified runs | Place alongside the five finalists |
| --- | ---: | ---: | ---: |
| Exams | 12/12 | 114/120 | 1st of 6 |
| Post-enrolment courses | 18/24 | 171/240 | 6th of 6 |
| Curriculum courses | 21/21 | 210/210 | 2nd of 6 |

For each instance, the reconstruction pools our ten runs with the finalists’ fifty. For exams, assigning unsuccessful attempts last place reproduces the published order of the original teams. ShiftOpt also finishes first if unsuccessful attempts share their average rank. On curriculum, Müller leads with a mean rank of 17.881 against ShiftOpt’s 18.083. On post-enrolment, the demo returns no result for incomplete schedules, while the competition could score them by distance to feasibility. The exam result measures two restarts of Müller's UniTime search in ShiftOpt. [Organizers’ report and per-run tables](https://web.archive.org/web/2010id_/http://www.cs.qub.ac.uk/itc2007/winner/finalorder.htm)
