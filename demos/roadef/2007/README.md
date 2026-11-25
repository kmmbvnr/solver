# ROADEF 2007 · Technician and intervention scheduling

Run `python solve.py example /tmp/ft-plan`. The output directory receives `tech_teams` and `interv_dates`. The pipeline compares input order with priority and duration order, combining available technicians into a single qualified team each day. Every intervention is scheduled in-house.

The official checker accepted all **10** Set A schedules. On the bundled `data1`, ShiftOpt scored **7,500** against a published feasible score of **2,490**. Lower is better. [Instances and checker](https://roadef.org/challenge/2007/en/instances.php) · [Reference scores](https://roadef.org/challenge/2007/files/references.html).
