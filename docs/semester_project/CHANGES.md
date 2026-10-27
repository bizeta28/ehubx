# Implementation-side change log

## 2026-10-27 · `formulation/01_heatpump_balance.md` + `03_air_lt_direction.md` · Steps 1, 3 and 1+3
- **Changed:** both specs committed with status "approved by Bea, 26 Oct 2026". Six new case folders,
  copied from the references (`inputs/` + `main_small_demo.py` only). `1_WH` and `4_WH+PV+DHN+Flex` are untouched:
  `1_WH_fix1`, `1_WH_fix3`, `1_WH_fix1+3`, `4_WH+PV+DHN+Flex_fix1`, `…_fix3`, `…_fix1+3`.
  - Step 1 (`techs.yaml`): HP_AW and HP_WW become `type: heatpump` with `heatpump_params.ecs`
    (`elec: El`, `heat_in: Air` / `MT`, `heat_out: MT` / `HT`, `cool_in` = `cool_out` = `HPdummy`).
    `ecs.yaml`: new carrier `HPdummy`, which has no demand, import or export. `hubs.yaml`: `profile_path: profiles/HPCOPprofile.csv`
    for both. Costs unchanged.
  - Step 3 (`techs.yaml`): HE_AW `in_ecs: [Air 1 kWh, LT 1 kWh]`, `main_in_ec: Air`, `out_ecs: [AirOut 1 kWh/kWh]`.
  - `erf_kpi.py`: A_HP, P_HPAW and P_HPWW are read as `V_ConvTechIn` *or* `V_HpTechIn`, and the script prints which one it used.
    Output on both references is unchanged (re-run, identical to the 26 Oct entry).
  - New `plots and print/fix_checks.py` (read-only): spec section 5 checks of both specs plus TAC and capacities.
- **Pre-checks (spec 01 §3):**
  1. Parser keys are as listed in the spec. `ecs` (`elec`, `heat_in`, `heat_out`, `cool_in`, `cool_out`) and `cop_factor` go
     in `techs.yaml`. `cop`, `availability`, `profile_path`, `temp_heat_in/out` go in `hubs.yaml`.
  2. The cap constraint (`hp_tech_model.py:327-332`) is `V_HpTechOut[heat_out] + V_HpTechIn[cool_in] ≤ a·Cap`, so it counts
     the cooling condenser term. With one dummy carrier, the equality balance gives Σ El_cool = 0, and
     `C_HpTechCopCo` then forces every cooling flow to 0.
  3. Cost basis: see the HP_AW capacity check below.
- **Deviation from spec 01 wording, data format only:** the spec says the heat pumps "keep `profiles/HPCOPprofile.csv`".
  The heatpump parser needs the header rows `stage_id / hub_id / tech_id / profile_key` (+ `unit`). The
  conversion file has `stage_id / tech_id / ec_id`. In the fix1 folders the file keeps its name and its 8760 values
  (verified identical) with the header rewritten. HP_WW's `cop: 4.5` in `hubs.yaml` is still there but is overridden in
  all 8760 h (`TimeSeries.get_value` prefers hourly values). Check S1.1 confirms Q^c = COP_profile(t)·P to 1e-14 kW.
- **HP_AW capacity check (reference results, before any change):**

  | | 1_WH | 4_full |
  |---|---|---|
  | Cap HP_AW [kW] | 44.854 | 26.335 |
  | max_t Q^c [kW_th] (hour, COP there) | 44.854 (t = 126, COP 3.02) | 26.335 (t = 31, COP 3.08) |
  | hours with Q^c = Cap | 66 | 1,240 |
  | max_t El [kW] | 16.26 | 10.03 |
  | annualised CAPEX / Cap [CHF/(kW_th·a)] | 160.92 | 160.92 |

  160.92 = 1370 CHF/kW × annuity(10 %, 20 a). The cap binds on heat output, never on El, so the basis is kW_th, the same as
  `pow_cond ≤ Cap` under `type: heatpump`. HP_WW (1_WH): 0.446 kW = max Q^c, also 160.92 CHF/(kW_th·a).
  *Reference temperature:* the model has no rating point. Cap is the same kW_th limit in every hour, whatever the COP,
  and the max output falls in cold hours (COP ≈ 3.0). The profile (min 2.63, mean 4.45, max 6.00) has no temperatures in the
  repo, so I cannot tell which source/sink temperatures it assumes.
- **Ran:** all six cases, Gurobi 11, gap 0 %. Solve time 14–21 min, except the two fix1 runs. These show 18.3 h of
  wall time, but their root LP took only 192–212 work units (the other runs took 194 work units in 155 s). Both stalled over the same night,
  so the machine slowed down, not the model.

  | | TAC [CHF/a] | Chiller [kW] | HP_AW [kW_th] | HP_WW | HE_AW | TES HT / MT / LT [kWh] | DoC | DoC_E | ERF |
  |---|---|---|---|---|---|---|---|---|---|
  | **1_WH** ref | 89,952.88 | 32.00 | 44.85 | 0.45 | 25.00 | 45.23 / 0 / 14.42 | 52.32 % | 40.46 % | 39.38 % |
  | + step 1 | 89,962.13 | 32.14 | 45.01 | 0.44 | 25.00 | 45.28 / 0 / 13.54 | 54.20 % | 42.97 % | 42.10 % |
  | + step 3 | 99,694.94 | 64.47 | 41.24 | 0.53 | 8.97 | 16.16 / 53.21 / 0 | 62.01 % | 44.41 % | 44.33 % |
  | + steps 1+3 | 99,039.20 | 57.36 | 41.43 | 0.47 | 8.69 | 20.00 / 49.49 / 12.83 | 64.55 % | 47.01 % | 49.09 % |
  | **4_full** ref | 79,754.74 | 31.00 | 26.33 | 0 | 25.00 | 0 / 0 / 20.97 | 61.19 % | 43.53 % | 39.70 % |
  | + step 1 | 79,729.44 | 31.35 | 26.33 | 0 | 25.00 | 0 / 0 / 18.66 | 63.74 % | 46.63 % | 42.44 % |
  | + step 3 | 89,080.55 | 59.57 | 26.33 | 0 | 9.03 | 0 / 0 / 36.39 | 63.09 % | 46.15 % | 36.34 % |
  | + steps 1+3 | 88,646.61 | 57.00 | 25.87 | 0 | 5.93 | 0 / 27.17 / 14.42 | 63.40 % | 47.64 % | 40.66 % |

  HE_AW capacity is in kW of LT output for ref/step 1, and kW of air (= AirOut) for steps 3 and 1+3.
- **Checks spec 01 §5 (fix1 and fix1+3, both cases): all PASS.**
  1. max|Q^e + P − Q^c| ≤ 7.1e-15 kW (HP_AW), ≤ 5.6e-17 kW (HP_WW).
  2. max Q^c = Cap to 1e-4 kW (HP_AW 45.009 / 26.335 / 41.429 / 25.874 kW).
  3. `V_HpTechElecCo` and both `HPdummy` flows are exactly 0 in all hours.
  Air drawn by HP_AW: 23.45 → 61.31 MWh/a (1_WH) and 20.65 → 54.96 MWh/a (4_full), each equal to Σ(COP−1)·P.
  HP El and heat output barely move: 1_WH Q^c 84.91 → 84.71 MWh/a.
- **Checks spec 03 §5 (fix3 and fix1+3, both cases): all PASS.**
  1. The Chiller is the only LT producer, and HE_AW has no LT output column. LT balance residual ≤ 5.3e-8 kW.
  2. max|Q_HE_AW,LT − Q_AW| = 0 kW.
  3. Chiller Cap vs peak of (D_LT + TESLT charge − discharge): 64.47 ≥ 64.00 (1_WH fix3), 57.36 ≥ 57.36 (1_WH 1+3),
     59.57 ≥ 59.01 (4_full fix3), 57.00 ≥ 57.00 (4_full 1+3). With HE_AW and HE_LT loads included, the net peak equals
     Cap in all four (the chiller covers the whole LT load).
  4. HE_AW LT, now a load (was 90.20 / 79.99 MWh/a as a producer): 23.97 / 16.83 MWh/a (1_WH fix3 / 1+3) and
     23.33 / 14.72 MWh/a (4_full). Chiller LT: 18.66 → 120.29 / 114.19 MWh/a (1_WH), 19.20 → 120.14 / 109.98 MWh/a (4_full).
     Chiller El: 5.61 → 28.87 / 27.38 (1_WH), 5.73 → 28.09 / 26.50 MWh/a (4_full).
  5. The three cases per reference are run and the KPI rows are filled (table above). `erf_kpi.py` checks 1, 2, 3 and 5 PASS in all six.
  - Feasibility: peak Q^CS_Air = 9.60 kW against an installed HE_AW of 5.9–9.0 kW. All runs are feasible: HP_AW absorbs the rest,
    since Air has no other sink. HE_AW cost basis: 145 CHF/kW was per kW of LT (= 0.9 kW of air) and is now per kW of air, so
    it is ~10 % cheaper per kW of air handled. HE_AW annualised cost is ≈ 18 CHF/(kW·a) × 6–9 kW, so the shift is ≈ 15 CHF/a.
- **Open issues (design side):**
  1. `kpis.md` §1: the variable for A_HP, P_HPAW and P_HPWW is `V_HpTechIn` once Step 1 is in (the table says `V_ConvTechIn`).
     The script handles both; the spec table needs the update.
  2. With Step 3, DC air that HP_AW does not use costs chiller El to reject (HE_AW + chiller). This makes HP_AW the
     cheaper air sink even when MT is not needed. Same question as the open point in spec 03 §6 (free Air → AirOut
     sensitivity, possible double count of cooling El).
  3. 1_WH + step 3 builds a 53 kWh TESMT (0 before) and cuts HE_LT dumping (R_MT 12.29 → 2.00 MWh/a). This is the main reason
     its ERF rises, although the chiller El rises too.
  4. HP_WW's `cop: 4.5` in `hubs.yaml` is overridden by the profile. Delete the line or keep it, whichever the design side prefers.
     The HPCOPprofile temperatures are unknown (see above).
  5. Nothing pushed. Branch is 9 commits ahead of `origin/semester-project` (incl. `41401ba`, `c5cf8d9` of 26 Oct).

## 2026-10-26 · `formulation/kpis.md` (sections 2–3) · KPI script erf_kpi.py
- **Changed:** added the spec `formulation/kpis.md` (as provided) and
  `examples/4_WH+PV+DHN+Flex/plots and print/erf_kpi.py`. It is one script for the whole 1_WH family:
  the case folder is an argument, and it writes nothing to disk. It computes ERF, DoC and DoC_E, skips REF,
  and prints the term breakdown (check 4) and PASS/FAIL for checks 1, 2, 3 and 5. No model code, inputs or
  existing scripts were touched (`5_ERF.py` and `5_ERF copy.py` are unchanged).
- **Data source:** flows come from the dense `tech-TS.csv`, `import_export-TS.csv` and `loads-TS.csv`
  (zeros included), so a missing variable can be told apart from an all-zero one. `opt_vars.csv` is sparse
  and is used only as a cross-check (equal annual sums). Every flow name in spec section 1 exists
  under that name in both cases. I_HT and X_HT are absent in 1_WH and set to 0, as the spec says.
- **Storage index:** ehubX `V_StorTechEnergy[t]` is the level at the *start* of hour t. The spec's E(t) is
  read as the level at the *end* of hour t: E(0) = `V_StorTechEnergy[1]`, E(T) = `V_StorTechEnergyFinal`
  (`tech.csv`). With this reading, L_TES ≥ 0 in every hour of both cases.
- **Ran** on the 22 Oct reference runs (MWh/a):

  | | 1_WH | 4_full |
  |---|---|---|
  | Q_CS_HT | 69.50 | 69.50 |
  | − L_TES | −11.25 | 0.00 |
  | − R_MT | −12.29 | −2.83 |
  | − φ_HT·X_HT (X_HT / I_HT) | 0.00 (– / –) | −21.32 (21.32 / 10.11) |
  | = Q_DC→HT | 45.96 | 45.35 |
  | + φ_Air·A_HP (A_HP) | 11.12 (23.45) | 11.10 (20.65) |
  | = Q_reuse | 57.08 | 56.45 |
  | P_DC / P_CS / P_HPAW / P_HPWW / P_Ch | 77.22 / 38.61 / 23.45 / 0.05 / 5.61 | 77.22 / 38.61 / 20.65 / 0.00 / 5.73 |
  | = P_el,total | 144.95 | 142.21 |
  | **ERF** | **39.38 %** | **39.70 %** |
  | **DoC** (hourly) | **52.32 %** | **61.19 %** |
  | **DoC_E** | **40.46 %** | **43.53 %** |

  Checks: 1 PASS (57.08 / 56.45 ≤ 106.57), 2 PASS (≤ 128.92), 3 PASS (E(0) = E(T) = 0 kWh) in both.
  Check 5 PASS in 4_full (0 h), N/A in 1_WH. The cross-check against `opt_vars.csv` passes. A copy of the 1_WH results
  with HE_LT renamed stops with `R_MT: V_ConvTechIn (carrier MT, tech HE_LT) not found`.
- **Open issues (design side):**
  1. DoC: 721 h/a have D_HT + D_MT = 0. The spec says "1/|T|" (|T| = 8760, section 0) and "hours with D = 0
     excluded". Implemented literally: excluded from the sum, divided by 8760. Dividing by the 8,039 h with
     demand instead gives 57.01 % (1_WH) and 66.68 % (4_full). Which one is meant?
  2. Q_reuse(t) < 0 in 613 h (1_WH) and 34 h (4_full). This is allowed by the spec (no clipping in ERF, DoC clips at 0),
     reported for information.
  3. Spec section 6 asks for a separate short test on 1_WH; the built-in checks cover it for now.

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
