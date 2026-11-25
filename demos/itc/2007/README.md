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

## One minute versus five minutes

With seed 1 and `--seconds 300`, the default pipeline finished in 1.6–23.8 seconds across the three instances. Each run exhausted its 50,000 annealing attempts. A separate experiment repeated the same annealing step from the best timetable, starting each step at temperature 8 with the next integer seed. The 60-second checkpoint includes construction. Each run continued from that checkpoint to 300 seconds. Independent checks confirmed feasibility and cost at both checkpoints.

| Instance | Default | 60 seconds | 300 seconds | Previous UniTime sample |
| --- | ---: | ---: | ---: | ---: |
| Exam set 1 | 8,088 | 6,246 | 5,712 | 4,496 |
| Post-enrolment set 5 | 1,337 | 963 | 722 | 7 |
| Curriculum comp01 | 25 | 16 | 15 | 5 |

## Comparing local search steps

Pass `--search greedy|hill|deluge|anneal` and `--attempts N` to the demo.
All four steps sample the same timetable moves. Greedy accepts strict improvements,
hill climbing also accepts ties, Great Deluge uses a falling cost ceiling, and
annealing uses a temperature. Annealing is the default.

The table gives median final penalties over seeds 1, 2 and 3 at 5,000 move
attempts per method. Each method started from the same timetable within each
instance and seed. Great Deluge used a linear ceiling from starting cost + 8
to zero. Annealing started at temperature 8. This comparison uses one instance
per track and a fixed move budget.

| Instance | Greedy | Hill climbing | Great Deluge | Annealing |
| --- | ---: | ---: | ---: | ---: |
| Exam set 1 | 11,987 | 11,962 | 13,157 | **11,814** |
| Post-enrolment set 5 | 1,599 | **1,577** | 1,605 | 1,584 |
| Curriculum comp01 | 496 | **307** | 506 | 342 |

## Incremental scores and targeted moves

Local moves now update the penalties of the affected student days, exam pairs and
rooms, or curriculum days and courses. The full objective remains available for
construction and independent checks. At 5,000 attempts, full and incremental
scoring returned identical plans for both hill climbing and annealing on seeds
1, 2 and 3. Median local-search speedups were 3.2× on exam set 1, 1.5× on
post-enrolment set 5 and 2.6×, 5.7× and 7.2× on curriculum comp01–03.

On comp01, a separate 60-second hill-climbing step with the attempt cap lifted
made a median of 2.91 million attempts with incremental scoring versus 0.91
million with full scoring. Across seeds 1–3 the final penalties were 5, 5, 5
versus 5, 6, 5. The six schedules passed the competition validator.

For curriculum timetables, `--compactness` reserves the final 10% of move
attempts for a separate hill-climbing step. It finds an isolated lecture and
tries to place it next to another lecture in the same curriculum and day.
To use it with another acceptance rule or a step policy, pass
`TimetableMoves(problem, ("compact",))` to the search step.

```sh
python -m demos.itc.2007.solve ctt demos/itc/2007/comp01.ctt /tmp/comp01.sln --search anneal --attempts 5000 --compactness
```

At 5,000 total attempts the targeted finish improved 3 of 18 paired runs
(three instances, three seeds, two search methods). With annealing, median
penalty changed from 342 to 508 on comp01, from 982 to 1,297 on comp02 and
from 548 to 502 on comp03. All targeted schedules passed the competition
validator. The directed step is opt-in.

## Choosing a step

The default demo uses a fixed sequence. To let a policy choose between short bursts of single-event moves and exchanges on the same parsed `problem`:

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

### Switching on stagnation

`--policy repeat` repeats the chosen search method with successive seeds.
`--policy stagnation` starts with that method and switches to hill climbing
(or to annealing when starting with hill climbing). Each burst gets
`--attempts` proposals. After `--patience` consecutive bursts without a strict
improvement, the policy advances to the next step, cycling back to the first.
Construction and all bursts share the wall-clock budget.

On the post-enrolment track, `--room-repair` adds a separate step. It swaps a
connected group of events between two periods and temporarily releases all
rooms in those periods. It checks period availability and precedence, then
uses bipartite matching to assign distinct eligible rooms. Only a complete
matching can produce a proposal. The generic `neighborhood_search` step
handles acceptance and retains the best feasible timetable.

```sh
python -m demos.itc.2007.solve tim demos/itc/2007/comp-2007-2-5.tim /tmp/tim.sln --seconds 300 --attempts 3000 --policy stagnation --patience 1 --room-repair
```

Each run below used 300 seconds including construction, 3,000 attempts per
burst and patience 1. Values are final penalties in seed order (1, 2, 3).
Within each seed all methods started from the same timetable.

| Instance | Repeated annealing | Repeated hill climbing | Switch on stagnation | Switch with room repair |
| --- | --- | --- | --- | --- |
| Curriculum comp01 | 25, 26, 28 | 8, 7, 6 | 6, 6, 6 | — |
| Post-enrolment set 5 | 1,146, 1,074, 1,032 | — | 1,147, 1,162, 1,189 | 1,167, 1,249, 1,147 |

On post-enrolment set 5, the repair step directly removed 26, 49 and 52 penalty
points during its three runs. The final timetable beat switching alone on one
seed. Repeated annealing scored best on all three. At 50,000 attempts per
burst, seed 1 scored 713 with repeated annealing, 883 with switching and 893
with switching plus repair. Competition validators confirmed all 21 schedules
and their penalties. Both switching and room repair remain opt-in.

## Previous UniTime pipeline on the full competition set

Each instance received ten runs with a local 60-second pipeline budget. The 2007 Mac calibration program is a 32-bit Intel executable, so the time limit on this Apple Silicon machine is a local choice. The ten run seeds were 1, 3, …, 19. Each run used two consecutive UniTime seeds. Every returned schedule passed a separate constraint and cost check.

| Track | Instances solved at least once | Verified runs | Place alongside the five finalists |
| --- | ---: | ---: | ---: |
| Exams | 12/12 | 114/120 | 1st of 6 |
| Post-enrolment courses | 18/24 | 171/240 | 6th of 6 |
| Curriculum courses | 21/21 | 210/210 | 2nd of 6 |

For each instance, the reconstruction pools our ten runs with the finalists’ fifty. For exams, assigning unsuccessful attempts last place reproduces the published order of the original teams. ShiftOpt also finishes first if unsuccessful attempts share their average rank. On curriculum, Müller leads with a mean rank of 17.881 against ShiftOpt’s 18.083. On post-enrolment, the demo returns no result for incomplete schedules, while the competition could score them by distance to feasibility. The exam result measures two restarts of Müller's UniTime search in ShiftOpt. [Organizers’ report and per-run tables](https://web.archive.org/web/2010id_/http://www.cs.qub.ac.uk/itc2007/winner/finalorder.htm)
