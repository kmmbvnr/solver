# ROADEF 2009 · Airline disruption recovery

The pipeline retains original aircraft assignments, cancels disrupted legs when permitted, and compares grounding an aircraft with resuming its rotation when it returns to a matching airport. The official feasibility and cost checkers evaluate each complete proposal. A run that finds no accepted plan exits with an error.

Extract the two Linux checkers from the organizers' archives and make them executable. Run from this directory on x86-64 Linux, using the paths to those binaries. An emulator may be supplied through `--runner`.

```sh
unzip -q A1_6088570.zip -d /tmp/amadeus-data
python solve.py /tmp/amadeus-data/A05_6088570 /tmp/amadeus-plan \
  --checker /path/to/solutionChecker-static.i686-64 \
  --cost-checker /path/to/costChecker-static.i686-64 --seconds 450
```

On public **A05**, all 11 official feasibility reports were empty and the official cost was **40,275,051**. The qualification standings aggregate scores across instances. [Instances](https://roadef.org/challenge/2009/en/instances.php) · [Checkers](https://roadef.org/challenge/2009/en/verif.php) · [Qualification standings](https://roadef.org/challenge/2009/en/resultat_qualif.php).
