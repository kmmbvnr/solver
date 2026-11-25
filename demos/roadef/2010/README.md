# ROADEF/EURO 2010 · Power generation and outage planning

Run `python solve.py > plan.txt` for the bundled public `data0`. The pipeline tries outage dates within their weekly windows and spacing limits. For each calendar it tests three refueling quantities, simulates fuel stocks and production profiles, and dispatches the remaining load to type-1 plants in marginal-cost order for every scenario.

The official checker accepted the complete plan built from scratch at **8,738,060,202,979.286**. The published starting plan costs **8,745,815,799,076.815** and the best qualification result was **8,730,985,367,093**. Lower is better. To verify, run `java -Xmx512m -jar checker.jar -d data0.txt -r plan.txt`.

The calendar constructor handles bounded CT13 outage windows and CT14 spacing. For instances with other outage constraints, pass a feasible plan for the same instance via `--seed`. The pipeline can then improve thermal dispatch while retaining its outages and fuel trajectories. [Inputs and checker](https://roadef.org/challenge/2010/en/instances.php) · [Starting plan and qualification results](https://roadef.org/challenge/2010/en/qualif.php).
