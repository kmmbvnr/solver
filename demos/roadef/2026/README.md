# ROADEF/EURO 2026 · Keep the Flow

ShiftOpt produced feasible plans for all 56 published instances. The official checker accepted 20 from set A and 12 each from B, C, and X. The benchmark records the peak link load, number of explicit routes, solution hash, and available comparisons with competitors. [Per-instance results](benchmark.csv).

| Phase | Instances | ShiftOpt points | Rank if included | Winner |
|---|---:|---:|---|---|
| Sprint (A) | 20 | 0 | Joint 30th of 54 | S22, 266 points |
| Qualification (X) | 12 | 0 | Joint 31st of 74 | S33, 153 points |

Each instance awards one point for 15th place and up to 15 points for first. The checker sorts link loads in descending order for lexicographic comparison. Where published comparisons leave a rank interval, both ends give the same score. The organizers publish separate standings for A and X. B and C are development sets. The final evaluation uses set Y, scheduled for February 2027. [Official datasets and schedule](https://gitlab.com/Orange-OpenSource/network-optimization-tools/challenge-roadef-2026/-/tree/8362c373f3dba5733af02f30ab01160afa089b41) · [Sprint standings](https://gitlab.com/Orange-OpenSource/network-optimization-tools/challenge-roadef-2026/-/tree/8362c373f3dba5733af02f30ab01160afa089b41/sprint_results) · [Qualification standings](https://gitlab.com/Orange-OpenSource/network-optimization-tools/challenge-roadef-2026/-/tree/8362c373f3dba5733af02f30ab01160afa089b41/qualification_results).

## Reproduce a plan

Install `.[roadef]` from the repository root. Run from this directory with official checker v1.2.4. The sparse search uses ShiftOpt to choose waypoint changes near congested links. It keeps a plan when the checker confirms feasibility and a better load vector. [Checker downloads](https://gitlab.com/Orange-OpenSource/network-optimization-tools/challenge-roadef-2026/-/releases).

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
