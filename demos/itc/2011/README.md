# ITC 2011 — high-school timetabling

ShiftOpt compares two CP-SAT constructions for lessons with fixed resources and several KHE constructions with different diversifier values. CP-SAT tries single and double lessons, avoids resource conflicts and tries at most one session of an event per day. KHE evaluates the full XHSTT constraints and discards every schedule with nonzero hard cost. KHE can also schedule resources on instances outside the fixed-resource model.

From the repository root, with a C compiler and Expat development headers installed:

```sh
python -m pip install -e '.[itc]'
git clone https://github.com/georgehgfonseca/itcgoal /tmp/itcgoal
git -C /tmp/itcgoal checkout 4f50f5a0dd10d4462c800d8c5b33aa5d9eed2225
export KHE_STEP=/tmp/shiftopt-khe
sh demos/itc/2011/build.sh /tmp/itcgoal "$KHE_STEP"
python -m demos.itc.2011.solve demos/itc/2011/BrazilInstance2.xml /tmp/brazil.xml
"$KHE_STEP" /tmp/brazil.xml /dev/null -1
```

On the hidden competition version of BrazilInstance2, the pipeline constructed a schedule from scratch. KHE reloaded the exported XML and confirmed **0 hard, 217 soft**. Lectio reached **0 hard, 5 soft** in round 3. On WesternGreeceUniversityInstance3 from the same archive, four KHE variants and the CP steps produced a checked cost of **0 hard, 19 soft**. All competition rounds use XHSTT. Results depend on the time budget and CP-SAT worker scheduling. [Input archive](https://www.utwente.nl/en/eemcs/dmmp/hstt/archives/XHSTT-ITC2011-hidden/) · [Round 3](https://www.utwente.nl/en/eemcs/dmmp/hstt/itc2011/results/round3/itc2011_ranking_round3.htm)
