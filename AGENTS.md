# AGENTS.md

- Use English for documentation, code comments, and user-facing messages.
- Keep shared algorithms and heuristics in `src/shiftopt/`.
- Route every benchmark solve through `shiftopt.run_pipeline`. Put construction, fallback and improvement inside named steps that propose complete plans.
- Keep each benchmark's code, inputs, run instructions, and brief results in `demos/<competition>/<year>/`.
- Add benchmarks where pipeline steps compare feasible plans or improve the incumbent.
- Keep drafts, interim reports, logs, and generated plans out of the repository.
