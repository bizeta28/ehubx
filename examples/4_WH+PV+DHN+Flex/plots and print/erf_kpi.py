"""
KPIs from docs/semester_project/formulation/kpis.md, sections 2 and 3: ERF, DoC, DoC_E.
REF (section 4) is not defined yet and is not computed.

One script for the whole 1_WH family of cases. Run from the repo root:
    python "examples/4_WH+PV+DHN+Flex/plots and print/erf_kpi.py" examples/1_WH
    python "examples/4_WH+PV+DHN+Flex/plots and print/erf_kpi.py" "examples/4_WH+PV+DHN+Flex"
Optional second argument: results subfolder (default: results).

Hourly series are in kW (= kWh/h), annual sums in MWh/a. Nothing is written to disk.
"""

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

N_HOURS = 8760
TOL = 1e-6  # numerical zero [kW, kWh]
CS_HEAT_PER_W = 0.9 + 0.48  # heat leaving CS_hybrid per unit of W (check 1) [kWh/kWh]

# =====================================================
# FLOWS (kpis.md section 1)
# =====================================================
# symbol: (results file, variable, carrier, tech, unit, optional)
# Optional flows are 0 when the case has no such variable (I_HT, X_HT in 1_WH).

FLOWS = {
    "W":        ("tech-TS", "V_ConvTechOut", "WH", "DC", "kW", False),
    "Q_CS_HT":  ("tech-TS", "V_ConvTechOut", "HT", "CS_hybrid", "kW", False),
    "Q_CS_Air": ("tech-TS", "V_ConvTechOut", "Air", "CS_hybrid", "kW", False),
    "A_imp":    ("import_export-TS", "V_Imp", "Air", None, "kW", False),
    "A_HP":     ("tech-TS", "V_ConvTechIn", "Air", "HP_AW", "kW", False),
    "R_MT":     ("tech-TS", "V_ConvTechIn", "MT", "HE_LT", "kW", False),
    "I_HT":     ("import_export-TS", "V_Imp", "HT", None, "kW", True),
    "X_HT":     ("import_export-TS", "V_Exp", "HT", None, "kW", True),
    "S_in":     ("tech-TS", "V_StorTechInflow", None, "TESHT", "kW", False),
    "S_out":    ("tech-TS", "V_StorTechOutflow", None, "TESHT", "kW", False),
    "E":        ("tech-TS", "V_StorTechEnergy", None, "TESHT", "h*kW", False),
    "D_HT":     ("loads-TS", "V_DemandSupply", "HT", None, "kW", False),
    "D_MT":     ("loads-TS", "V_DemandSupply", "MT", None, "kW", False),
    "P_DC":     ("tech-TS", "V_ConvTechIn", "El", "DC", "kW", False),
    "P_CS":     ("tech-TS", "V_ConvTechIn", "El", "CS_hybrid", "kW", False),
    "P_HPAW":   ("tech-TS", "V_ConvTechIn", "El", "HP_AW", "kW", False),
    "P_HPWW":   ("tech-TS", "V_ConvTechIn", "El", "HP_WW", "kW", False),
    "P_Ch":     ("tech-TS", "V_ConvTechIn", "El", "Chiller", "kW", False),
}


def fail(msg):
    sys.exit(f"ERROR: {msg}")


# =====================================================
# READ RESULTS
# =====================================================

def read_ts(path):
    """
    Read an ehubX *-TS.csv. These files are dense (zeros included), with
    labelled header rows (Entry, Unit, Ec, Tech, ...) above 8760 hourly rows.
    Returns (header rows indexed by label, hourly values).
    """
    if not path.exists():
        fail(f"missing results file {path}")
    raw = pd.read_csv(path, header=None, dtype=str, keep_default_na=False)
    is_hour = raw[0].str.fullmatch(r"\d+(\.0)?")
    n_head = int(is_hour.idxmax())
    head = raw.iloc[:n_head].set_index(0)
    data = raw.iloc[n_head:, 1:].astype(float).reset_index(drop=True)
    if len(data) != N_HOURS:
        fail(f"{path.name}: expected {N_HOURS} hourly rows, found {len(data)}")
    return head, data


def get_flow(ts_files, symbol):
    """Hourly series of one flow from FLOWS, matched on variable, carrier and tech."""
    file, var, ec, tech, unit, optional = FLOWS[symbol]
    head, data = ts_files[file]
    mask = head.loc["Entry"].str.endswith(f"({var})")
    if ec is not None:
        mask &= head.loc["Ec"] == ec
    if tech is not None:
        mask &= head.loc["Tech"] == tech
    cols = mask[mask].index
    if len(cols) == 0:
        if optional:
            absent.add(symbol)
            return np.zeros(N_HOURS)
        fail(f"{symbol}: {var} (carrier {ec}, tech {tech}) not found in {file}.csv")
    if len(cols) > 1:
        fail(f"{symbol}: {var} (carrier {ec}, tech {tech}) is ambiguous in {file}.csv")
    if head.loc["Unit", cols[0]] != unit:
        fail(f"{symbol}: unit is {head.loc['Unit', cols[0]]}, expected {unit}")
    return data[cols[0]].to_numpy()


def opt_vars_sum(opt_vars, symbol):
    """
    Annual sum of the same flow from opt_vars.csv (sparse: zeros are not written).
    Storage energy is indexed by S_TimeHorizon, all flows by S_Time.
    """
    _, var, ec, tech, _, _ = FLOWS[symbol]
    f = (opt_vars.var_name == var) & (opt_vars.S_Time.notna() | opt_vars.S_TimeHorizon.notna())
    if ec is not None:
        f &= opt_vars.S_Ec == ec
    if tech is not None:
        f &= opt_vars.S_Tech == tech
    return opt_vars.loc[f, "var_value"].sum()


parser = argparse.ArgumentParser(description="ERF, DoC, DoC_E as in kpis.md")
parser.add_argument("case", type=Path, help="case folder, e.g. examples/1_WH")
parser.add_argument("results", nargs="?", default="results", help="results subfolder")
args = parser.parse_args()
res = args.case / args.results

ts_files = {n: read_ts(res / f"{n}.csv") for n in ("tech-TS", "import_export-TS", "loads-TS")}
absent = set()  # optional flows the case does not have (set to 0)
f = {s: get_flow(ts_files, s) for s in FLOWS}

# Final TESHT level after the last hour [kWh] (tech.csv, not a time series)
tech = pd.read_csv(res / "tech.csv")
row = tech[(tech.Entry == "Final storage energy (V_StorTechEnergyFinal)") & (tech.Tech == "TESHT")]
if len(row) != 1:
    fail("V_StorTechEnergyFinal for TESHT not found in tech.csv")
E_final = float(row.Value.iloc[0])

# Parse check: every series must have the same annual sum as in opt_vars.csv
opt_vars = pd.read_csv(res / "opt_vars.csv", low_memory=False)
parse_bad = [s for s in FLOWS
             if abs(f[s].sum() - opt_vars_sum(opt_vars, s)) > 1e-6 * max(1.0, abs(f[s].sum()))]

# =====================================================
# ERF (kpis.md section 2)
# =====================================================

# Electricity: P_el,total = P_DC + P_CS + P_HPAW + P_HPWW + P_Ch
P_total = f["P_DC"] + f["P_CS"] + f["P_HPAW"] + f["P_HPWW"] + f["P_Ch"]

# DC share of the Air carrier: phi_Air = Q_CS_Air / (Q_CS_Air + A_imp), 0 if no air
den_air = f["Q_CS_Air"] + f["A_imp"]
phi_air = np.divide(f["Q_CS_Air"], den_air, out=np.zeros(N_HOURS), where=den_air > TOL)

# DC heat into the air-source HP: Q_DC->HP_AW = phi_Air * A_HP
Q_DC_HPAW = phi_air * f["A_HP"]

# TESHT loss: L_TES(t) = S_in(t) - S_out(t) - (E(t) - E(t-1)).
# The spec's E(t) is the level at the END of hour t. ehubX's V_StorTechEnergy[t]
# is the level at the START of hour t, so E(0) = V_StorTechEnergy[1],
# E(t) = V_StorTechEnergy[t+1] and E(T) = V_StorTechEnergyFinal.
E_spec = np.append(f["E"], E_final)  # E(0) ... E(T), 8761 values
L_TES = f["S_in"] - f["S_out"] - np.diff(E_spec)

# DC share of the HT carrier: phi_HT = Q_CS_HT / (Q_CS_HT + I_HT), 1 if no HT
den_ht = f["Q_CS_HT"] + f["I_HT"]
phi_ht = np.divide(f["Q_CS_HT"], den_ht, out=np.ones(N_HOURS), where=den_ht > TOL)

# DC heat to HT: Q_DC->HT = Q_CS_HT - L_TES - R_MT - phi_HT * X_HT
X_DC = phi_ht * f["X_HT"]
Q_DC_HT = f["Q_CS_HT"] - L_TES - f["R_MT"] - X_DC

# Q_reuse = Q_DC->HT + Q_DC->HP_AW; ERF as a ratio of annual sums, no clipping
Q_reuse = Q_DC_HT + Q_DC_HPAW
ERF = Q_reuse.sum() / P_total.sum()

# =====================================================
# DoC (kpis.md section 3)
# =====================================================

D = f["D_HT"] + f["D_MT"]
has_D = D > TOL
Q_pos = np.maximum(0.0, Q_reuse)

# Hourly DoC: (1/|T|) * sum over hours with D > 0 of min(1, max(0, Q_reuse) / D), |T| = 8760
cover = np.minimum(1.0, np.divide(Q_pos, D, out=np.zeros(N_HOURS), where=has_D))
DoC = cover[has_D].sum() / N_HOURS

# Energy-weighted: DoC_E = sum min(max(0, Q_reuse), D) / sum D
DoC_E = np.minimum(Q_pos, D).sum() / D.sum()

# =====================================================
# CHECKS (kpis.md section 2)
# =====================================================

mwh = lambda x: x.sum() / 1e3  # annual sum [MWh/a]

checks = {}
# 1. Q_reuse <= 1.38 * W (annual)
checks["1  sum Q_reuse <= 1.38 sum W"] = (
    Q_reuse.sum() <= CS_HEAT_PER_W * f["W"].sum() + TOL,
    f"{mwh(Q_reuse):.2f} <= {CS_HEAT_PER_W * mwh(f['W']):.2f} MWh/a")
# 2. Q_reuse <= D_HT + D_MT (annual)
checks["2  sum Q_reuse <= sum (D_HT + D_MT)"] = (
    Q_reuse.sum() <= D.sum() + TOL,
    f"{mwh(Q_reuse):.2f} <= {mwh(D):.2f} MWh/a")
# 3. TESHT cyclic: E(T) = E(0)
dE = E_spec[-1] - E_spec[0]
checks["3  TESHT E(T) = E(0)"] = (
    abs(dE) <= TOL,
    f"E(0) = {E_spec[0]:.4f} kWh, E(T) = {E_spec[-1]:.4f} kWh, dE = {dE:.4f} kWh")
# 5. No simultaneous HT import and export (only meaningful when the case has DHN)
n_both = int(((f["I_HT"] > TOL) & (f["X_HT"] > TOL)).sum())
has_dhn = not ({"I_HT", "X_HT"} & absent)
checks["5  hours with I_HT > 0 and X_HT > 0"] = (
    (n_both == 0) if has_dhn else None,
    f"{n_both} h" if has_dhn else "no HT import/export in this case")

# =====================================================
# REPORT
# =====================================================

print(f"Case: {args.case}  ({res})")
print(f"Parse check (TS files vs opt_vars.csv annual sums): "
      f"{'PASS' if not parse_bad else 'FAIL: ' + ', '.join(parse_bad)}")

print("\nERF terms (check 4) [MWh/a]")
print(f"  Q_CS_HT                 {mwh(f['Q_CS_HT']):10.2f}")
print(f"  - L_TES                 {-mwh(L_TES):10.2f}   (hours with L_TES < 0: {(L_TES < -TOL).sum()})")
print(f"  - R_MT                  {-mwh(f['R_MT']):10.2f}")
print(f"  - phi_HT * X_HT         {-mwh(X_DC):10.2f}   (X_HT {mwh(f['X_HT']):.2f}, I_HT {mwh(f['I_HT']):.2f})")
print(f"  = Q_DC->HT              {mwh(Q_DC_HT):10.2f}")
print(f"  + phi_Air * A_HP        {mwh(Q_DC_HPAW):10.2f}   (A_HP {mwh(f['A_HP']):.2f}, Q_CS_Air {mwh(f['Q_CS_Air']):.2f}, A_imp {mwh(f['A_imp']):.2f})")
print(f"  = Q_reuse               {mwh(Q_reuse):10.2f}   (hours with Q_reuse < 0: {(Q_reuse < -TOL).sum()})")
print("  P_el,total breakdown")
for s in ("P_DC", "P_CS", "P_HPAW", "P_HPWW", "P_Ch"):
    print(f"    {s:20s}  {mwh(f[s]):10.2f}")
print(f"  = P_el,total            {mwh(P_total):10.2f}")

print("\nKPIs")
print(f"  ERF    {ERF * 100:6.2f} %")
print(f"  DoC    {DoC * 100:6.2f} %   (hourly, |T| = {N_HOURS}, {(~has_D).sum()} h with D = 0 excluded from the sum)")
print(f"  DoC_E  {DoC_E * 100:6.2f} %   (energy-weighted, D = {mwh(D):.2f} MWh/a)")

print("\nChecks")
for name, (ok, detail) in checks.items():
    status = "N/A " if ok is None else ("PASS" if ok else "FAIL")
    print(f"  {status}  {name:38s} {detail}")
