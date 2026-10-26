# KPIs: ERF and DoC for the 1_WH family of cases

**Status: approved by Bea, 26 Oct 2026. Supervisors pending on K1, K4, K6.** Flow names are from the 1_WH `opt_vars.csv` list (Claude Code, 26 Oct 2026). They change after Step 1 (heat-pump type) and Step 3 (HE_AW becomes a rejection tech), so this file is re-checked after each step.

## 0. Conventions

- Hourly series in kW (= kWh/h), $t \in T$, $|T| = 8760$.
- ERF and the energy-weighted DoC are **ratios of annual sums**. No hourly clipping at $\ge 0$. No division by hourly totals.
- One script computes every KPI for every case (`plots and print/erf_kpi.py`, to be written after approval and committed). The old `5_ERF.py` and `5_ERF copy.py` are kept only to reproduce the paper's 56 %, never to report new numbers.

## 1. Symbols and model flows

| Symbol | Meaning | Model variable |
|---|---|---|
| $W(t)$ | Server waste heat | `V_ConvTechOut` DC → WH |
| $Q^{CS}_{HT}(t)$ | Liquid-cooling heat to HT | `V_ConvTechOut` CS_hybrid → HT |
| $Q^{CS}_{Air}(t)$ | Warm DC exhaust air | `V_ConvTechOut` CS_hybrid → Air |
| $A_{imp}(t)$ | Ambient air import | `V_Imp` Air |
| $A_{HP}(t)$ | Air heat taken by HP_AW | `V_ConvTechIn` HP_AW ← Air |
| $R_{MT}(t)$ | MT heat sent to AirOut | `V_ConvTechIn` HE_LT ← MT |
| $I_{HT}(t)$ | DHN heat import (4_full only, else 0) | `V_Imp` HT |
| $X_{HT}(t)$ | DHN heat export (4_full only, else 0) | `V_Exp` HT |
| $S^{in}(t), S^{out}(t), E(t)$ | TESHT charge, discharge, stored heat | `V_StorTechInflow`, `V_StorTechOutflow`, `V_StorTechEnergy` (TESHT) |
| $D_{HT}(t), D_{MT}(t)$ | DHW and space-heating demand | `V_DemandSupply` HT, MT |
| $P_{DC}, P_{CS}, P_{HPAW}, P_{HPWW}, P_{Ch}$ | Electricity of DC, CS_hybrid, HP_AW, HP_WW, Chiller | `V_ConvTechIn` ← El of each tech |

## 2. ERF (Eq. (11))

$$
\mathrm{ERF}=\frac{\sum_{t\in T} Q_{reuse}(t)}{\sum_{t\in T} P_{el,total}(t)}
$$

**Electricity, one list for ERF and REF:**

$$
P_{el,total}(t)=P_{DC}(t)+P_{CS}(t)+P_{HPAW}(t)+P_{HPWW}(t)+P_{Ch}(t)
$$

Not included: the building's own electricity demand and the grid export `V_Exp` El.

**Reusable heat, counted at the source side** (as D7.2 Table 6: DC heat to HT plus DC heat into the air-source HP):

$$
Q_{reuse}(t)=Q_{DC\to HT}(t)+Q_{DC\to HP_{AW}}(t)
$$

$$
Q_{DC\to HP_{AW}}(t)=\varphi_{Air}(t)\,A_{HP}(t),\qquad
\varphi_{Air}(t)=\frac{Q^{CS}_{Air}(t)}{Q^{CS}_{Air}(t)+A_{imp}(t)}\quad(\varphi_{Air}=0\text{ if the denominator is }0)
$$

$$
Q_{DC\to HT}(t)=Q^{CS}_{HT}(t)-L_{TES}(t)-R_{MT}(t)-\varphi_{HT}(t)\,X_{HT}(t),\qquad
L_{TES}(t)=S^{in}(t)-S^{out}(t)-\big(E(t)-E(t-1)\big)
$$

$$
\varphi_{HT}(t)=\frac{Q^{CS}_{HT}(t)}{Q^{CS}_{HT}(t)+I_{HT}(t)}\quad(\varphi_{HT}=1\text{ if the denominator is }0)
$$

- **1_WH:** no HT import or export, so $\varphi_{HT}X_{HT}=0$ and the formula is the one above.
- **4_full:** the DHN export is a free, unlimited sink, so DC heat that leaves through it is not reused. It is subtracted (as $Q_{exp}$ in D7.2 Table 6). The DHN import dilutes the HT carrier, hence $\varphi_{HT}$. TESHT is sized 0 there, so $L_{TES}=0$.

- $L_{TES}$ is the TESHT loss in hour $t$ (efficiency and standby). Heat charged into the tank and lost there is **not** reused. This closes the TES-sink loophole seen in the 22 Oct runs (1,980 h of simultaneous charge and discharge).
- $R_{MT}$ is MT heat dumped through HE_LT to AirOut, charged against DC heat. This is a convention (decision K2).
- The demand-side form ($D_{HT}+D_{MT}-P_{HP}-\text{ambient}$) is **not** used. In 1_WH the HP air heat is fixed at $1\times El$ instead of $COP-1$, so heat pumps with $COP>2$ create energy, and a demand-side balance would credit that phantom heat to the DC.

**Checks the script must pass on every run:**

1. $\sum_t Q_{reuse}(t) \le \sum_t W(t)\cdot 1.38$ (the heat that leaves the cooling system: $0.9+0.48$ per unit of $W$).
2. $\sum_t Q_{reuse}(t) \le \sum_t \big(D_{HT}(t)+D_{MT}(t)\big)$.
3. TESHT: $E(T)\approx E(0)$ (cyclic). If not, report $\Delta E$ with the result.
4. Print the terms $Q^{CS}_{HT}$, $L_{TES}$, $R_{MT}$, $\varphi_{HT}X_{HT}$ and the $P_{el,total}$ breakdown next to the ERF, so every number can be traced.
5. 4_full only: report the hours with $I_{HT}(t)>0$ and $X_{HT}(t)>0$ at the same time. They should be none. If there are some, $\varphi_{HT}$ is not meaningful in those hours.

**Case notes (flows from the 1_WH and 4_full variable lists):**

- 4_full adds PV and BES. They do not enter $P_{el,total}$: it counts the electricity the five techs consume, whatever its source (grid, PV or battery).
- 4_full has IT load shifting (`ls3`, 10 %, 24 h blocks). It changes $P_{DC}(t)$ and $W(t)$ but not the definitions. $D(t)$ stays the heat demand.
- 4_full has 271 non-zero hours of El export, including zero-price import and export loops. They do not affect ERF, but check them before quoting electricity totals.

## 3. DoC

Hourly, as D7.2, with $D(t)=D_{HT}(t)+D_{MT}(t)$:

$$
\mathrm{DoC}=\frac{1}{|T|}\sum_t \min\!\Big\{1,\ \frac{\max\{0,\,Q_{reuse}(t)\}}{D(t)}\Big\}\quad(\text{hours with }D(t)=0\text{ excluded})
$$

Energy-weighted, reported next to it (July hours with 1 kW of DHW otherwise count as much as January hours at 40 kW):

$$
\mathrm{DoC}_E=\frac{\sum_t \min\{\max\{0,Q_{reuse}(t)\},\,D(t)\}}{\sum_t D(t)}
$$

Here the lower bound at 0 is part of the definition of a share. It does not touch the annual ERF sum.

## 4. REF

Not defined here. Eq. (12) is not in the notes yet. It must use the same $P_{el,total}$ list as the ERF above.

## 5. Decisions needed

| # | Decision | Who | Default in this draft |
|---|---|---|---|
| K1 | Which electricity enters $P_{el,total}$ | Bea, then supervisors | DC + CS_hybrid + HP_AW + HP_WW + Chiller |
| K2 | Charge dumped MT heat ($R_{MT}$) fully against DC heat | Bea | yes (conservative) |
| K3 | Air split $\varphi_{Air}$ by proportional mixing | Bea | yes |
| K4 | Is the cooling electricity of the Chiller part of the system boundary | Supervisors | yes |
| K5 | How to disclose the published 56 % | Gabriele | state the HE_LT bug as a fact, ask how to correct it |
| K6 | 4_full: DHN export is subtracted from DC heat, and the import dilutes it by $\varphi_{HT}$ | Bea, then supervisors | yes |

## 6. After approval

1. Claude Code writes `plots and print/erf_kpi.py` and a short test on the 1_WH results.
2. Run the 22 Oct reference runs (1_WH, 4_full) and put the numbers in the results table in `model_fix_plan.md`. Do not compare them with 47.5 % or 56 %: the definition is different.
3. Re-derive $R_{MT}$, $Q^{CS}_{Air}$ and the HP flows after Step 1 and Step 3.
