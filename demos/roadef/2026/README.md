# ROADEF/EURO 2026 · Keep the Flow

The search builds a route set shared across periods, then refines it for each period within the reconfiguration budget.

After installing `.[roadef]`, run the commands from this directory. For setX-02 and setX-03, change `case_id` and replace `solve.py` with `run_static.py`, which stores identical routing-table rows once.

```sh
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 NUMBA_NUM_THREADS=1
work=$(mktemp -d)
case_id=setX-01
python solve.py data "$case_id" --seconds 120 --output "$work/static.json"
python refine.py data "$case_id" "$work/static.json" "$work/plan.json"
checker124 --net "data/$case_id-net.json" --tm "data/$case_id-tm.json" \
  --scenario "data/$case_id-scenario.json" --srpaths "$work/plan.json" \
  --max-decimal-places 6 > "$work/check.json"
python rank.py "$case_id" "$work/check.json" qualification_results/readme.md \
  qualification_results/log qualification_results/loads_vector.csv
```

The inputs in `data/` come from snapshot `8362c373`. The organizers provide checker v1.2.4 and the files used by `rank.py`. [Official materials and checker](https://roadef.org/challenge/2026/en/material.php) · [Qualification results](https://gitlab.com/Orange-OpenSource/network-optimization-tools/challenge-roadef-2026/-/tree/8362c373f3dba5733af02f30ab01160afa089b41/qualification_results).

The checker accepted all three plans in the original benchmark. Each rank shows where our plan would place among the published qualification results for that instance. Link loads are sorted from highest to lowest and compared lexicographically.

| Instance | Rank | Leader | First differing link load (ours / leader) |
|---|---:|---|---:|
| setX-01 | 36 | J156 | #1 · 38.8174% / 38.8170% |
| setX-02 | 46 | J156 | #8 · 33.4454% / 33.1240% |
| setX-03 | 46 | S33 | #2 · 40.6091% / 34.6417% |
