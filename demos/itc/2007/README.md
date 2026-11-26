# ITC 2007 — all three tracks

The Python pipeline first places events and reinserts those they displace. On the post-enrolment track, the default hybrid constructor switches to tabu repair if brief reinsertion leaves events unassigned. Use `--constructor reinsert` to reproduce the earlier post-enrolment experiments. Simulated annealing moves individual events, swaps assignments and exchanges connected groups between two periods. On the curriculum track a separate step also exchanges room labels. Each edition uses the shared annealing step from ShiftOpt.

Install ShiftOpt with `python -m pip install -e .` and run from the repository root. The default budget is 60 seconds and the default seed is 1. Earlier post-enrolment measurements through the first full-track standings table used blocker count alone. Their commands below select it explicitly.

```sh
python -m demos.itc.2007.solve exam demos/itc/2007/exam_comp_set1.exam /tmp/exam.sln
python -m demos.itc.2007.solve tim demos/itc/2007/comp-2007-2-5.tim /tmp/events.sln --no-conflict-memory --event-moves standard
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
python -m demos.itc.2007.solve tim demos/itc/2007/comp-2007-2-5.tim /tmp/tim.sln --seconds 300 --attempts 3000 --policy stagnation --patience 1 --room-repair --no-conflict-memory --event-moves standard
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

## Python standings on the full post-enrolment track

All 24 scored instances used the ten odd seeds 1–19 and a local budget of
60 seconds per trial. Construction received up to 48 seconds. In this earlier comparison, conflict memory was off. Each method
received the same saved start and the remaining wall time for its instance
and seed. Construction succeeded in 123 of 240 trials across 15 instances,
taking a median of 1.25 seconds on successful starts. Nine instances yielded
no complete start. Concurrent local timings are approximate.

The control repeats 50,000-attempt annealing cycles. With `--resume`, the
pipeline regains control every 3,000 attempts while the annealer keeps both
random streams, its current timetable and its position in the 50,000-attempt
cooling cycle. At fixed work, 25 bursts of 2,000 attempts on set 5 reproduced
the entire final timetable of one uninterrupted cycle (penalty 1,337).

| Search | Mean rank among 60 runs per instance | Place among six teams |
| --- | ---: | ---: |
| Repeated long annealing | 51.665 | 6 |
| Resumable annealing | 51.658 | 6 |
| Resumable annealing with stagnation switching | 52.273 | 6 |
| Resumable annealing with penalty-directed event selection | 51.277 | 6 |

Across the 123 paired feasible starts, resumption beat the long control 17
times, tied 91 and lost 15. The median paired difference was zero. Against
resumption alone, switching to hill climbing after one idle burst won 26,
tied 3 and lost 94. Its median paired penalty increased by 47.

Pass `--penalty-events` to the post-enrolment demo to bias event selection.
Half the draws try a random period and sample an event in proportion to the
number of students incurring a single-lecture, late-lecture or consecutive-
lecture penalty there. Empty draws fall back to uniform sampling. The move
types, temperature and cooling cycle stay the same.

Against uniform resumption, this option won 66 paired trials, tied one and
lost 56. The median paired change was −5 penalty points. The median change
favored it on seven instances and favored uniform selection on eight.
Some control trials ran alongside construction jobs. Among the 73 feasible
pairs whose controls ran entirely after construction finished, the directed
step won 38, tied one and lost 34 (median change −2). Its mean competition
rank improved slightly. The demo keeps directed selection opt-in.

Each reconstructed table compares one Python configuration with the five
historical finalists. Runs are ordered by distance to feasibility and then
soft penalty. Missing schedules rank last and ties share the mean rank.
This calculation reproduced all 1,200 published historical run ranks before
inserting Python. The competition validator checked every returned schedule
and its penalty.

```sh
python -m demos.itc.2007.solve tim demos/itc/2007/comp-2007-2-5.tim /tmp/events.sln --seconds 60 --seed 1 --policy repeat --resume --attempts 3000 --cycle-attempts 50000 --no-conflict-memory --event-moves standard
```

## Construction with eviction history

The shared `assignment_constructor` chooses placements, evicts blockers and
requeues them. The timetable adapter supplies eligible period-room pairs and
conflicts. The post-enrolment demo penalizes each previous eviction of the
same event by the same placement. Use `--no-conflict-memory` for blocker count
alone. Exams and curriculum use blocker count alone by default.

On all 24 post-enrolment instances, both constructors had 48 seconds, the same
ten odd seeds and the same item-order and tie-breaking rules. Paired trials
ran concurrently in randomized order. Every complete timetable passed the
competition validator.

| Construction | Verified starts | Instances solved at least once |
| --- | ---: | ---: |
| Blocker count | 133/240 | 15/24 |
| Blocker count plus eviction history | 176/240 | 18/24 |

History added 43 successful starts and retained all 133 paired successes.
It solved set 14 on 10 seeds, set 23 on six and set 24 on ten. On the common
successes the median paired time to feasibility fell by 1.13 seconds and the
median paired change in initial penalty was zero. The previous full-pipeline
experiment had 123 successful starts under its own machine load. The standings
above still refer to that earlier experiment.

### Full-pipeline comparison

Both variants ran through the CLI on all 24 instances and ten odd seeds (1–19)
with 60 local wall-clock seconds per run. Construction could use up to 48
seconds. Resumable annealing used the remaining time, penalty-directed events,
3,000 attempts per burst and 50,000 per cooling cycle. The paired runs differed
only in conflict memory and ran in randomized order with ten concurrent jobs.

| Construction | Valid runs | Instances solved | Mean rank | Place |
| --- | ---: | ---: | ---: | ---: |
| Blocker count | 133/240 | 15/24 | 50.8542 | 6/6 |
| Eviction history | 176/240 | 18/24 | 50.3625 | 6/6 |

The competition validator confirmed all 309 returned schedules and penalties.
History retained all 133 control successes and added 43. On common successes
it won 68, tied seven and lost 58, with a median paired penalty change of −4.

With history, Müller placed fifth at 32.0604. To split the 18.3021 mean-rank
gap, subtract Müller's mean rank on each instance from each of our trial ranks
and divide the sums by 240. The 176 feasible trials contributed 13.4563
points (74%) and the 64 missing schedules contributed 4.8458 (26%).
Reproduce the comparison by running this command with each memory flag:

```sh
python -m demos.itc.2007.solve tim INSTANCE.tim OUTPUT.sln --seconds 60 --seed 1 --policy repeat --resume --attempts 3000 --cycle-attempts 50000 --penalty-events --conflict-memory --event-moves standard
```

## Local search with event displacement

Post-enrolment annealing now samples a displacement move three times as
often as either a period-chain exchange or a room move. To move an event,
it first looks for a free eligible room in the target period. If one event
blocks the move, it tries to rehome that event in the source period or up to
five sampled eligible periods. The timetable checks the combined changes
before annealing scores them. Use `--event-moves standard` to reproduce the
older neighborhood.

Both neighborhoods used the same saved starts (24 instances, ten odd seeds,
eviction history), 60 seconds including the measured construction time,
penalty-directed event selection and resumable annealing at temperature 8.
Each burst used 3,000 attempts and each cooling cycle lasted 50,000.

| Event moves | Valid runs | Instances solved | Mean rank | Place |
| --- | ---: | ---: | ---: | ---: |
| Standard | 177/240 | 18/24 | 50.4125 | 6/6 |
| Displacement mixture | 177/240 | 18/24 | 47.8146 | 6/6 |

Displacement won 157 paired runs, tied one and lost 19. The median penalty
fell by 179 points (median paired reduction 19.4% across the 176 nonzero
baselines). It won 147 of 166 feasible pairs outside the pilot sample. The
median penalty fell on 17 of 18 solved instances. Set 17 rose from 18 to 37.
Müller placed fifth at 32.3708 in the displacement comparison. The competition
validator confirmed all 354 schedules and their penalties.

In a separate seed-1 check with the demo's fixed single annealing burst and
uniform event selection, displacement won 17 of 18 feasible pairs and reduced
the median paired penalty by 127 points. All 36 schedules passed validation.

```sh
python -m demos.itc.2007.solve tim INSTANCE.tim OUTPUT.sln --seconds 60 --seed 1 --policy repeat --resume --attempts 3000 --cycle-attempts 50000 --penalty-events --event-moves displace
```

## Three-event chain finish

Pass `--three-event-finish` on the post-enrolment track to reserve the final
10% of the pipeline budget for the shared `ejection_chain` step. It selects
an event, moves it into a placement that displaces a second event, then moves
the second into a placement that displaces a third. The third must find a
free placement. All three events change period. The demo checks the combined
move and the step retains strict improvements. Each attempt explores at most
13 nodes with depth limited to three.

```sh
python -m demos.itc.2007.solve tim INSTANCE.tim OUTPUT.sln --seconds 300 --construction-seconds 48 --policy repeat --resume --attempts 3000 --penalty-events --three-event-finish
```

The paired comparison used the same saved construction results and charged
their elapsed time to both variants (48-second construction cap). Of the 240
instance-seed pairs, 177 yielded a feasible start across 18 of 24 instances.
At 54 or 270 seconds each pair shared the same incumbent. The control continued
its annealing trajectory for the remaining 6 or 30 seconds. The experimental
branch used that time for three-event chains. The minute and five-minute
finishes branched independently from the control trajectory.

| Total budget | Annealing mean rank | Chain finish mean rank | Chain wins / ties / losses | Feasible three-event proposals scored | Strict improvements accepted |
| --- | ---: | ---: | ---: | ---: | ---: |
| 60 s | 48.1375 | 48.3833 | 44 / 51 / 82 | 8,655,649 | 286 |
| 300 s | 43.2646 | 43.3979 | 39 / 85 / 53 | 52,698,407 | 245 |

Each configuration placed sixth of six. Counts include repeated proposals.
On 19 pairs the finish beat the control at five minutes after tying or losing
at one minute. Extending ordinary annealing from one to five minutes reduced
the median paired penalty by 142 points (18.3% median relative reduction
among nonzero minute scores). The chain finish stays opt-in.

A separate 15-minute run covered sets 5, 17 and 20 with seeds 1 and 3.
The 90-second finish won twice, tied three times and lost once. On set 5,
seed 3, the annealing and chain scores were respectively 640 and 738 at one
minute, 40 and 54 at five minutes, and 2 and 1 at fifteen minutes. The lowest
published finalist score on that instance was 5 under the original competition
conditions. The validator confirmed all 708 full-track checkpoint schedules
and all 36 checkpoints in the extended sample. The 15-minute sample has no
full-track place.

## Search with temporarily unroomed events

Add `--partial-rooms` to a `tim` run to reserve the final 10% of the time
budget for this step. A move may take an occupied room and leave its previous
occupant without a room. Later moves can repair that event or move another.
The search adds eight points per missing room when deciding whether to accept
a move. Only timetables with every event assigned a room reach the pipeline.

On sets 5, 8 and 14 (seeds 1 and 3), both finishes started from the same
archived 270-second timetable for each pair. After 30 further seconds the
partial-room finish tied continued annealing three times and lost three times.
It retained the starting score on all six runs.

A second comparison gave each step a fresh 300 seconds from the set 5
checkpoints. The competition validator checked all final schedules and scores.

| Seed | Starting penalty | Ordinary annealing | Partial-room search |
| ---: | ---: | ---: | ---: |
| 1 | 410 | 374 | 410 |
| 3 | 40 | 3 | 40 |

In the first 50,000 attempts on these starts, the new search entered a
partial timetable 11 and 18 times, respectively. These runs support keeping
the room move optional. They cover a sample of the post-enrolment track.

## Mixed search against UniTime

Run the same command with `--mixed-rooms strict` and `--mixed-rooms relaxed`:

```sh
python -m demos.itc.2007.solve tim demos/itc/2007/comp-2007-2-5.tim /tmp/events.sln \
    --seconds 300 --policy repeat --resume --attempts 3000 --penalty-events --seed 1 --mixed-rooms relaxed
```

From a complete timetable, each attempt samples the ordinary moves with
probability 0.9 and the room-repair move with probability 0.1. Strict mode
discards any proposal that leaves an event without a room. Relaxed mode can
accept it at an eight-point penalty per missing room and uses room-repair
moves until it reaches a complete timetable or the annealing cycle restarts.

Each row below used a 300-second budget. The ShiftOpt pair reused the same
saved construction and charged its elapsed time to both runs. Each UniTime
run started from scratch with the same seed and a 300-second solver timeout.
The Java control changed only `-DTim.AllowNoRoom=false`. All four columns
give soft penalties confirmed by the competition validator.

| Set | Seed | ShiftOpt strict | ShiftOpt relaxed | UniTime, rooms required | UniTime, default |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 5 | 1 | 98 | 471 | 39 | 16 |
| 5 | 3 | 568 | 267 | 125 | 0 |
| 8 | 1 | 220 | 333 | 0 | 1 |
| 8 | 3 | 0 | 0 | 45 | 92 |
| 14 | 1 | 787 | 817 | 434 | 138 |
| 14 | 3 | 1,079 | 991 | 219 | 461 |

Against its strict control, ShiftOpt relaxed won two pairs, tied one and lost
three. With a fixed budget of 500,000 proposals per run on the same six starts,
it won one and lost five. UniTime's default room setting won three pairs and
lost three against its own control at 300 seconds. These six pairs do not
establish a track ranking.

Two warm starts isolated local search on set 5. Both solvers received the
same complete ShiftOpt timetables (initial penalties 1,786 and 1,876).
At the one-minute checkpoint the strict/relaxed ShiftOpt penalties were
686/793 and 771/758. Given 59 seconds after construction, UniTime reached
355 and 47. Its trace first beat the better ShiftOpt minute score with a
fully feasible timetable after 4.53 and 4.34 seconds, respectively. Both
traces visited schedules with precedence violations. The current ShiftOpt
room move enforces precedence at every proposal. The warm starts locate a
gap in local search; they do not isolate the contributions of move choice,
constraint penalties, phase scheduling or implementation speed.

[UniTime competition configuration](https://github.com/tomas-muller/cpsolver-itc2007/blob/a253a5a/src/tim.properties)

## Temporary precedence violations

Use `--precedence relaxed` in place of `--mixed-rooms relaxed` in the command
above. The constructor still enforces every prerequisite. During annealing,
each pair scheduled in reverse order or at the same time adds
`--precedence-weight` points to the acceptance cost (default 8). Rooms, availability and student conflicts stay hard.
The pipeline keeps only schedules that satisfy every prerequisite. The paired
`--precedence strict` control generates moves the same way and discards any
proposal with a violated prerequisite.

With 500,000 proposals on sets 5, 8 and 14 (seeds 1 and 3), weight 8 beat the
strict control once and lost five times. On set 5, 99.8% and 99.9% of attempts
started from an out-of-order timetable. With weight 32 these shares fell to
16.8% and 14.3%. The best feasible penalties were 768 and 624, versus 760 and
656 for the strict control. Before the occupancy fix below, extending both
searches to 15 minutes gave 1,403 and 1,415 at weight 8, versus 557 and 278
for strict. The ordinary search checks precedence while generating a move
and can try another placement within the same attempt.

### Search speed and quality from identical starts

Set 5 started at penalties 1,786 (seed 1) and 1,876 (seed 3). UniTime loaded
the same two complete schedules as ShiftOpt. The table reports validator-checked
soft penalties from local wall-clock runs. Each ShiftOpt column uses ordinary
annealing with displacement moves and penalized-event selection.

| Seed | UniTime 59 s | ShiftOpt 59 s | UniTime 5 min | ShiftOpt 5 min | ShiftOpt 10 min | ShiftOpt before fix, 15 min |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 355 | 437 | 140 | 311 | 61 | 311 |
| 3 | 47 | 347 | 47 | 2 | 2 | 2 |

ShiftOpt first reached the two 59-second UniTime scores at burst boundaries
after 245 and 131 seconds. Before the fix it needed 662 and 239 seconds for
the same targets. With ten minutes it beat both five-minute UniTime results
in this two-start comparison. The experiment does not estimate a track rank.

An unchanged timetable used to trigger a full occupancy rebuild after an
unsuccessful attempt. Keeping the occupancy reduced builds from 20,074 to one
in the first 50,000 attempts on seed 1. Over four alternating 200,000-attempt
runs (two seeds, each repeated twice), mean CPU time fell from 14.35 to
4.59 seconds. The best and current plans and both random generators matched
every 50,000 attempts through 500,000 on both seeds. Separately, compiling
the three original hot modules unchanged with Cython 3.3.2 gave a 1.15×
CPU speedup. The cache fix runs in plain Python.

A separate instrumented comparison counted transitions to a different
timetable, ignoring proposals that left assignments unchanged. After 500,000
transitions, ShiftOpt had penalties 437 and 376 after 36.1 and 35.6 seconds.
UniTime had 975 and 994 after 3.72 and 3.69 seconds. A transition can change
multiple events; the two solvers do different work per transition. Times
are local to this machine and include the observation overhead.

### Time and transitions to a target penalty

From the same feasible starts, each solver had five minutes to halve and
quarter the initial penalty (rounded down). Counts below include transitions
to a different timetable. Each reached threshold passed the competition
validator. A dash means the solver missed the target within the budget.

| Set / seed | Halve: ShiftOpt | Halve: UniTime | Quarter: ShiftOpt | Quarter: UniTime |
| --- | ---: | ---: | ---: | ---: |
| 5 / 1 | 90,118 | 579,057 | 356,455 | 1,451,674 |
| 5 / 3 | 112,121 | 582,439 | 338,007 | 1,213,459 |
| 8 / 1 | 4,232 | 369,862 | 64,998 | 754,869 |
| 8 / 3 | 5,947 | 255,453 | 26,893 | 612,494 |
| 14 / 1 | 1,715,484 | 20,641,068 | — | — |
| 14 / 3 | 3,814,866 | 15,121,447 | — | 46,909,135 |

Each solver reached the halfway target first on three starts in the timed
traces. For example, set 5 / seed 1 reached penalty 893 in 4.54 s with
ShiftOpt and 3.15 s with UniTime. On set 8 / seed 1 the times to penalty
835 were 0.39 and 3.39 s. These traces used ShiftOpt before the event draw
cache described below. Transition counts include plateau moves and depend
on how many assignments one move changes.

Across the first million attempts on each start, displacements accounted
for 5,488 points of incumbent improvement and period chains for 1,528.
Room-only moves contributed zero points directly. Rejecting those proposals
while keeping the same sampling weights worsened the final penalty on all
six starts; on set 5 the two scores rose from 437 and 376 to 678 and 653.

The event selector now reuses the weighted draw for a period while the day's
event assignments match. In alternating runs on set 5, mean CPU time for
500,000 attempts fell from 13.66 to 11.41 s. On sets 8 and 14 (seed 1),
200,000 attempts took 6.05 and 6.36 s before, and 5.27 and 5.23 s after.
The replay matched every proposal and acceptance decision, plus the incumbent
and both random generators at cycle boundaries, for 500,000 attempts on
each of the six starts. In paired five-minute runs on set 5, the old and
new selectors both finished at penalties 311 and 8 (seeds 1 and 3).

### Full post-enrolment standings at fifteen minutes

ShiftOpt `65ea27b` ran ordinary annealing on the 24 instances with seeds
1, 3, …, 19. The local 900-second limit per start included the recorded
construction time (48-second construction cap). Each run continued from
its own five-minute checkpoint and could stop at zero penalty. The competition
validator checked all 177 complete schedules at both checkpoints. The remaining
63 starts had no complete timetable. Historical finalist scores were held
fixed. Lower mean rank is better.

| Place | Solver | ShiftOpt at 5 min | ShiftOpt at 15 min |
| ---: | --- | ---: | ---: |
| 1 | Cambazard | 14.8146 | 15.2125 |
| 2 | Atsuta | 27.6208 | 28.1479 |
| 3 | Chiarandini | 31.6833 | 32.1417 |
| 4 | Nothegger | 33.0792 | 33.4792 |
| 5 | Müller | 33.8563 | 34.4521 |
| 6 | ShiftOpt | 41.9458 | 39.5667 |

The extra time improved 128 of 177 valid runs across 18 solved instances;
the number with zero penalty rose from 14 to 21. Of the 5.1146 mean-rank
gap to Müller at fifteen minutes, 4.7042 points came from the 63 failed
starts, comparing each start with Müller's mean rank on its instance.

### Repairing incomplete post-enrolment timetables

We repeated construction on all 24 instances with the same ten odd seeds and
48-second construction budget. The hybrid gives reinsertion up to four seconds,
then starts tabu repair from a complete assignment that can contain conflicts.
The search relocates conflicting events and raises the weights of persistent
violations after stagnation. The competition validator checked every returned
schedule for feasibility and soft cost.

| Instance | Earlier reinsertion | Hybrid | Historical Müller finalist |
| --- | ---: | ---: | ---: |
| 1 | 0/10 | 10/10 | 3/10 |
| 2, 9, 10, 19 (each) | 0/10 | 10/10 | 0/10 |
| 22 | 0/10 | 8/10 | 6/10 |
| 23 | 7/10 | 10/10 | 10/10 |
| Other 17 (combined) | 170/170 | 170/170 | — |
| All | 177/240 | 238/240 | — |

Counts are complete feasible schedules. The historical column counts runs with
zero distance to feasibility in the organizers’ tables. In a separate local
48-second UniTime run on seed 15, only instance 1 reached feasibility among
these seven. The hybrid solved all seven on that seed.

On instance 22, reinsertion reached 550 of 600 events on seed 15. Among the
50 remaining events, 30 had no eligible period free of student clashes.
All 50 had a free eligible room in at least one eligible period when student
and ordering constraints were ignored. A hybrid with fixed conflict weights
solved only one of ten starts on this instance. Adaptive weights solved eight.
The two failures on instance 22 (seeds 13 and 17) both passed on a separate
retry with a 90-second construction budget, after 35 and 62 seconds of wall
time. These retries are excluded from the 48-second tally.
This benchmark measures construction. The fifteen-minute standings above
belong to the earlier solver.

```sh
python -m demos.itc.2007.solve tim INSTANCE.tim OUTPUT.sln --constructor hybrid --seed 15 --seconds 60 --construction-seconds 48 --attempts 0
```

### Hybrid standings at twenty seconds

ShiftOpt ran all 24 post-enrolment instances on seeds 1, 3, …, 19 with
20 local seconds per start, including up to 16 seconds for construction.
The competition validator confirmed feasibility and penalty for 234 of 240
starts. All six misses were on instance 22. Each instance had at least
one valid schedule. Pooling the ten starts with the fifty archived finalist
scores on each instance gave the following mean ranks (lower is better).

| Place | Solver | Mean rank |
| ---: | --- | ---: |
| 1 | Cambazard | 14.6958 |
| 2 | Atsuta | 27.5104 |
| 3 | Chiarandini | 30.6042 |
| 4 | Nothegger | 32.9104 |
| 5 | Müller | 34.2542 |
| 6 | ShiftOpt | 43.0250 |

ShiftOpt ranked ahead of Müller on instances 1, 2, 9, 10, 12, 17 and 19.
The twenty-second limit applies to ShiftOpt. The finalists retain their
published competition scores.

```sh
python -m demos.itc.2007.solve tim INSTANCE.tim OUTPUT.sln --seed 1 --seconds 20 --construction-seconds 16 --policy repeat --resume --attempts 3000 --penalty-events
```

### Hybrid standings at five minutes

Each of the 240 starts ran from scratch with a 300-second local budget and up
to 90 seconds for construction. The twenty-second experiment above used a
16-second construction cap. Both runs used the same 24 instances, ten seeds,
annealing settings and archived finalist scores. The competition validator
accepted 239 schedules, including 14 with zero soft penalty. Only instance
22, seed 17, exhausted construction without a feasible schedule.

| Place | Solver | Mean rank |
| ---: | --- | ---: |
| 1 | Cambazard | 15.3167 |
| 2 | Atsuta | 28.9625 |
| 3 | Chiarandini | 32.4813 |
| 4 | Nothegger | 34.0812 |
| 5 | Müller | 36.0375 |
| 6 | ShiftOpt | 36.1208 |

ShiftOpt led Müller on 11 of 24 instances. Its overall gap to fifth fell from
8.7708 at twenty seconds to 0.0833 at five minutes. To reproduce a start,
use the command above with `--seconds 300 --construction-seconds 90`.

## Previous UniTime pipeline on the full competition set

Each instance received ten runs with a local 60-second pipeline budget. The 2007 Mac calibration program is a 32-bit Intel executable, so the time limit on this Apple Silicon machine is a local choice. The ten run seeds were 1, 3, …, 19. Each run used two consecutive UniTime seeds. Every returned schedule passed a separate constraint and cost check.

| Track | Instances solved at least once | Verified runs | Place alongside the five finalists |
| --- | ---: | ---: | ---: |
| Exams | 12/12 | 114/120 | 1st of 6 |
| Post-enrolment courses | 18/24 | 171/240 | 6th of 6 |
| Curriculum courses | 21/21 | 210/210 | 2nd of 6 |

For each instance, the reconstruction pools our ten runs with the finalists’ fifty. For exams, assigning unsuccessful attempts last place reproduces the published order of the original teams. ShiftOpt also finishes first if unsuccessful attempts share their average rank. On curriculum, Müller leads with a mean rank of 17.881 against ShiftOpt’s 18.083. On post-enrolment, the demo returns no result for incomplete schedules, while the competition could score them by distance to feasibility. The exam result measures two restarts of Müller's UniTime search in ShiftOpt. [Organizers’ report and per-run tables](https://web.archive.org/web/2010id_/http://www.cs.qub.ac.uk/itc2007/winner/finalorder.htm)
