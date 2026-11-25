# DIMACS 2026–2027 · Minimum-cost flow

Read a DIMACS `.min` network. Each arc specifies its lower bound, upper bound and unit cost. Solve a sparse node-balance linear program with HiGHS. The output gives the cost and arc flows in input order.

The example sends nine units at cost 33. A 5,000-node path delivered seven units at cost 69,986, matching its unique feasible flow. [Source](https://coral.ise.lehigh.edu/flow-challenge-2-0/minimum-cost-flow-input-format/).

From the repository root, run `python demos/dimacs/run.py 2026` for the included example or append the path to an input file.
