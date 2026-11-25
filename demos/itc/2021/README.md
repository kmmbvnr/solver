# ITC 2021 — sports timetabling

The pipeline constructs a double round robin using the circle method or CP-SAT. CP-SAT enforces the tournament structure and home/away count limits (CA1). With a feasible starting schedule it can also reassign venues while keeping opponents fixed. The final steps reverse home and away for a pair of teams or exchange two entire rounds. The RobinX validator evaluates every proposal against the full instance. Only schedules with zero infeasibility enter the pipeline.

From the repository root, with a C++ compiler, make and Boost headers installed:

```sh
python -m pip install -e '.[itc]'
git clone https://github.com/Robin-X/RobinX /tmp/robinx
git -C /tmp/robinx checkout 878bf2db7b25b43cc3022bc08c00be938b997b6a
make -C /tmp/robinx
export ROBINX=/tmp/robinx/RobinX
python -m demos.itc.2021.solve demos/itc/2021/ITC2021_Test2.xml /tmp/test2.xml
"$ROBINX" -i demos/itc/2021/ITC2021_Test2.xml -s /tmp/test2.xml
```

On macOS, if the Boost headers are outside the compiler search path, pass `CFLAGS="-std=c++14 -I./source/include -I$(brew --prefix boost)/include"` to make. RobinX prints the feasibility and objective values and returns the objective as its process exit code.

| Instance | Run | RobinX result | Reference |
| --- | --- | --- | --- |
| Test2 | From scratch | 0 hard, 197 soft | Published optimum 176 |
| Early 9 | From David Van Bulck's public 67-cost seed | 0 hard, 67 soft. The search retained the seed cost. | Competition best 108, later public schedule 56 |

```sh
data=/tmp/robinx/Repository/ITC2021
python -m demos.itc.2021.solve "$data/Instances/ITC2021_Early_9.xml" /tmp/early9.xml --seed "$data/Solutions/Early9_67.xml" --seconds 60
```

[Competition instances and bounds](https://robinxval.ugent.be/ITC2021/instances.php) · [Published schedules and validator](https://github.com/Robin-X/RobinX/tree/878bf2db7b25b43cc3022bc08c00be938b997b6a/Repository/ITC2021)
