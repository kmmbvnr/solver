# ROADEF/EURO 2016 · Inventory Routing

The pipeline starts with calendar search and uses CP-SAT assignment if calendar search produces no plan. It then runs three improvement steps and retains the lowest cost per unit delivered. Bounded maximum flow allocates deliveries across trailer stops and customer inventories. A local search shifts routes and changes their last stops in the first four days, recomputing feasible quantities for each proposal. OR-Tools CP-SAT adjusts shift and stop times. The default path makes no HiGHS solve calls. Pass `--route-mip` to use the mixed-integer route pool instead of local search.

After installing `.[roadef]`, run the commands from this directory. The archives in `data/` contain all 20 instances from the B+X final. [Official instances and checker](https://roadef.org/challenge/2016/en/instances.php).

```sh
work=$(mktemp -d)
unzip -q data/B.zip -d "$work"
unzip -q data/X.zip -d "$work"
python solve.py "$work/Instances_B_V25-11042016/V2.24.xml" --output "$work/plan.xml"
```

Pass the input XML and `plan.xml` to the official checker as two arguments.

The official checker accepted all 20 default plans with HiGHS solve calls disabled. The B+X score was **8.8138 (4th of 10 if included)**. Lower is better. The original LP/MIP pipeline scored 8.7121, also fourth. Compared with that run, one instance improved, four tied and fifteen had higher costs per unit delivered. On the same twenty fixed schedules, the flow and LP quantity optima agreed within 0.00000001 kg. [Per-instance results](benchmark.csv) · [Final standings](https://roadef.org/challenge/2016/en/finalResults.php).

The default run took a median of 4.64 seconds and a maximum of 55.39 seconds on a Mac with two instances running concurrently. The original timings were measured on one Intel core.

With `--recombine-seconds 3`, the last stage builds a second calendar plan (seed 17, up to 8 seconds), pools complete routes from both plans and gives HiGHS 3 seconds to select compatible routes and rebalance deliveries. Both parents remain eligible.

On 12 final instances (13–19 and 24–28), the official checker accepted every pooled result. Pooling beat the better of two separately optimized parents on nine and tied on three within 1e-9. Each individual pool solve also received 3 seconds. On instance 25, the cost per unit fell from 0.018602 for the better separately optimized parent to 0.018232. The published rank above uses the default pipeline.

Pass `--sequence` to score the alternate calendar after quantity optimization and retiming. On instances 13–19 and 24–28, both comparisons started from the same saved default plan and used the same seed-17 donor. Treating the three moves as one proposal beat accepting each move separately on instances 14, 19 and 25 and tied on nine. The official checker accepted all 24 results. On instance 19 the ratio fell from 0.056852 to 0.055209.
