# ROADEF/EURO 2018 · Glass Cutting

ShiftOpt scored **134 points, placing 7th of 20** in the B+X final comparison. S6 is sixth with 138 points. The official checker accepted all 90 plans in a three-way comparison on the 30 instances. With a shared 170-second search budget on the same Mac, beam search scored 121, bounded best-first search scored 111, and running beam followed by best-first scored 134. The combined search reduced waste on 11 instances and tied on 19 compared with beam alone. [Per-instance comparison](search.csv) · [Official standings and workbook](https://roadef.org/challenge/2018/en/finalResults.php).

The default pipeline runs five stages.

1. `strips` uses `shiftopt.select_candidates` to pack ordered stack prefixes. Each selection has a 40 ms budget.
2. `shelves` builds an independent plan with multiple items per row.
3. `repair` rebuilds the last four plates of the best plan.
4. `beam` searches item placements one at a time. At each depth it keeps alternative partial layouts ranked by estimated waste, allowing the active strip to widen as rows grow. It tries beam widths of 12, 48 and 128 under the shared deadline.

5. `imba` explores partial cuts from different depths in one priority queue. It restarts with capacities 1, 4, 16, 64 and 256. The used plate width gives a lower bound independently of the waste-density guide.

In the earlier four-stage benchmark, compared with the archived three-stage run, waste fell on 29 instances, with a median reduction of 52.6% across all 30. [Four-stage results](beam.csv) · [Three-stage results](pipeline.csv) · [Original strip baseline](benchmark.csv).

For that four-stage benchmark, the official checker accepted all 30 plans. Wall time on one pinned Intel Core i7-10750H core included Python startup and file I/O, with a median of 23.06 s and a maximum of 167.90 s. All runs finished within three minutes. We used the same plan for both time limits and compared its waste with each team's weighted result (10% at three minutes and 90% at one hour). We recalculated the top-ten points for every team after adding ShiftOpt. [Competition rules](https://roadef.org/challenge/2018/files/Challenge_Rules.pdf).

Choose a subset or order with `--stages`. The default shared search budget is `--seconds 170`.

Install the package from the repository root with `python -m pip install .`. From this directory, generate a plan and check it using the organizers' C++ checker and GNU g++ on Linux. [Official data and checker](https://roadef.org/challenge/2018/en/instances.php).

```sh
work=$(mktemp -d)
unzip -q data/dataset_B.zip -d "$work"
unzip -q data/dataset_X.zip -d "$work"
curl -fsSL https://roadef.org/challenge/2018/files/checker.zip -o "$work/checker.zip"
unzip -q "$work/checker.zip" -d "$work"
cp "$work"/dataset_{B,X}/*.csv "$work/instances_checker/"
case_id=B2
python solve.py "$work/instances_checker" "$case_id" "$work/instances_checker/${case_id}_solution.csv"
(cd "$work" && g++ -std=gnu++11 -O2 -Iinclude src/*.cpp -o checker && ./checker "$case_id" 0)
```
