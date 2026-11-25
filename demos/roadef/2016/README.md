# ROADEF/EURO 2016 · Inventory Routing

A calendar search builds the initial plan. ShiftOpt runs three improvement steps and retains the lowest cost per unit delivered. Bounded maximum flow allocates deliveries across trailer stops and customer inventories. A local search shifts routes and changes their last stops in the first four days, recomputing feasible quantities for each proposal. OR-Tools CP-SAT adjusts shift and stop times. The default path makes no HiGHS solve calls. Pass `--route-mip` to use the mixed-integer route pool instead of local search.

After installing `.[roadef]`, run the commands from this directory. The archives in `data/` contain all 20 instances from the B+X final. [Official instances and checker](https://roadef.org/challenge/2016/en/instances.php).

```sh
work=$(mktemp -d)
unzip -q data/B.zip -d "$work"
unzip -q data/X.zip -d "$work"
python solve.py "$work/Instances_B_V25-11042016/V2.24.xml" --output "$work/plan.xml"
```

Pass the input XML and `plan.xml` to the official checker as two arguments.

The checker accepted all 20 plans in the original benchmark. On one Intel core, median wall time was 22.3 seconds and the maximum was 83.3 seconds. [Per-instance results](benchmark.csv).

The B+X score was **8.7121** versus **0.00** for the winner, S17 (Ahmed Kheiri). On B24, the logistic ratio was 0.018332 versus 0.011219. Lower scores and ratios are better. The official limit was 30 minutes of CPU time per instance. [Final standings](https://roadef.org/challenge/2016/en/finalResults.php).
