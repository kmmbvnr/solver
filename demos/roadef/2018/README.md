# ROADEF/EURO 2018 · Glass Cutting

The official checker accepted all three stage proposals on each of the 30 final instances. Compared with the strip constructor in the same run, the pipeline reduced waste on 29 instances, with a median reduction of 26.6% across all 30. The best instance rank improved from 13th in the archived baseline to 12th. ShiftOpt still scored **0 points**. The workbook labels the four-way tie for last **20th of 20**. J28 won with 286 points. [Pipeline results](pipeline.csv) · [Archived baseline](benchmark.csv) · [Official standings](https://roadef.org/challenge/2018/en/finalResults.php).

The default pipeline runs three stages in order.

1. `strips` uses `shiftopt.select_candidates` to pack stack prefixes in the largest clear band of a strip. Each selection has a 40 ms budget, so baseline results may vary.
2. `shelves` builds a fresh plan using several items per row across defect-free bands. It beat the strip constructor on 28 instances.
3. `repair` keeps the prefix of the best plan and rebuilds its last four plates using more candidate widths. It improved the incumbent on 16 instances.

Set the order with `--stages strips shelves repair` and the shared time budget with `--seconds 170`. On a pinned Intel core, median solve time was 7.77 s and the maximum was 23.46 s, including input and output and excluding interpreter startup and checking. We used the same final waste for both contest limits and ranked it against each team's weighted waste (10% at three minutes and 90% at one hour). The top ten earn points on each instance. [Competition rules](https://roadef.org/challenge/2018/files/Challenge_Rules.pdf).

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
