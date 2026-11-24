# ROADEF/EURO 2022 · Truck loading

The official checker accepted all 155 final C and X plans. Adding ShiftOpt to the published table gives **14th of 16 with 460 points**. S41 won with 2,115. ShiftOpt scored on 137 instances. Grouping compatible order lines alone did not change any instance cost. Trying the same groups in descending footprint area reduced cost on 131 instances and preserved the other 24 scores. Both strategies earned 460 points. Median solve time was 1.87 s and the maximum was 7.09 s on Intel, excluding checker time and Python startup. [Per-instance results](benchmark.csv) · [Official workbook](https://roadef.org/challenge/2022/en/results_final_phase.xlsx).

ShiftOpt assigns items to eligible departures, forms nested stacks and packs them along the trailer walls. It checks payload, stack density, geometry and axle loads when placing a stack. The pipeline compares packing by order line with consolidation of compatible order lines for each departure and dock group. Pass `--rows-only` to reproduce the first strategy alone.

Install from the repository root with `python -m pip install '.[roadef]'`. From this directory, solve final instance C/AS and run Renault's Java checker.

```sh
work=$(mktemp -d)
unzip -q data/AS.zip -d "$work"
python solve.py "$work/AS" "$work/AS"
base=https://raw.githubusercontent.com/renault-iaa/challenge-roadef-2022/e0cae1e8d2aebe476cca5a1d75179560aa10a852
curl -fsSL "$base/checker.zip" -o "$work/checker.zip"
(cd "$work" && unzip -q checker.zip && sed 's@data/SDV/@AS/@g' checker/instances.csv > instances.csv && java -Xmx2g -Dlogback.configurationFile=checker/logback.xml -jar checker/CheckerChallenge-1.11.4.jar instances.csv)
cat "$work/AS/report.csv"
```

The full final uses 155 instances from `dataset_C_{1,2,3}.zip` and `dataset_X_{1,2,3,4,5}.zip` at the same pinned source. The scientific prize for this edition was awarded in 2024. [Official data](https://roadef.org/challenge/2022/en/instances.php) · [Final standings](https://roadef.org/challenge/2022/en/finalresult.php) · [Schedule](https://roadef.org/challenge/2022/en/calendrier.php).

Pass `--beam-width 1` or `--beam-width 2` to explore adjacent swaps in stack order. On C1/AS, BY and CA, the official checker reported the following costs. The full standings above use the default width of zero.

| C1 instance | Default | Width 1 | Width 2 |
|---|---:|---:|---:|
| AS | 3,775,800 | 3,774,000 | 3,772,200 |
| BY | 22,753,200 | 22,510,200 | 22,423,800 |
| CA | 2,565,300 | 2,552,700 | 2,552,700 |
