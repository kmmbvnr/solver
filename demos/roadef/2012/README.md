# ROADEF/EURO 2012 · Machine reassignment

Run `python solve.py > assignment.out` for public `a1_1`. For another instance, pass its `model_*.txt` file with the corresponding `assignment_*.txt` alongside it. Forward and reverse searches move one process at a time and check capacity, transient usage, conflicts, spread and service dependencies.

Google's checker accepted a reduction from **49,528,750** to **44,306,804** on `a1_1`. To verify it, run `solution_checker model_a1_1.txt assignment_a1_1.txt assignment.out`. The final standings use different inputs. [Data and checker](https://roadef.org/challenge/2012/en/instances.php) · [Final results](https://roadef.org/challenge/2012/en/results.php).
