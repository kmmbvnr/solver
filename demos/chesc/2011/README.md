# CHeSC 2011

One policy selects HyFlex operators on all 30 competition instances, five each from MAX-SAT, bin packing, personnel scheduling, permutation flow shop, TSP and vehicle routing. Each operator proposes a complete solution. The pipeline keeps the lower objective. Crossover uses a freshly initialized second parent. The bandit rewards strict improvements. The fixed baseline cycles through the same seeded operator order.

## Run

Use a JDK and set `JAVA_HOME` if JPype cannot locate it. From the repository root:

```sh
python -m pip install -e '.[chesc]'
export HYFLEX_HOME="$HOME/.cache/shiftopt/hyflex"
mkdir -p "$HYFLEX_HOME"
curl -fL https://people.cs.nott.ac.uk/pszwj1/chesc2011/chesc-jars.zip -o "$HYFLEX_HOME/chesc-jars.zip"
unzip -o "$HYFLEX_HOME/chesc-jars.zip" -d "$HYFLEX_HOME"
python -m demos.chesc.2011.solve --steps 41 --seconds 10 --seed 1
python -m demos.chesc.2011.solve --steps 41 --seconds 10 --seed 1 --policy fixed
```

The corrected JARs contain the instances and operators. Archive SHA-256: `afaa3cd92dafa7c039ccd2d490203a12692c6dd0a792d10937ff7bf3655c8472`. Add `--domain sat --instance 3` for a single case. Output columns are domain, instance ID, initial cost and best cost. Steps include construction. A Java operator already running may finish after the wall-clock deadline.

## Results

On one seed at the limits above, both policies improved the initial plan on all 30 instances. The bandit beat the fixed order on 16, tied on 11 and lost on 3. On MAX-SAT instance 3, the initial cost was 337, the bandit reached 177 and fixed order reached 188. Overall winner AdapHH reported a median of 3 and a best of 1 on that instance across 31 competition runs. The short run has no official rank. The 2019 JARs also correct the historical personnel scheduling objective.

[Instances and competition runner](https://people.cs.nott.ac.uk/pszwj1/chesc2011/examples/CompetitionRunner.java) · [Corrected domain software](https://people.cs.nott.ac.uk/pszwj1/chesc2011/hyflex_download.html) · [Historical results](https://people.cs.nott.ac.uk/pszwj1/chesc2011/raw-results.html)
