# ITC 2002 — university course timetabling

UniTime constructs a feasible assignment of events to rooms and periods. ShiftOpt then tries exchanges of whole periods. Each exchange preserves room suitability and all clashes. The search recomputes student penalties for long runs of lectures, late lectures and single lectures on a day.

## Setup for 2002 and 2007

From the repository root, install ShiftOpt and compile the pinned UniTime backend with a JDK (tested with Java 21). Its checkout includes the competition data and validator sources.

```sh
python -m pip install -e .
export ITC2007_HOME="$HOME/.cache/shiftopt/cpsolver-itc2007"
git clone https://github.com/tomas-muller/cpsolver-itc2007 "$ITC2007_HOME"
git -C "$ITC2007_HOME" checkout a253a5a45a5b148d5a8981c3fd0af5ecf9ae4b06
(cd "$ITC2007_HOME" && mkdir -p classes && find src -name '*.java' > sources.list && javac --release 8 -encoding ISO-8859-1 -cp 'lib/*' -d classes @sources.list && cp src/*.properties classes/)
python -m demos.itc.2002.solve demos/itc/2002/competition01.tim /tmp/competition01.sln --seconds 30
```

On `competition01` the archived validator confirmed a complete timetable for all 400 events with penalty **77**. Competition winner Philipp Kostuch scored **45** on this instance. Wall-clock search results can vary. [Data and validators](https://github.com/tomas-muller/cpsolver-itc2007) · [Historical results, Table 2](https://iridia.ulb.ac.be/~mbiro/paperi/ChiBirSocRos2006js.pdf)
