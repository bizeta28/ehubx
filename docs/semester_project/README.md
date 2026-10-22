# Semester project — context for the implementation side

**Quantifying the flexibility potential of decentralised data centres in buildings.**
Bea Zanini, 12 ECTS semester project, MSc Energy Science and Technology, ETH Zürich.
Runs 14 weeks at 50 % from 1 Oct 2026, with the final presentation on 7 Jan 2027.
Hosted at Empa UESL: Gabriele Humbert and Jenny Hansson. ETH examiner: Prof. Anthony Patt.

## Research question (from the proposal)
How much seasonal heat-demand flexibility can coordinated data-centre waste-heat recovery unlock
across a multi-building portfolio, and how does it depend on the type of computational workload?
1. How do workload types differ in temporal profile, deferrability, and the amount and temperature of recoverable heat?
2. How much heat-demand flexibility does each workload type provide across seasons and demand profiles, and which provides the best fit?
3. How does the workload–demand match change the electrical load seen by the grid?

## Where things live
| What | Where | Who writes it |
|---|---|---|
| Design, reasoning, literature, decisions | claude.ai Project "SP: DC Flexibility (EMPA)": `project_log.md` is the source of truth | Bea + Claude (design side) |
| Approved specs | `docs/semester_project/formulation/` | design side, after Bea approves |
| Implementation log | `docs/semester_project/CHANGES.md` | Claude Code (implementation side) |
| Public references | `docs/semester_project/literature.md` | design side |
| Papers, internal reports, project log copy, full fix plan | `docs/semester_project/private/` (**local only, git-ignored, never commit**) | design side, synced by Bea |

The repo copies of design-side material are snapshots. If they conflict with the claude.ai
Project, the Project wins. Flag the conflict; don't resolve it yourself.

## Cases
- `examples/1_WH/`: WHR scenario of the baseline model (Hansson et al. preprint). It has no PV, BES, DHN or Flex.
- `examples/4_WH+PV+DHN+Flex/`: the full scenario. Same techs, parameters and profiles as `1_WH`,
  plus PV/BES, HT import (0.1887 CHF/kWh) and free HT export, a DC fixed at 20 kW, and
  `load_shifting` on `IT` (`ls3`: β = 0.1, `interval_length: 24 h`, zero shifting cost).
- Both are **reference cases**: keep them reproducible. Model changes go into new case folders or behind
  a switch. Never edit these two in place.

## Current status (22 Oct 2026)
- Phase: understanding and correcting the baseline model before extending it (workload-type flexibility).
- Planned order of model changes (each one gets a spec in `formulation/` before any code):
  0. Repo hygiene + reproduce the paper's numbers with both reference cases
  1. Heat-pump energy balance (`type: heatpump` instead of `conversion`)
  2. Separate DC exhaust air from ambient air (`AirDC` / `AirAmb`, separate COPs)
  3. Direction of the Air → LT path (DC air must not supply cooling)
  4. Cost or limit on HT export (explicit heat rejection)
  5. Workload-type, delay-only IT flexibility (extension of `load_shifting`)
  6. Air-path threshold sweep over DC size
- Details and rationale: `private/model_fix_plan.md`.

## Session start checklist (implementation side)
1. Read this file, the latest entries in `CHANGES.md`, and the spec you are asked to implement.
2. If the task touches the model physics, also read `private/model_fix_plan.md` and the relevant paper in `private/`.
3. Check the `git log` for changes since the last `CHANGES.md` entry.
