# CHeSC 2014 batch modes

This demo reproduces the single-solver and multiple-solver formats using the 30 public CHeSC 2011 competition instances. A study using the 2014 library reports that it became unavailable. The instance mix, runtime and scores here describe a local benchmark. A historical 2014 rank requires the original evaluation batch and scoring software. [Organizers' announcement](https://dmatheorynet.blogspot.com/2013/11/?m=0) · [Availability of the original library, section 2](https://d-nb.info/1186769327/34)

## Run

Follow the [2011 setup](../2011/README.md#run) to install the Python extra and set `HYFLEX_HOME` to the two corrected domain JARs. Run from the repository root:

```sh
python -m demos.chesc.2014.solve --workers 1 --seconds 300 --steps 16
python -m demos.chesc.2014.solve --workers 2 --seconds 300 --steps 16
```

One worker processes the whole batch in order. Multiple workers take instances round-robin, with one JVM per process. Each worker divides the remaining wall time among its remaining instances and carries unused time forward. Both modes share a single batch deadline. Java operators finish their current move before returning. A budget too small to construct a solution for every instance fails explicitly.

Each instance runs its own ShiftOpt pipeline. Earlier strict improvements influence which operator families the worker tries first on the next instance. The bandit then selects individual operators using that instance's search history.

## Results

With seed 1 and the commands above, both modes improved the initial solution on all 30 instances across six domains. One worker gave a lower cost on five instances, two workers on five, and 20 tied. For MAX-SAT instance 5 the initial cost was 456, one worker reached 378 and two workers reached 371. Output columns are domain, instance ID, initial cost and best cost.
