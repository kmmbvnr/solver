# ITC 2002 — university course timetabling

The Python pipeline inserts events, reinserts displaced events, exchanges whole periods and anneals feasible moves. Its objective counts late lectures, single lectures on a day and runs of consecutive lectures.

```sh
python -m pip install -e .
python -m demos.itc.2002.solve demos/itc/2002/competition01.tim /tmp/competition01.sln --seconds 60
```

On competition01 the archived validator confirmed a feasible timetable at penalty **261**, with seed 1 and a 60-second limit. The previous UniTime pipeline scored 77 and the competition winner scored 45.

With seed 1, setting `--seconds 300` still returned 261 in 2.9 seconds. The default annealing step stops after 50,000 attempts. In a separate timed run, the pipeline repeated that step from the best timetable with successive seeds. Including construction, the penalty reached 217 at 60 seconds and 216 at 300 seconds. Both schedules passed the validator.

## Previous UniTime pipeline

On `competition01` the archived validator confirmed a complete timetable for all 400 events with penalty **77**. Competition winner Philipp Kostuch scored **45** on this instance. Wall-clock search results can vary. [Data and validators](https://github.com/tomas-muller/cpsolver-itc2007) · [Historical results, Table 2](https://iridia.ulb.ac.be/~mbiro/paperi/ChiBirSocRos2006js.pdf)

On all 20 competition instances, one run per instance with a local 60-second budget produced 20 validator-confirmed feasible schedules. The total penalty was **1,645**. ShiftOpt beat Kostuch on one instance (75 versus 78 on competition13) and scored higher penalties on the other 19. The historical entries could select their best run.

Inserting this run into the [archived results table](https://web.archive.org/web/2010id_/http://www.idsia.ch/Files/ttcomp2002/results.htm) gives **4th of 12** on the 20 public instances. This uses the sum of per-instance min–max normalized penalties, includes all 11 eligible entries and excludes the two organizing teams. Using either the claimed or organizer-verified scores where both are available gives the same place. The local time limit differs from the historical hardware calibration.
