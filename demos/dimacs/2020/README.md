# DIMACS 2020–2022 · Inventory routing

Read the DIMACS IRP `.dat` format. Try just-in-time replenishment, then a single-threaded HiGHS assignment model with integer deliveries, daily inventory limits, vehicle capacities and a ten-second solve limit. The model estimates travel using depot distances. Order each vehicle's assigned stops and compare full travel and holding costs. Each route lists customer ID and delivered quantity between implicit depot stops.

The linked feasibility checker accepted the routes and costs for `S_abs1n10_2_H3` (5,900.78) and `L_abs10n200_2_H` (117,581.08, 200 customers). These are local runs. The time-limited MIP may return different incumbents. [Source](https://dimacs.rutgers.edu/programs/implementation-challenges/vehicle-routing/implementation-challenge-vehicle-routing/inventory-routing).

From the repository root, run `python demos/dimacs/run.py 2020` for the included example or append the path to an input file.
