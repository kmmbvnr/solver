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

## Round 2

ShiftOpt placed **4th of 5** when added to the historical results for all 18 hidden instances and their ten published seeds. Run the demo with `--seed SEED --workers 1 --seconds 269` for each trial. The organizers’ x86-64 Mac benchmark reported 269 seconds on this machine under Rosetta while other jobs were active. Independent trials ran concurrently, so timings are approximate.

KHE reloaded and scored 79 feasible schedules across 10 instances. In 96 trials the solver returned no schedule with zero hard cost. In five more, KHE aborted during construction on Kottenpark2008. All 101 missing results received the worst rank for their trial. The reconstruction preserves the organizers’ exclusions and tie handling. The resulting mean ranks were GOAL 1.221, HySST 2.419, Lectio 2.475, ShiftOpt 3.961 and HFT 4.139. [Round 2 scores and seeds](https://www.utwente.nl/en/eemcs/dmmp/hstt/itc2011/results/round2/itc2011_ranking_round2.htm) · [Calibration procedure](https://www.utwente.nl/en/eemcs/dmmp/hstt/itc2011/benchmarking/)
