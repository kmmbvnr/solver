# ROADEF/EURO 2018 · Glass Cutting

The official checker accepted all 30 final instances (15 B and 15 X). ShiftOpt scored **0 points**, tying S4, S22 and S27 behind the 16 teams with points. With ShiftOpt added, the organizers' workbook labels this four-way tie **20th of 20**. J28 won with 286 points. Our best individual results were 13th on B2 and B8. [Per-instance results](benchmark.csv) · [Official results and workbook](https://roadef.org/challenge/2018/en/finalResults.php).

The adapter calls the existing `shiftopt.select_candidates` with its default strategy and a 40 ms budget per call. It tries up to four strip widths at each position. Within the largest defect-free horizontal band, each candidate is an ordered prefix of one stack. The solver maximizes item area subject to the height limit and one prefix per stack. This baseline uses only part of the permitted cutting patterns.

On one pinned Intel CPU per process, median wall time was 9.10 s and the maximum was 23.46 s, including interpreter startup. Every run finished within three minutes. We used its final waste for both official time limits. The instance rank compares that value to each team's weighted waste (10% at three minutes and 90% at one hour). Only the first ten places on an instance earn points. [Competition rules](https://roadef.org/challenge/2018/files/Challenge_Rules.pdf).

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
