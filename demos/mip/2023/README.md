# MIP 2023 · Reoptimization

Run `python demos/mip/2023/solve.py [first.mps.gz second.mps.gz ...] --seconds 35`. Supply models in chronological order. Each model gets its own budget. The first pipeline step clips the preceding solution to the new bounds and attempts an LP repair with fixed integer values. The second gives the best available start to HiGHS. Output includes the primal objective and the solver's dual bound for each model.

The two bundled minimization models have optimal costs **4 → 6**. On the first two public models of bound-change series 3 (`bnd_s3_i01`, `bnd_s3_i02`), a 35-second run per model gave costs **549 → 409** and lower bounds **331 → 360**. The MIPLIB checker accepted both solutions. Bounds and incumbents can vary with runtime. [Competition and series](https://github.com/ambros-gleixner/MIPcc23).
