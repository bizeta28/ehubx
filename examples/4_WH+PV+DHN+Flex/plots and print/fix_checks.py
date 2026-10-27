"""
Checks of section 5 of formulation/01_heatpump_balance.md (Step 1) and
formulation/03_air_lt_direction.md (Step 3), plus the results-table row
(TAC, capacities, TES). ERF, DoC and DoC_E come from erf_kpi.py.

One script for the whole 1_WH family of cases. Run from the repo root:
    python "examples/4_WH+PV+DHN+Flex/plots and print/fix_checks.py" examples/1_WH_fix1
Optional second argument: results subfolder (default: results).

Step 1 checks run when HP_AW/HP_WW are `type: heatpump` (V_HpTechIn in the results),
Step 3 checks when HE_AW outputs AirOut. Hourly series in kW, annual sums in MWh/a.
Nothing is written to disk.
"""

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

N_HOURS = 8760
TOL = 1e-6  # numerical zero [kW] (spec 01, check 1)


def fail(msg):
    sys.exit(f"ERROR: {msg}")


def read_ts(path):
    """Dense ehubX *-TS.csv: labelled header rows above 8760 hourly rows (as in erf_kpi.py)."""
    if not path.exists():
        fail(f"missing results file {path}")
    raw = pd.read_csv(path, header=None, dtype=str, keep_default_na=False)
    n_head = int(raw[0].str.fullmatch(r"\d+(\.0)?").idxmax())
    head = raw.iloc[:n_head].set_index(0)
    data = raw.iloc[n_head:, 1:].astype(float).reset_index(drop=True)
    if len(data) != N_HOURS:
        fail(f"{path.name}: expected {N_HOURS} hourly rows, found {len(data)}")
    return head, data


def cols(ts, var, ec=None, tech=None):
    """Column labels of variable var, optionally filtered by carrier and tech."""
    head, _ = ts
    mask = head.loc["Entry"].str.endswith(f"({var})")
    if ec is not None:
        mask &= head.loc["Ec"] == ec
    if tech is not None:
        mask &= head.loc["Tech"] == tech
    return list(mask[mask].index)


def series(ts, var, ec=None, tech=None, required=True):
    """Hourly series of one variable; zeros if absent and not required."""
    c = cols(ts, var, ec, tech)
    if len(c) > 1:
        fail(f"{var} (carrier {ec}, tech {tech}) is ambiguous")
    if not c:
        if required:
            fail(f"{var} (carrier {ec}, tech {tech}) not found")
        return np.zeros(N_HOURS)
    return ts[1][c[0]].to_numpy()


def cop_profile(case, tech):
    """Hourly COP of one tech from the case's HPCOPprofile.csv (header rows up to 'unit' or 'ec_id')."""
    raw = pd.read_csv(case / "inputs/basic/profiles/HPCOPprofile.csv", header=None, dtype=str)
    n_head = int(raw[0].str.fullmatch(r"\d+").idxmax())
    head = raw.iloc[:n_head].set_index(0)
    c = head.columns[head.loc["tech_id"] == tech]
    return raw.iloc[n_head:][c[0]].astype(float).to_numpy()


mwh = lambda x: x.sum() / 1e3  # annual sum [MWh/a]

parser = argparse.ArgumentParser(description="Section 5 checks of specs 01 and 03")
parser.add_argument("case", type=Path, help="case folder, e.g. examples/1_WH_fix1")
parser.add_argument("results", nargs="?", default="results", help="results subfolder")
args = parser.parse_args()
res = args.case / args.results

tech_ts = read_ts(res / "tech-TS.csv")
loads_ts = read_ts(res / "loads-TS.csv")
tech = pd.read_csv(res / "tech.csv")
system = pd.read_csv(res / "system.csv")


def tech_value(entry_var, x):
    r = tech[tech.Entry.str.endswith(f"({entry_var})") & (tech.Tech == x)]
    return float(r.Value.iloc[0]) if len(r) == 1 else float("nan")


checks = {}  # name -> (ok, detail)

# =====================================================
# RESULTS-TABLE ROW
# =====================================================

tac = float(system[system.Entry == "Cost (V_SystemCost)"].Value.iloc[0])
print(f"Case: {args.case}  ({res})")
print(f"  TAC {tac:,.2f} CHF/a")
print("  Capacities [kW / kWh]: " + ", ".join(
    f"{x} {tech_value('V_TechCap', x):.2f}"
    for x in ("Chiller", "HP_AW", "HP_WW", "HE_AW", "HE_WW", "HE_LT", "TESHT", "TESMT", "TESLT", "BES", "PV")
    if not np.isnan(tech_value("V_TechCap", x))))

# =====================================================
# STEP 1 (spec 01, section 5)
# =====================================================
# HP j: Q^e = V_HpTechIn on heat_in, P = V_HpTechIn on El (= V_HpTechElecHt + V_HpTechElecCo),
# Q^c = V_HpTechOut on heat_out.

HPS = {"HP_AW": ("Air", "MT"), "HP_WW": ("MT", "HT")}  # tech: (heat_in, heat_out)
if cols(tech_ts, "V_HpTechIn"):
    print("\nStep 1 [kW, MWh/a]")
    for x, (ec_in, ec_out) in HPS.items():
        Qe = series(tech_ts, "V_HpTechIn", ec_in, x)
        P = series(tech_ts, "V_HpTechIn", "El", x)
        Qc = series(tech_ts, "V_HpTechOut", ec_out, x)
        P_ht = series(tech_ts, "V_HpTechElecHt", None, x)
        cap = tech_value("V_TechCap", x)
        cop = cop_profile(args.case, x)
        # (2) energy balance Q^e + P = Q^c
        r_bal = np.abs(Qe + P - Qc).max()
        # (1) Q^c = COP(t) P, with COP from the profile (not the scalar cop in hubs.yaml)
        r_cop = np.abs(Qc - cop * P).max()
        checks[f"S1.1 {x} max|Q^e + P - Q^c| < 1e-6"] = (r_bal < TOL, f"{r_bal:.2e} kW")
        checks[f"S1.1 {x} max|Q^c - COP(t) P|  (profile COP)"] = (r_cop < TOL, f"{r_cop:.2e} kW")
        # (3) Q^c <= Cap
        checks[f"S1.2 {x} max Q^c <= Cap"] = (
            Qc.max() <= cap + TOL, f"max Q^c {Qc.max():.4f} kW, Cap {cap:.4f} kW")
        # Cooling mode: El, condenser input and evaporator output on the dummy carrier
        cool = [series(tech_ts, "V_HpTechElecCo", None, x)]
        cool_in = [tech_ts[1][c].to_numpy() for c in cols(tech_ts, "V_HpTechIn", None, x)
                   if tech_ts[0].loc["Ec", c] not in ("El", ec_in)]
        cool_out = [tech_ts[1][c].to_numpy() for c in cols(tech_ts, "V_HpTechOut", None, x)
                    if tech_ts[0].loc["Ec", c] != ec_out]
        cool_max = max(np.abs(s).max() for s in cool + cool_in + cool_out)
        checks[f"S1.3 {x} cooling-mode flows = 0"] = (
            cool_max < TOL,
            f"max {cool_max:.2e} kW over V_HpTechElecCo and {len(cool_in) + len(cool_out)} dummy-carrier flows")
        print(f"  {x}: Q^c {mwh(Qc):.2f}, P {mwh(P):.2f}, Q^e {mwh(Qe):.2f} = (COP-1)P {mwh((cop - 1) * P):.2f}; "
              f"P_ht - P = {np.abs(P_ht - P).max():.1e} kW; Cap {cap:.2f} kW_th, "
              f"CAPEX {tech_value('V_TechCostCapex', x) / cap if cap > 0 else float('nan'):.2f} CHF/(kW_th a)")

# =====================================================
# STEP 3 (spec 03, sections 3 and 5)
# =====================================================

if cols(tech_ts, "V_ConvTechOut", "AirOut", "HE_AW"):
    print("\nStep 3 [kW, MWh/a]")
    # 1. LT producers: every output-type column on LT with a non-zero value
    lt_out = cols(tech_ts, "V_ConvTechOut", "LT") + cols(tech_ts, "V_HpTechOut", "LT")
    producers = {tech_ts[0].loc["Tech", c]: mwh(tech_ts[1][c]) for c in lt_out
                 if np.abs(tech_ts[1][c]).max() > TOL}
    he_aw_lt_out = cols(tech_ts, "V_ConvTechOut", "LT", "HE_AW")
    checks["S3.1 only Chiller (+ TESLT discharge) produce LT"] = (
        set(producers) <= {"Chiller"} and not he_aw_lt_out,
        f"LT producers: {producers}; HE_AW LT output columns: {len(he_aw_lt_out)}")
    # 2. Q_HE_AW,LT(t) = Q_AW(t)
    Q_AW = series(tech_ts, "V_ConvTechIn", "Air", "HE_AW")
    Q_AW_LT = series(tech_ts, "V_ConvTechIn", "LT", "HE_AW")
    r = np.abs(Q_AW_LT - Q_AW).max()
    checks["S3.2 max|Q_HE_AW,LT - Q_AW| < 1e-6"] = (r < TOL, f"{r:.2e} kW")
    # 3. Chiller capacity vs LT peak net of TES_LT shaving.
    #    Net LT load(t) = D_LT + HE_LT(LT) + HE_AW(LT) + TESLT charge - TESLT discharge.
    D_LT = series(loads_ts, "V_DemandSupply", "LT")
    HE_LT_LT = series(tech_ts, "V_ConvTechIn", "LT", "HE_LT")
    ch = series(tech_ts, "V_StorTechInflow", None, "TESLT")
    dis = series(tech_ts, "V_StorTechOutflow", None, "TESLT")
    Q_ch = series(tech_ts, "V_ConvTechOut", "LT", "Chiller")
    net = D_LT + HE_LT_LT + Q_AW_LT + ch - dis
    cap_ch = tech_value("V_TechCap", "Chiller")
    checks["S3.3 Cap_Chiller >= LT peak net of TESLT"] = (
        cap_ch >= net.max() - TOL,
        f"Cap {cap_ch:.2f} kW; net LT peak {net.max():.2f} kW "
        f"(D_LT only, net of TESLT: {(D_LT + ch - dis).max():.2f} kW; D_LT peak {D_LT.max():.2f} kW)")
    # LT balance of spec 03 section 2: Chiller + TESLT discharge = D_LT + TESLT charge + HE_LT + HE_AW.
    # A residual of ~0 also shows that no other LT flow exists.
    r_bal = np.abs(Q_ch + dis - (D_LT + ch + HE_LT_LT + Q_AW_LT)).max()
    print(f"  LT balance residual max|Q_ch + Q_dis - (D_LT + Q_ch,TES + HE_LT + HE_AW)| = {r_bal:.2e} kW")
    # 4. Annual flows
    print(f"  HE_AW LT (now a load) {mwh(Q_AW_LT):.2f} MWh/a; Chiller LT {mwh(Q_ch):.2f} MWh/a; "
          f"Chiller El {mwh(series(tech_ts, 'V_ConvTechIn', 'El', 'Chiller')):.2f} MWh/a")
    print(f"  LT loads: D_LT {mwh(D_LT):.2f}, HE_LT {mwh(HE_LT_LT):.2f}, HE_AW {mwh(Q_AW_LT):.2f}, "
          f"TESLT charge {mwh(ch):.2f} / discharge {mwh(dis):.2f}")
    # Feasibility (spec 03 section 3): peak DC exhaust air vs HE_AW capacity
    Q_CS_Air = series(tech_ts, "V_ConvTechOut", "Air", "CS_hybrid")
    print(f"  peak Q^CS_Air {Q_CS_Air.max():.2f} kW vs installed HE_AW {tech_value('V_TechCap', 'HE_AW'):.2f} kW "
          f"(HE_AW at cap in {(Q_AW >= tech_value('V_TechCap', 'HE_AW') - TOL).sum() if Q_AW.max() > TOL else 0} h)")

print("\nChecks")
if not checks:
    print("  none: neither Step 1 nor Step 3 is active in this case")
for name, (ok, detail) in checks.items():
    print(f"  {'PASS' if ok else 'FAIL'}  {name:48s} {detail}")
