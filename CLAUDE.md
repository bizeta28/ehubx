# CLAUDE.md — semester project (branch `semester-project`)

Fork of ehubX (Empa UESL; Pyomo + Gurobi), used for Bea Zanini's 12 ECTS ETH semester project
at Empa UESL: **flexibility of decentralised (edge) data centres in buildings** — seasonal
mismatch between DC waste heat and building heat demand, and how workload type changes the
value of IT flexibility. Supervisors: Gabriele Humbert, Jenny Hansson (Empa). ETH: Prof. Anthony Patt.

## Division of labour
- **Design happens in the claude.ai Project, implementation happens here.** Model formulations
  (sets, parameters, variables, constraints, objective) are agreed and approved by Bea there.
- The approved formulation for each change is written to `docs/semester_project/formulation/`
  as a Markdown + LaTeX file. **That file is the spec. Implement exactly it.**
- If the spec is ambiguous, wrong, or doesn't fit the ehubX structure: stop and say so.
  Don't silently change the formulation in code. Propose the change; Bea updates the spec.
- No spec file for a modelling change → don't implement it. Ask for one.

## Coding rules
- Prefer extending existing ehubX submodels (e.g. `load_shifting`) over writing new ones.
  Check `src/` for an existing mechanism before adding one.
- Explain each implementation block by block: what it does and which spec equation it maps to.
  Bea runs and reads everything; she must be able to defend every line.
- Units explicit everywhere (kW, kWh, CHF, °C). Hourly resolution, full year (8760 h) unless stated.
- Small, focused commits on `semester-project`. Commit message says which spec file it implements.
- Run the relevant tests / the case script before declaring something done; report what you ran.

## Data — this repo is PUBLIC
- Gabriele Humbert confirmed (8 Oct 2026) that a public repo is fine and the supervisor-provided
  case data (e.g. `examples/1_WH/inputs/`) is not sensitive, so those inputs are committed.
- Anything **new** (raw NEST measurements, other Empa data, Polybox material): ask Bea before
  committing. Don't commit generated results.
- Don't commit notes about the supervisors' unpublished preprint or internal reports.

## Case layout
- `examples/1_WH/` — baseline case (1 office building + 20 kW edge DC, waste-heat recovery),
  run via `main_small_demo.py`; inputs incl. 8760 h profiles in `inputs/basic/profiles/`.
- Post-processing scripts in `plots and print/`: only the 1_WH case matters; disregard
  scripts/logic for other cases (per Gabriele).

## Handoff back
- At the end of a session, append a short entry to `docs/semester_project/CHANGES.md`:
  date · spec implemented · what changed · what was tested · open issues.
  Bea carries this back to the design side.
