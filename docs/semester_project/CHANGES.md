# Implementation-side change log

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
