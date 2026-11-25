# ROADEF/EURO 2026 · Keep the Flow

ShiftOpt produced feasible plans for all 56 published instances. The official checker accepted 20 from set A and 12 each from B, C, and X. The benchmark records the peak link load, number of explicit routes, solution hash, and available comparisons with competitors. [Per-instance results](benchmark.csv).

| Phase | Instances | ShiftOpt points | Rank if included | Winner |
|---|---:|---:|---|---|
| Sprint (A) | 20 | 0 | Joint 30th of 54 | S22, 266 points |
| Qualification (X) | 12 | 0 | Joint 31st of 74 | S33, 153 points |

Each instance awards one point for 15th place and up to 15 points for first. The checker sorts link loads in descending order for lexicographic comparison. Where published comparisons leave a rank interval, both ends give the same score. The organizers publish separate standings for A and X. B and C are development sets. The final evaluation uses set Y, scheduled for February 2027. [Official datasets and schedule](https://gitlab.com/Orange-OpenSource/network-optimization-tools/challenge-roadef-2026/-/tree/8362c373f3dba5733af02f30ab01160afa089b41) · [Sprint standings](https://gitlab.com/Orange-OpenSource/network-optimization-tools/challenge-roadef-2026/-/tree/8362c373f3dba5733af02f30ab01160afa089b41/sprint_results) · [Qualification standings](https://gitlab.com/Orange-OpenSource/network-optimization-tools/challenge-roadef-2026/-/tree/8362c373f3dba5733af02f30ab01160afa089b41/qualification_results).

## Reproduce a plan

Install `.[roadef]` from the repository root. Run from this directory with official checker v1.2.4. The sparse search uses ShiftOpt to choose waypoint changes near congested links. The pipeline starts with default routes. Each round proposes waypoint changes, the checker reports feasibility and link loads, and the pipeline retains lexicographic improvements. The dense and shared static modes use the same pipeline with their internal load estimates. Period refinement starts from a static seed and proposes changes one period at a time. [Checker downloads](https://gitlab.com/Orange-OpenSource/network-optimization-tools/challenge-roadef-2026/-/releases).

```sh
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 NUMBA_NUM_THREADS=1
work=$(mktemp -d)
case_id=setX-04
python sparse_search.py data "$case_id" ./checker124 "$work/plan.json"
```

For rows marked `period`, append `--period-only --rounds 12`. The three original qualification runs use a static route pool followed by per-period refinement. Use `solve.py` for the `dense` row and `run_static.py` for the two `shared` rows.

```sh
case_id=setX-01
python solve.py data "$case_id" --seconds 120 --output "$work/static.json"
python refine.py data "$case_id" "$work/static.json" "$work/plan.json"
```

## Check and rank a plan

Use checker v1.2.4 with the qualification results for X. For the sprint, use checker v1.2.2 and the corresponding files from `sprint_results/`.

```sh
./checker124 --net "data/$case_id-net.json" --tm "data/$case_id-tm.json" \
  --scenario "data/$case_id-scenario.json" --srpaths "$work/plan.json" \
  --max-decimal-places 6 > "$work/check.json"
python rank.py "$case_id" "$work/check.json" qualification_results/readme.md \
  qualification_results/log qualification_results/loads_vector.csv
```

A pilot tried 12 waypoint proposals from each saved plan on A01–A05 and X07, keeping one or two plans per layer for three layers. Both widths improved the checker's lexicographic load vector on all six instances. Width 1 beat width 2 on A02, A03 and A05 and tied on the others. Both lowered the peak on X07 from 0.437521 to 0.368036, moving from 55th to 53rd on that instance. None of these six runs reached the top 15 needed for points.

## Choosing waypoint moves

Pass `--policy adaptive --rounds 12` to start with a shared waypoint move, repeat the last operator after an improvement, and switch between shared and single-period moves after a miss. Use `--policy alternate` for fixed alternation.

All four modes started from default routing and made 12 proposals per instance. The sprint checker v1.2.2 accepted all 80 plans. Counts compare the adaptive plan's full load vector with each baseline. The last ten instances were held out of the pilot.

| Baseline | Better / tied / worse on A01–A20 | Better / tied / worse on A11–A20 |
|---|---:|---:|
| Shared moves only (default) | 11 / 3 / 6 | 3 / 3 / 4 |
| Single-period moves only | 19 / 0 / 1 | 10 / 0 / 0 |
| Fixed alternation | 15 / 1 / 4 | 7 / 0 / 3 |

The adaptive run earned 0 sprint points. Its closest result was A11, between 18th and 21st. These runs used equal proposal counts and had no wall-clock limit.

For a learning baseline, pass `--policy bandit --rounds 12`. UCB tries both operators and balances mean reward against an exploration bonus (coefficient 0.15). For accepted moves, the reward is the relative reduction at the first differing position of the sorted load vector. With the same seed, starting plan and 12 proposals, UCB beat the manual adaptive policy on 3 of 20 sprint instances, tied on 1 and lost on 16. On A11–A20 the counts were 2 / 0 / 8. Checker v1.2.2 accepted all 40 plans.
