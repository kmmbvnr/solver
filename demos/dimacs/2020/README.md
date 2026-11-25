# DIMACS 2020–2022 · Inventory routing

Read the DIMACS IRP `.dat` format. Try just-in-time replenishment, then a single-threaded HiGHS assignment model with integer deliveries, daily inventory limits, vehicle capacities and a ten-second solve limit. The model estimates travel using depot distances. Order each vehicle's assigned stops and compare full travel and holding costs. Each route lists customer ID and delivered quantity between implicit depot stops.

The linked feasibility checker accepted the routes and costs for `S_abs1n10_2_H3` (5,900.78) and `L_abs10n200_2_H` (117,581.08, 200 customers). These are local runs. The time-limited MIP may return different incumbents. [Source](https://dimacs.rutgers.edu/programs/implementation-challenges/vehicle-routing/implementation-challenge-vehicle-routing/inventory-routing).

From the repository root, run `python demos/dimacs/2020/solve.py` for the included example or append the path to an input file.

## More tracks

From the repository root, run `python demos/dimacs/2020/cvrp/solve.py`. Each script accepts an input path and `--seconds`. [Edition and problem definitions](https://dimacs.rutgers.edu/programs/implementation-challenges/vehicle-routing).

| Track | Pipeline | Local result |
|---|---|---|
| [Capacitated vehicle routing](cvrp/solve.py) | Compare angular sweeps, then relocate customers. Reads single-depot CVRPLIB EUC_2D. | CMT1, rounded distance 602. |
| [Vehicle routing with time windows](time_windows/solve.py) | Compare earliest-due and farthest-first feasible insertions. Uses the Solomon format and truncates each distance to one decimal. | C101, distance 997.5. |
| [Split-delivery vehicle routing](split_delivery/solve.py) | Compare two capacity sweeps, then apply 2-opt within each route. | SD1, rounded distance 26,472. |
| [Electric vehicle routing with nonlinear charging](electric/solve.py) | Compare angular orders with partial charging; --chargers 0 allows unlimited simultaneous charges, 1 or 2 enforces station capacity. The constructor considers one intermediate station per leg. | tc2c10s2cf0, total durations 42.211355 (unlimited), 56.551118 (one), 43.735862 (two). |
| [CARP, node/edge/arc routing and time-dependent CARP](arc_routing/solve.py) | Compare demand packing, path scanning and route selection from randomized scans. TDCARP integrates directional speeds across time intervals. | egl-e1-A cost 5,012. BHW1 cost 483. C01-L duration 3,381.826667, nine vehicles serving all 79 required edges. |
| [Dynamic ride-hailing](ride_hailing/solve.py) | At each observed epoch compare greedy and maximum-weight dispatch. Estimate net fare from passenger and pickup distance. The simulator accumulates actual daily profit. | pyhailing 0.0.9, one stochastic day, 14 vehicles, 1,400 requests, seed 7, profit 12,481.48. |

The arc-routing demo also includes `mixed.txt` and `time_dependent.txt`. Electric and time-dependent routes were replayed against the original charging curves, station bookings and speed profiles.

The optional ride-hailing simulator uses an older NumPy. Install it in a separate Python 3.10 environment and pass the absolute path of the ShiftOpt interpreter to the simulation driver.

```sh
python -m pip install pyhailing==0.0.9 gym==0.17.3 "pandas<2" "matplotlib<3.8" "setuptools<81"
python demos/dimacs/2020/ride_hailing/simulate.py /path/to/shiftopt-environment/bin/python
```

The driver exchanges one observation and one action per decision. It uses the simulator's current mean pickup times and a 60-second maximum interval between decisions. The checked day is one seed of the small category. The competition evaluation uses 50 instances.
