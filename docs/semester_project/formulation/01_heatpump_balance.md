# Step 1: Heat-pump energy balance

**Status: approved by Bea, 26 Oct 2026.** Scope decision of 26 Oct: only Steps 1 and 3 are fixed. The model is not ours, so we change only what the research question needs.

## 1. Problem

`HP_AW` and `HP_WW` are `type: conversion` techs with source heat `in_part: 1 kWh` and electricity `in_part: 1 kWh`, and the heat output is $COP(t)\times$ El. They draw 1 kWh of source heat per kWh of electricity instead of $(COP-1)$ kWh, so the heat pump creates heat from nothing whenever $COP>2$.

Evidence from the 22 Oct runs (Claude Code, `CHANGES.md`): in 4_full HP_AW takes 41.3 MWh in and delivers 75.6 MWh out. In 1_WH the air heat taken by HP_AW (`A_HP` = 23.45 MWh/a) equals its electricity. The `cop: 4.5` of HP_WW in `hubs.yaml` is ignored, because the tech is `conversion`.

## 2. Formulation

Sets: $\mathcal H=\{HP_{AW},HP_{WW}\}$, $t\in T$ (hourly, 8760 h).

Variables (all $\ge 0$, kW): $P_j(t)$ electricity, $Q^{c}_j(t)$ condenser heat (output), $Q^{e}_j(t)$ evaporator heat (source), and the installed capacity $Cap_j$.

For every $j\in\mathcal H$ and every $t$:

$$Q^{c}_j(t)=COP_j(t)\,P_j(t)\qquad(1)$$
$$Q^{e}_j(t)+P_j(t)=Q^{c}_j(t)\ \ \Rightarrow\ \ Q^{e}_j(t)=\big(COP_j(t)-1\big)P_j(t)\qquad(2)$$
$$Q^{c}_j(t)\le a_j(t)\,Cap_j\qquad(3)$$

Carriers: $HP_{AW}$ takes $Q^e$ from `Air` and delivers $Q^c$ to `MT`. $HP_{WW}$ takes $Q^e$ from `MT` and delivers $Q^c$ to `HT`. Both take $P$ from `El`.

Costs: unchanged parameters (1370 CHF/kW, 430 CHF one-time), now applied to $Cap_j$ on the condenser heat output. Objective and all other techs unchanged.

COP data: both heat pumps keep `profiles/HPCOPprofile.csv`. HP_WW's own COP (35 → 65 °C) is not part of this step, so that the effect of the balance fix is isolated.

## 3. Implementation (preferred: existing ehubX submodel)

- Switch both techs to `type: heatpump` (`hp_tech_model.py` already implements (1) and (2) as `C_HpTechCopHt` and the evaporator balance, and (3) as `pow_cond <= availability * Cap`).
- The parser requires `cool_in` and `cool_out`. Map them to a dummy carrier that has no demand, no import and no export, so the cooling mode is forced to 0.
- Put the fix in **new case folders** copied from `1_WH` and `4_WH+PV+DHN+Flex` (for example `*_fix1`). Never overwrite the reference cases.
- Fallback if the dummy-carrier mapping does not work: keep `conversion` and add (2) with `modify_model`. Decision #1 in the fix plan.

Claude Code must verify before changing anything:
1. The YAML keys in `hp_tech_parser.py` (`heat_in`, `heat_out`, `cool_in`, `cool_out`, `elec`, `cop` or `profile_path`, `availability`) and what each one maps to.
2. That the capacity constraint at `hp_tech_model.py:327-331` counts the cooling-mode condenser term, and that this term is 0 with the dummy carrier.
3. That cost per kW is applied to the condenser heat output, the same basis as today. Numerically: for HP_AW in the existing 1_WH results, print $\max_t Q^c$, the installed capacity and the annualised cost per kW.

## 4. Expected effect

The air heat drawn by HP_AW rises from $1\times P$ to $(COP-1)\times P$. Electricity and heat output of the HP are not changed by the formulation itself, but the optimiser can now meet the demand differently. Do not predict TAC. Report the change.

## 5. Checks (done when all pass)

1. Hourly residual $\max_t |Q^e_j+P_j-Q^c_j|<10^{-6}$ kW for both heat pumps, in both cases.
2. $\max_t Q^c_j(t)\le Cap_j$.
3. Cooling-mode variables of both heat pumps are 0 in every hour.
4. Rerun `erf_kpi.py` on both new cases and fill the results table row "+ step 1": TAC, capacities (Chiller, AWHP), TES, DoC, $DoC_E$, ERF.
5. Write the result in `CHANGES.md`. Nothing is pushed without asking.

## 6. Not in this step

Separating DC air from ambient air (Step 2), HP_WW's own COP, any change to the air threshold.
