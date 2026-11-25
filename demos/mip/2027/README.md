# MIP 2027 · Small infeasible subsystems

Run `python demos/mip/2027/solve.py [instance.mps.gz] [solution.json] --seconds 20`. The pipeline first proves infeasibility with HiGHS. It then tries removing groups and individual elements, retaining each smaller subsystem only after HiGHS proves it infeasible. The remaining time is used to find witnesses showing that removing an individual kept element makes the subsystem feasible. Integer variables retained in the subsystem keep their original bounds under the contest rules.

The official checker proved inclusion-minimality on the bundled integer example and on **stein15inf** from the organizers' sample set. On the latter, it accepted **36 rows and 6 integrality conditions**, with valid certificates for all 42. Inclusion-minimality means each retained element matters; a different subsystem could be smaller.

To check a saved solution, run `mipcc-iis-checker --solver highs --instance instance.mps.gz --solution solution.json`. This is a sample-set result for the announced 2027 competition. [Rules](https://www.mixedinteger.org/2027/competition/) · [Official checker and sample instances](https://github.com/mixedinteger/MIPcc27).
