# ROADEF 2001 · Frequency assignment with polarization

Install `.[roadef]` from the repository root. From this directory, run `python solve.py --seconds 20 > fapp01_0200.out`. The first CP-SAT step satisfies the mandatory constraints. Later steps tighten the interference level and use the incumbent as a hint. The pipeline compares relaxation level, violations at the preceding level and violations at earlier levels, in that order.

On the public `fapp01_0200`, the official evaluator reported **(4, 22, 294)** with **zero mandatory violations** in a 20-second run. Time-limited CP-SAT results can vary. To reproduce the check, place the compiled evaluator alongside the input and output and run `./fappeval fapp01_0200`. [Data and evaluator](https://roadef.org/challenge/2001/en/sujet.php) · [Competition results](https://roadef.org/challenge/2001/en/resultats_phase2.php).
