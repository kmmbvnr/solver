# ITC 2019 — university timetabling and student sectioning

The first pipeline step calls Edon Gashi's competition solver to assign times, rooms and students. The next two steps exchange equivalent room labels and swap two students' complete section assignments for one course. These swaps preserve section sizes and parent-child enrolments. ShiftOpt retains the smallest weighted penalty.

From the repository root, with the .NET 8 SDK on the path:

```sh
python -m pip install -e .
git clone https://github.com/edongashi/itc-2019 /tmp/itc2019-gashi
git -C /tmp/itc2019-gashi checkout b7b7110d1968758b0b7efe099e7f68aa7f19a4a0
dotnet build /tmp/itc2019-gashi/src/Timetabling.Common -c Release
export ITC2019_LIB=/tmp/itc2019-gashi/src/Timetabling.Common/bin/Release/netstandard2.0
python -m demos.itc.2019.solve demos/itc/2019/wbg-fal10.xml /tmp/wbg.xml --seconds 60
```

On the public test instance `wbg-fal10`, the pipeline scheduled **150 classes at cost 116** from scratch. On the scored middle instance `lums-spr18`, it scheduled **487 classes at cost 193** with the published room/time warm start below. The winning competition cost was **95**. Both exported XML schedules were independently checked against their input constraints and weighted objective. These are single time-limited runs.

```sh
base=https://raw.githubusercontent.com/ADDALemos/MPPTimetables/c33d15797686a27c192eabb90948baa54d3ddef5/data
curl -fL "$base/input/ITC-2019/lums-spr18.xml" -o /tmp/lums.xml
curl -fL "$base/output/ITC-2019/solution-lums-spr18.xml" -o /tmp/lums-start.xml
python -m demos.itc.2019.solve /tmp/lums.xml /tmp/lums-out.xml --warm-start /tmp/lums-start.xml --seconds 75
```

[Input and warm-start archive](https://github.com/ADDALemos/MPPTimetables) · [Competition results](https://www.itc2019.org/results) · [Solution format](https://www.itc2019.org/format)

With a local 60-second budget per instance and no warm starts, ShiftOpt solved **1 of 30** scored instances. On `lums-spr18` its 487-class schedule passed a separate constraint and objective check at cost **415**. That would place fifth on this middle instance, between 178 and 820, for four points and **6th of 6 overall** alongside the five historical teams. The competition imposed no per-instance time limit. [Final score tables, slides 18, 26 and 33](https://www.itc2019.org/papers/itc2019-awards-slides.pdf)
