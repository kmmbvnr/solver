# MIP 2024 · Presolve and postsolve

Run `python demos/mip/2024/solve.py [instance.mps.gz]`. The steps substitute fixed columns into row bounds and the objective offset, then remove rows whose bounds hold over the variable domains. The score counts eliminated rows and columns. Both steps preserve the objective and the mapping to the original variables.

Use `--reduced reduced.mps.gz --mapping fixed.json` to write the reduced model and the values needed for postsolve. Given a MIPLIB .sol file or a JSON object mapping the remaining variable names to values, `python demos/mip/2024/solve.py --postsolve fixed.json reduced-solution.json` restores the original assignment.

On the public **30n20b8** model, rows fell from **576 to 493**, columns from **18,380 to 11,098**, and nonzeros from **109,706 to 63,123**. A separate HiGHS run found a reduced solution; after postsolve the MIPLIB checker accepted it on the original instance at cost **302**. [Competition and test list](https://github.com/dominiqs81/MIPcc24).
