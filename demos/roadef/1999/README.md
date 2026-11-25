# ROADEF 1999 · Equipment inventory

Run `python solve.py > plan.rsl` for the bundled `I808nb`, or pass another native `.tes` file. Two allocation orders compete with chronological scheduling of purchases and workshop maintenance. Unfilled demand goes to an external supplier.

All 16 published inputs passed independent checks for demand, substitutions, purchase limits, equipment availability, wear, workshop capacity and cost. On `I808nb`, ShiftOpt costs **1,238,300** against the published reference of **1,288,400**. On the purchase variant `I808b`, the costs are **1,236,648** and **1,223,782**. The worked example in `example` reaches its published optimum of **3,820**. [Instances](https://roadef.org/challenge/1999/docs/tes/) · [Reference plans](https://roadef.org/challenge/1999/docs/rsl/) · [Scoring and reference costs](https://roadef.org/challenge/1999/docs/imp.html).
