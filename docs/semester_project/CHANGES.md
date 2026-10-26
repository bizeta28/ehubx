# Implementation-side change log

## 2026-10-26 · no spec (Step 0, analysis only) · ERF scripts, Air→LT, TES dumping, HP capacity basis
- **Changed:** nothing in code, inputs or case scripts. All analysis ran on the 22 Oct `results/` of
  both reference cases, from scratch copies of the scripts with only the output folder redirected
  (`4_full` scripts also repointed from `results_flex/10_flex` to `results/`).
- **ERF: the gap is explained.** `5_ERF copy.py` gives real ERF **55.99 %** (1_WH) and 49.68 % (4_full).
  `5_ERF.py` gives 47.49 % / 47.24 %. Both are reproduced exactly by one re-implementation; each
  difference is switched on in turn below (1_WH; MT/HT = DC-attributed useful heat, MWh/a; El DC+CS = 115.83 MWh/a):

  | Step | Change vs. the row above | 1_WH ERF | MT / HT | 4_full ERF |
  |---|---|---|---|---|
  | A | `5_ERF.py` | 47.49 % | 40.15 / 14.86 | 47.24 % |
  | B | α_HT = 0 where HT_total < 0 (`5_ERF.py` divides by negative totals in 1,417 h) | 38.93 % | 40.15 / 4.94 | 47.24 % |
  | C | HE_LT dropped: the copy reads `V_ConvTechOut`/MT of HE_LT, which is always 0 (HE_LT takes MT as an **input**, 12.29 MWh/a) | 49.54 % | 52.44 / 4.94 | 49.68 % |
  | D | HP_WW weighted by the air share r instead of α_MT | 49.54 % | 52.44 / 4.94 | 49.68 % |
  | E | hourly MT, HT clipped at ≥ 0 (= `5_ERF copy.py`) | **55.99 %** | 52.44 / 12.41 | 49.68 % |

  So the 56 % comes from a script that (i) never subtracts the MT that HE_LT takes (+10.6 pp, a bug)
  and (ii) clips negative hourly HT, which hides most of the −11.25 MWh/a TESHT net loss (+6.5 pp).
  Neither script gives a clean definition. Input for the KPI spec (`formulation/kpis.md`).
- **Air → LT (HE_AW) is active and large.** 1_WH / 4_full:
  - HE_AW supplies 90.20 / 79.99 MWh/a of LT, i.e. 82.9 / 80.6 % of LT production. The Chiller supplies 18.66 / 19.20 MWh/a.
  - HE_AW sits at its 25 kW cap. It outputs LT in 8,289 / 8,254 h, and in 3,410 / 2,731 h it outputs more than the LT demand.
  - The Chiller is off in 6,495 / 6,497 h with LT demand > 0.
  - LT peak demand is 64 kW, the Chiller is 32 / 31 kW. In 841 / 858 h, Cap_chiller + TES_LT discharge < D_LT, so
    LT demand is only met because of HE_AW (max shortfall 25 kW = the HE_AW cap).
- **TES used as a heat sink.** Hours with inflow and outflow both > 0 in the same hour:
  - 1_WH TESHT (45.23 kWh): 1,980 h, 79.01 MWh/a moved simultaneously, 11.25 MWh/a net loss.
  - TESLT: 764 h / 9.30 MWh (1_WH), 535 h / 8.87 MWh (4_full).
  - BES (4_full): 8 h / 0.47 MWh.
- **HP capacity basis (needed for Step 1).** `conversion` techs cap the **main output** carrier
  (`conv_tech_model.py:479-493`). Without `main_out_ec`, the single output is the main one
  (`conv_tech_data.py:417`). So the HP_AW, HP_WW, Chiller and HE_AW capacities and `capex_per_cap` are per kW of
  heat output (kW_th), as for `type: heatpump` (`pow_cond ≤ Cap`). Confirmed in results: max output =
  capacity (HP_AW 44.85 kW_th vs max El 16.26 kW). The switch in Step 1 does not change the cost basis.
- **Repo state:** branch was already level with `origin/semester-project` at session start (Step 0a commits pushed).
- **Open issues:**
  1. ERF definition: which one is the reference, and is the paper's value kept as reported or recomputed
     (design side, `kpis.md`).
  2. Step 0 model/input fixes (`ls1` profile, simultaneous El import/export, ε shifting cost, BES C-rate)
     and Steps 1–4 still have no spec in `formulation/`. Nothing implemented.

## 2026-10-22 · no spec (Step 0a: repo hygiene + reference runs) · untrack generated files, rerun both cases
- **Changed:** untracked 39 generated CSVs in `examples/4_WH+PV+DHN+Flex/plots and print/csv_files/`
  and 7 `.DS_Store` files (`git rm --cached`; files stay on disk, both patterns were already in
  `.gitignore`). No code, input or script changes.
- **Ran:** `main_small_demo.py` in `1_WH` and `4_WH+PV+DHN+Flex`, unchanged (Gurobi 11, conda env
  `ehubx`). Both optimal, gap 0 %, ~73 min solve each. Real DoC / ERF from the cases' own
  `3_realDOC_Calculation2.py` and `5_ERF.py`, run from scratch copies with only the input/output
  paths changed to point at the fresh `results/`.

  | | 1_WH | 4_WH+PV+DHN+Flex |
  |---|---|---|
  | TAC [CHF/a] | 89,952.88 | 79,754.74 |
  | Capex (annualised) [kCHF/a] | 15.17 | 25.60 |
  | Opex (capacity) [kCHF/a] | 1.68 | 2.38 |
  | El import [kCHF/a] | 73.10 | 49.86 |
  | HT import [kCHF/a] | – | 1.91 |
  | HP_AW / HP_WW [kW] | 44.85 / 0.45 | 26.33 / 0 |
  | Chiller [kW] | 32.00 | 31.00 |
  | HE_AW / HE_WW / HE_LT [kW] | 25.00 / 16.30 / 7.62 | 25.00 / 34.67 / 2.17 |
  | CS_hybrid / DC [kW] | 25 / 20 | 25 / 20 |
  | TES HT / MT / LT [kWh] | 45.23 / 0 / 14.42 | 0 / 0 / 20.97 |
  | PV [m²] / BES [kWh] | – | 400 / 61.21 |
  | Real DoC combined (MT / HT) | 41.45 % (35.50 / 82.65) | 42.73 % (36.49 / 90.01) |
  | ERF real / ideal | 47.49 % / 92.00 % | 47.24 % / 92.00 % |

  Capex + opex + imports = TAC exactly (no export revenue in either case). Both TACs and all
  capacities equal the earlier runs (`results/` of 22 Oct, `results_flex/10_flex`).
- **Open issues:**
  1. Real ERF of `1_WH` (47.5 %) does not match the design-side reference value. Numerator split
     (MWh/a): MT from DC 40.13 (HP_AW 11.11 + HE_WW 41.00 − HE_LT 11.95 − HP_WW 0.02),
     HT from DC 14.86 (incl. −11.59 net TESHT balance); denominator DC 77.22 + CS 38.61 El.
     Dropping the HE_LT subtraction gives 57.8 %. Which ERF definition/script version produced
     the reference value needs to be checked on the design side.
  2. `4_full` real ERF varies with dispatch at identical TAC: 47.24 % (this run) vs 48.33 %
     (committed CSV, from `10_flex`). Same non-uniqueness as issue 5 of the previous entry.
  3. `1_WH`: TESHT has a net −11.6 MWh/a balance (losses) on a 45 kWh tank, with no HT export
     available. It looks like it is used partly as a heat sink. Relevant for Step 4.
  4. Post-processing scripts hard-code paths: `1_WH/.../3_realDOC_Calculation2.py` points to
     `2_WH+PV` (not in this repo); the `4_full` scripts read `results_flex/10_flex`, not `results/`.
  5. `main_small_demo.py` stops with `EOFError` in non-interactive runs when `results/` already
     exists (ehubX asks before overwriting). Workaround used: `yes y | python main_small_demo.py`.

## 2026-10-22 · no spec (analysis only) · trace of 4_WH+PV+DHN+Flex results
- **Changed:** nothing in code or inputs.
- **Done:** traced the 22 Oct run (`examples/4_WH+PV+DHN+Flex/results/`, ls3 = 10 % flex) through
  the energy balance. Checked per-carrier balance for all 8760 h and every conversion ratio
  against `techs.yaml`. Traced two hours in full: Mon 6 Jan 04:00 (t=125) and Fri 4 Jul 12:00 (t=4429).
- **Tested:** every balance closes (max residual 5e-12 kW). All conversion ratios match the
  inputs exactly. Cost 79,754.74 CHF, the same as `results_flex/10_flex`.
- **Open issues for the design side:**
  1. Zero-price hours (t=3157, t=4668): the solver imports and exports about 41 MW of El at the same time.
     This inflates Imp.El (296 → ~213 MWh real), Exp.El (86.6 → ~4 MWh) and CO2 (+~5.1 t,
     36.3 vs 31.2 t in 10_flex at an identical cost). The CO2 figure is not unique.
  2. Air import is free and unlimited. 72 of 109 MWh of Air is ambient, not DC exhaust, so DC exhaust
     air has no marginal value. HE_AW runs at its 25 kW cap in summer, and the Chiller only
     covers the remainder. Open question: what does LT physically represent? It peaks in summer and the Chiller feeds it.
  3. HP_AW uses a fixed 1:1 Air:El in_part with COP output. That breaks energy conservation
     (41.3 MWh in → 75.6 MWh out; physically Air should be (COP−1)·El). The `cop: 4.5` on HP_WW in
     hubs.yaml is ignored because the tech is `type: conversion`.
  4. HT export is free and unlimited (DHN as free sink). 31 % of DC heat (21.7 MWh) is dumped in Apr–Oct,
     while 10.1 MWh of HT is imported in Nov–Mar.
  5. Load shifting has zero cost, so solutions are non-unique (ehubX warns in the log).
     V_LoadShiftingCap and the peak variables have no meaning. There is no 0 % flex baseline run yet.
     The 5→30 % runs span 79,974 → 78,842 CHF.
  6. The IT profile is flat at 1.7 kW for most of May (29 Apr–12 May, 19–31 May). Possible data gap.
  7. BES has no C-rate limit, so it fills 61 kWh in one hour.
