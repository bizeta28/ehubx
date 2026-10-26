# Step 3: Air → LT direction of energy flow

**Status: approved by Bea, 26 Oct 2026.** The 1:1 ratio was decided on 26 Oct. Scope: only Steps 1 and 3 are fixed.

## 1. Problem

`LT` is chilled water: the chiller produces it, the cooling demand consumes it. `HE_AW` (`in: Air 1`, `out: LT 0.9`) turns 25 °C DC exhaust air into LT, so waste heat *supplies cooling*. That is physically impossible. D7.2 §2.3 says the opposite: unrecovered DC air heat is rejected into the LT network, where it is an *additional cooling load* that the chiller must cover.

Evidence from the 22 Oct 1_WH run (Claude Code, `CHANGES.md`): HE_AW makes 83 % of all LT (90.2 MWh/a), the chiller only 18.7 MWh/a. The chiller is off in 6,495 h although LT is demanded. The LT peak is 64 kW against a 32 kW chiller, and in 841 h LT is met only because of HE_AW. 4_full looks almost the same.

## 2. Formulation

Redefine HE_AW as a rejection tech with the same structure as the existing `HE_LT` (inputs MT and LT, output `AirOut`):

$$\text{HE\_AW:}\quad Air\ (1)\ +\ LT\ (1)\ \longrightarrow\ AirOut\ (1)$$

With $Q_{AW}(t)\ge 0$ the air heat taken by HE_AW, the LT balance (all kW) becomes:

$$Q_{chiller}(t)+Q_{TES\_LT,dis}(t)=D_{LT}(t)+Q_{TES\_LT,ch}(t)+Q_{HE\_LT,LT}(t)+Q_{HE\_AW,LT}(t)$$
$$Q_{HE\_AW,LT}(t)=Q_{AW}(t)\qquad\text{(1:1)}$$

*Why 1:1:* the chilled-water coil absorbs exactly the air heat it removes. An efficiency below 1 on a rejection process has no clear physical meaning, so the repo's 0.9 is dropped. Do not argue from `HE_LT`: its own comment (MT → LT exchanger) does not match its implementation (MT + LT → AirOut). Justify on physics and D7.2 §2.3.

Everything else is unchanged: Air balance, HP_AW, chiller, TES_LT, costs (145 CHF/kW, 1.1 CHF/kW).

## 3. Implementation

- In `techs.yaml` change HE_AW to: `in_ecs: [Air 1 kWh, LT 1 kWh]`, `main_in_ec: Air`, `out_ecs: [AirOut, out_eff 1 kWh/kWh]`. It copies the layout of HE_LT.
- Put the change in **new case folders** (for example `*_fix3`). Do not overwrite the reference cases.
- The capacity basis of HE_AW moves from the LT output (0.9 × Air) to the AirOut output (1 × Air). Keep 145 CHF/kW and report that this shifts the cost by about 10 % of a small item. Do not tune it.
- Check feasibility: the Air carrier must always have a sink. The DC exhaust air (0.48 × waste heat) must be absorbed by HP_AW or HE_AW in every hour. Print the peak of $Q^{CS}_{Air}$ against the installed HE_AW capacity. If the solver is infeasible, report it. Do not add an Air → AirOut route on your own: that is a separate sensitivity.

## 4. Expected effect

The chiller must now cover the air heat that is not used by HP_AW, so its capacity and electricity rise and the free cooling disappears. Report the change, do not predict it.

## 5. Checks (done when all pass)

1. No tech other than the Chiller and TES_LT discharge produces `LT`. HE_AW has no LT output.
2. In every hour $Q_{HE\_AW,LT}(t)=Q_{AW}(t)$.
3. Chiller capacity is at least the LT peak net of TES_LT shaving, in both cases.
4. Report HE_AW's annual LT flow (it was 90.2 MWh/a as a producer) and the chiller's annual LT.
5. Run three cases per reference: `fix1`, `fix3`, `fix1+3`. Run `erf_kpi.py` on each and fill the rows "+ step 1", "+ step 3" and the combination: TAC, capacities, TES, DoC, $DoC_E$, ERF.
6. Write the result in `CHANGES.md`. Nothing is pushed without asking.

## 6. Open point (not changed here)

D7.2 Table 4 flags a possible double count: if the air-side PUE already includes the rack compressor, charging the chiller for the same heat counts cooling electricity twice. Exhaust to ambient without chilled water (Air → AirOut, free) stays a sensitivity case for later.
