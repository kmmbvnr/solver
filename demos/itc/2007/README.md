# ITC 2007 — all three tracks

The Python pipeline first builds a feasible timetable by placing events and reinserting the events they displace. Simulated annealing moves individual events, swaps assignments and exchanges connected groups between two periods. On the curriculum track a separate step also exchanges room labels. Each edition uses the shared annealing step from ShiftOpt.

Install ShiftOpt with `python -m pip install -e .` and run from the repository root. The default budget is 60 seconds and the default seed is 1.

```sh
python -m demos.itc.2007.solve exam demos/itc/2007/exam_comp_set1.exam /tmp/exam.sln
python -m demos.itc.2007.solve tim demos/itc/2007/comp-2007-2-5.tim /tmp/events.sln
python -m demos.itc.2007.solve ctt demos/itc/2007/comp01.ctt /tmp/courses.out
```

| Instance | Python pipeline | Previous UniTime sample |
| --- | ---: | ---: |
| Exam set 1 | 8,088 | 4,496 |
| Post-enrolment set 5 | 1,337 | 7 |
| Curriculum comp01 | 25 | 5 |

All three Python schedules passed independent feasibility and cost checks. These are single-instance results. The full standings below apply to the earlier solver.

[Input archive and validator source](https://github.com/tomas-muller/cpsolver-itc2007) · [Competition standings](https://www.eeecs.qub.ac.uk/itc2007/winner/finalorder.htm) · [Müller's results](https://www.unitime.org/present/patat08itc.pdf)

## Choosing a step

The demo uses a fixed sequence. To let a policy choose between short bursts of single-event moves and exchanges on the same parsed `problem`:

```python
from functools import partial
from operator import itemgetter

from demos.itc.timetable import TimetableMoves, construct
from shiftopt import bandit_policy, run_pipeline, simulated_annealing

score = itemgetter(0)
build = partial(construct, problem, 1, 40)
local = simulated_annealing(TimetableMoves(problem, ("time", "room", "relocate")),
                            score, attempts=1000, temperature=8, seed=1)
exchange = simulated_annealing(TimetableMoves(problem, ("swap", "chain")),
                               score, attempts=1000, temperature=4, seed=2)
policy = bandit_policy([local, exchange], construct=build)
plan = run_pipeline([build, local, exchange], score, policy=policy, max_steps=50, seconds=60)
```

## Previous UniTime pipeline on the full competition set

Each instance received ten runs with a local 60-second pipeline budget. The 2007 Mac calibration program is a 32-bit Intel executable, so the time limit on this Apple Silicon machine is a local choice. The ten run seeds were 1, 3, …, 19. Each run used two consecutive UniTime seeds. Every returned schedule passed a separate constraint and cost check.

| Track | Instances solved at least once | Verified runs | Place alongside the five finalists |
| --- | ---: | ---: | ---: |
| Exams | 12/12 | 114/120 | 1st of 6 |
| Post-enrolment courses | 18/24 | 171/240 | 6th of 6 |
| Curriculum courses | 21/21 | 210/210 | 2nd of 6 |

For each instance, the reconstruction pools our ten runs with the finalists’ fifty. For exams, assigning unsuccessful attempts last place reproduces the published order of the original teams. ShiftOpt also finishes first if unsuccessful attempts share their average rank. On curriculum, Müller leads with a mean rank of 17.881 against ShiftOpt’s 18.083. On post-enrolment, the demo returns no result for incomplete schedules, while the competition could score them by distance to feasibility. The exam result measures two restarts of Müller's UniTime search in ShiftOpt. [Organizers’ report and per-run tables](https://web.archive.org/web/2010id_/http://www.cs.qub.ac.uk/itc2007/winner/finalorder.htm)
