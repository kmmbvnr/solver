# ROADEF 2003 · Earth observation scheduling

Run `python solve.py > solution` for the bundled public instance `2_9_36`. Pass another native instance as a positional argument. Two construction orders schedule single observations within their time windows. A common upper bound on setup time preserves feasibility between observations. Paired stereo requests stay unscheduled.

The official Java checker accepted all **10** plans on the original public set. On `2_9_36` the gain was **10,423,440**, matching the archived plan. On the larger `2_15_170`, ShiftOpt scored **80,488,672** against the archived **524,896,372**. Higher is better. [Instances, checker and reference plans](https://roadef.org/challenge/2003/en/sujet.php).
