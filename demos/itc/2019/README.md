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
