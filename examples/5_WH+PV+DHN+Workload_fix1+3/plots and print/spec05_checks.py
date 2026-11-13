"""
Checks of section 5 of formulation/05_workload_flexibility.md (v3) on a solved
run of a backlog-mode case. Read-only.

    python "examples/5_WH+PV+DHN+Workload_fix1+3/plots and print/spec05_checks.py" \
        examples/5_WH+PV+DHN+Workload_fix1+3 [--results results] \
        [--noflex examples/4_WH+PV+DHN+Flex_fix1+3_noflex/results]

Reports (§5.4): TAC_sys, V_SystemCost, sum L (must be 0), eps * sum B, solve
time and MIP gap from the Gurobi log (gurobi_<results>.log in the case folder).
With --noflex, compares TAC and the installed capacities with the no-flex run
(§5.3, theta = 0 regression: everything must match).
"""

import argparse
import re
from pathlib import Path

import pandas as pd

ENTRY_COST = "Cost (V_SystemCost)"
ENTRY_TAC_SYS = "System cost without load shifting penalties"  # prefix
ENTRY_LATE_COST = "Total lateness penalty"
ENTRY_BACKLOG_COST = "Total backlog tie-break cost"
ENTRY_LATE_SUM = "Total lateness (sum_t V_LoadShiftingLate * dt)"
ENTRY_CAP = "Tech capacity (V_TechCap)"
TOL_L = 1e-6  # kWh h
TOL_TAC = 1e-3  # CHF
TOL_CAP = 1e-4  # kW / kWh


def rows(df: pd.DataFrame, entry_prefix: str) -> pd.DataFrame:
    return df[df["Entry"].str.startswith(entry_prefix)]


def read_static(results: Path, name: str) -> pd.DataFrame:
    return pd.read_csv(results / f"{name}.csv", keep_default_na=False)


def gurobi_summary(log_path: Path) -> dict:
    """Solve time and gap from a Gurobi log. LP: 'Solved in N iterations and
    X seconds'. MIP: 'Explored N nodes ... in X seconds' + 'gap X%'."""
    out = {"log": str(log_path), "found": log_path.is_file()}
    if not log_path.is_file():
        return out
    txt = log_path.read_text(errors="replace")
    m = re.findall(r"Solved in (\d+) iterations and ([\d.]+) seconds", txt)
    if m:
        out["lp_iterations"], out["solve_time_s"] = int(m[-1][0]), float(m[-1][1])
    m = re.findall(r"Explored (\d+) nodes .*? in ([\d.]+) seconds", txt)
    if m:
        out["nodes"], out["solve_time_s"] = int(m[-1][0]), float(m[-1][1])
    m = re.findall(r"gap ([\d.e+-]+)%", txt)
    out["mip_gap_pct"] = float(m[-1]) if m else None
    m = re.findall(r"Optimal objective\s+([\d.e+-]+)", txt)
    if m:
        out["optimal_objective"] = float(m[-1])
    m = re.findall(r"Best objective ([\d.e+-]+), best bound ([\d.e+-]+)", txt)
    if m:
        out["best_objective"], out["best_bound"] = float(m[-1][0]), float(m[-1][1])
    out["is_lp"] = "nodes" not in out
    return out


def capacities(results: Path) -> pd.Series:
    tech = read_static(results, "tech")
    cap = rows(tech, ENTRY_CAP)
    return pd.Series(
        {f"{t} [{u}]": float(v) for t, u, v in zip(cap["Tech"], cap["Unit"], cap["Value"])}
    )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("case", type=Path, help="case folder")
    ap.add_argument("--results", default="results", help="results subfolder")
    ap.add_argument("--noflex", type=Path, help="results folder of the no-flex run")
    args = ap.parse_args()
    results = args.case / args.results
    system = read_static(results, "system")
    loads = read_static(results, "loads")

    cost = float(rows(system, ENTRY_COST)["Value"].iloc[0])
    tac_sys_rows = rows(system, ENTRY_TAC_SYS)
    print(f"Run: {results}")
    print(f"  V_SystemCost (incl. penalties) : {cost:,.2f} CHF/a")
    status = 0
    if len(tac_sys_rows):
        tac_sys = float(tac_sys_rows["Value"].iloc[0])
        late_cost = float(rows(system, ENTRY_LATE_COST)["Value"].iloc[0])
        backlog_cost = float(rows(system, ENTRY_BACKLOG_COST)["Value"].iloc[0])
        print(f"  TAC_sys                        : {tac_sys:,.2f} CHF/a")
        print(f"  pi * sum L                     : {late_cost:.6f} CHF/a")
        print(f"  eps * sum B                    : {backlog_cost:.6f} CHF/a")
        for _, r in rows(system, ENTRY_LATE_SUM).iterrows():
            late_sum = float(r["Value"])
            ok = abs(late_sum) <= TOL_L
            status |= 0 if ok else 1
            print(f"  sum L ({r['Ec']})                   : {late_sum:.3e} {r['Unit']}  "
                  f"-> {'PASS' if ok else 'FAIL'} (must be 0, §5.4)")
        for _, r in rows(loads, ENTRY_LATE_SUM).iterrows():
            print(f"    {r['Load shift']:>16s}: sum L = {float(r['Value']):.3e} {r['Unit']}")
        for _, r in rows(loads, "Load shifting cost backlog").iterrows():
            print(f"    {r['Load shift']:>16s}: eps * sum B = {float(r['Value']):.6f} CHF")
    else:
        tac_sys = cost
        print("  (no backlog-mode load shift: TAC_sys = V_SystemCost)")

    g = gurobi_summary(args.case / f"gurobi_{args.results}.log")
    if g["found"]:
        kind = "LP" if g.get("is_lp") else "MIP"
        gap = g.get("mip_gap_pct")
        print(f"  Gurobi ({kind}): solve time {g.get('solve_time_s', float('nan')):.1f} s, "
              f"gap {'n/a (LP, exact)' if gap is None else f'{gap} %'}, "
              f"objective {g.get('optimal_objective', g.get('best_objective'))}")
    else:
        print(f"  Gurobi log not found: {g['log']}")

    if args.noflex is not None:
        nf_system = read_static(args.noflex, "system")
        nf_cost = float(rows(nf_system, ENTRY_COST)["Value"].iloc[0])
        d = tac_sys - nf_cost
        ok = abs(d) <= TOL_TAC
        status |= 0 if ok else 2
        print(f"\nComparison with no-flex run {args.noflex}")
        print(f"  TAC no-flex                    : {nf_cost:,.2f} CHF/a")
        print(f"  TAC_sys - TAC no-flex          : {d:+.4f} CHF/a -> {'PASS' if ok else 'FAIL'} (tol {TOL_TAC})")
        cap = pd.concat(
            [capacities(results).rename("this run"), capacities(args.noflex).rename("no-flex")],
            axis=1,
        )
        cap["diff"] = cap["this run"] - cap["no-flex"]
        print(cap.to_string(float_format=lambda x: f"{x:.4f}"))
        cap_ok = (cap["diff"].abs() <= TOL_CAP).all()
        status |= 0 if cap_ok else 4
        print(f"  capacities equal within {TOL_CAP}: {'PASS' if cap_ok else 'FAIL'}")
    return status


if __name__ == "__main__":
    raise SystemExit(main())
