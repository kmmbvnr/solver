# ROADEF/EURO 2020 · Maintenance scheduling

Schedule each intervention once, respecting the workload bounds and seasonal exclusions. ShiftOpt builds a mixed-integer schedule with a mean-risk objective. For large scenario arrays or a failed construction, it repairs resource and exclusion conflicts directly. During repair, temporary capacity margins and higher penalties on persistently overloaded periods guide the search. Feasibility is tested against the original limits. Use `--repair-first` to select this constructor explicitly. A second stage changes start dates using the official scenario quantiles. At a local minimum it perturbs several feasible starts and retains the best complete schedule.

Install from the repository root with `python -m pip install '.[roadef]'`. From this directory, reproduce the first final instance and check the schedule with RTE's checker.

```sh
work=$(mktemp -d)
unzip -q data/C_01.zip -d "$work"
python solve.py "$work/C_01.json" "$work/plan.txt" --refine-seconds 90
base=https://raw.githubusercontent.com/rte-france/challenge-roadef-2020/052def4d47271f913f89a68169083059732360f3
curl -fsSL "$base/RTE_ChallengeROADEF2020_checker.py" -o "$work/checker.py"
python "$work/checker.py" "$work/C_01.json" "$work/plan.txt"
```

The full final comprises the 15 C and 15 X instances. Download `C_compact.7z`, `X_compact_1_1.7z` and `X_compact_1_2.7z` from the same pinned source and extract them with 7-Zip. [Official datasets](https://roadef.org/challenge/2020/en/instances.php) · [Final standings](https://roadef.org/challenge/2020/en/finalresult.php).

The official checker accepted all 30 final schedules. Inserting ShiftOpt into the published C+X results gives **13th of 14 with 20 points**, ahead of S28 (11). S34 leads with 291. The strongest instance was X_04, sixth with an objective of 12,010.566. Each ShiftOpt plan finished within 394 seconds, so its objective serves at both official checkpoints. The comparison uses each competitor's published weighted objective (80% at 15 minutes and 20% at 90 minutes). These retrospective runs used different hardware from the competition. [Per-instance results](benchmark.csv).

The table records the construction budget (`--seconds`) and host. Use `--repair-first` for direct construction and `--plain-repair` for rows with fixed conflict penalties (`plain_repair=1`). Every row uses `--refine-seconds 90`. Time-limited searches can vary across runs.
