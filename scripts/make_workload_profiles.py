"""
Pre-processing for docs/semester_project/formulation/05_workload_flexibility.md
(v3, §4 "Profiles and pre-processing script").

Builds the load shifting profile CSV for the backlog-mode workload archetypes
from the IT demand profile of a case. For each archetype w

    arrival_flex(t) = max_below_abs(t) = theta_w * alpha_w * d_IT(t)      [kW]

where a_w(t) = alpha_w * d_IT(t) is the arriving work of archetype w (spec §2)
and theta_w its deferrable share. The script checks sum_w alpha_w = 1 and that
every alpha_w >= 0 and 0 <= theta_w <= 1. W_w and h^D_w are not needed for the
profiles; they are kept in the same parameter file so that `--print-yaml` can
print the matching `load_shifting:` block for demands.yaml.

The generated CSV is reproducible from demands.csv and the parameter file and
is NOT committed (see .gitignore, `examples/**/loadshifting_workload*.csv`).

Usage (from the repo root):
    python scripts/make_workload_profiles.py <params.yaml> [--print-yaml]

Parameter file (YAML; paths are relative to the parameter file):
    demands_csv: basic/profiles/demands.csv
    output_csv: basic/profiles/loadshifting_workload.csv
    ec: IT                 # energy carrier of the IT demand column
    stage: S1              # optional, only needed if several columns match
    hub: H1                # optional
    demands_yaml_dir: basic  # folder of demands.yaml, for the --print-yaml paths
    late_cost: 10 CHF/(kWh*h)        # pi_w, only for --print-yaml
    backlog_cost: 0.0001 CHF/(kWh*h) # epsilon, only for --print-yaml
    archetypes:
    - id: batch_rolling
      alpha: 0.5
      theta: 0.1
      deadline_type: rolling
      window: 24 h
    - id: batch_calendar
      alpha: 0.5
      theta: 0.1
      deadline_type: calendar
      deadline_hours: [5]
"""

import argparse
import csv
import os
import sys
from typing import Dict, List, Tuple

import yaml

ALPHA_TOL = 1e-9
"""Tolerance for the check sum_w alpha_w = 1"""

PROFILE_KEYS = ("arrival_flex", "max_below_abs")
"""Profile keys written per archetype; both equal theta_w * alpha_w * d_IT(t)"""


def load_params(params_path: str) -> dict:
    """Read and validate the parameter file. Raises ValueError on bad input."""
    with open(params_path, encoding="utf-8") as f:
        params = yaml.safe_load(f)
    if not isinstance(params, dict):
        raise ValueError(f"{params_path}: top level must be a mapping")
    for key in ("demands_csv", "output_csv", "ec", "archetypes"):
        if key not in params:
            raise ValueError(f"{params_path}: key '{key}' is missing")
    archetypes = params["archetypes"]
    if not isinstance(archetypes, list) or len(archetypes) == 0:
        raise ValueError(f"{params_path}: 'archetypes' must be a non-empty list")
    ids = []
    for arch in archetypes:
        for key in ("id", "alpha", "theta", "deadline_type"):
            if key not in arch:
                raise ValueError(f"{params_path}: archetype without '{key}': {arch}")
        alpha = float(arch["alpha"])
        theta = float(arch["theta"])
        if alpha < 0:
            raise ValueError(f"alpha_{arch['id']} = {alpha} < 0")
        if not 0 <= theta <= 1:
            raise ValueError(f"theta_{arch['id']} = {theta} not in [0, 1]")
        if arch["deadline_type"] == "rolling" and "window" not in arch:
            raise ValueError(f"archetype {arch['id']}: rolling needs 'window'")
        if arch["deadline_type"] == "calendar" and "deadline_hours" not in arch:
            raise ValueError(f"archetype {arch['id']}: calendar needs 'deadline_hours'")
        if arch["deadline_type"] not in ("rolling", "calendar"):
            raise ValueError(f"archetype {arch['id']}: unknown deadline_type")
        ids.append(str(arch["id"]))
    if len(set(ids)) != len(ids):
        raise ValueError(f"duplicate archetype ids: {ids}")
    # Spec §4: sum_w alpha_w = 1 (the archetypes partition d_IT)
    alpha_sum = sum(float(a["alpha"]) for a in archetypes)
    if abs(alpha_sum - 1.0) > ALPHA_TOL:
        raise ValueError(f"sum_w alpha_w = {alpha_sum!r} != 1")
    return params


def read_demand(
    demands_csv: str, ec: str, stage: str = None, hub: str = None
) -> Tuple[str, List[Tuple[str, float]]]:
    """
    Read one demand column of an ehubX demands.csv (header rows ec_id,
    stage_id, hub_id, unit; then one row per time id). Returns (unit,
    [(time_id, value), ...]) in file order.
    """
    with open(demands_csv, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.reader(f))
    header: Dict[str, List[str]] = {}
    data_rows = []
    for row in rows:
        if not row or all(cell.strip() == "" for cell in row):
            continue
        if row[0] in ("ec_id", "stage_id", "hub_id", "unit"):
            header[row[0]] = [c.strip() for c in row[1:]]
        else:
            data_rows.append(row)
    for key in ("ec_id", "stage_id", "hub_id", "unit"):
        if key not in header:
            raise ValueError(f"{demands_csv}: header row '{key}' is missing")
    matches = [
        i
        for i, e in enumerate(header["ec_id"])
        if e == ec
        and (stage is None or header["stage_id"][i] == stage)
        and (hub is None or header["hub_id"][i] == hub)
    ]
    if len(matches) != 1:
        raise ValueError(
            f"{demands_csv}: {len(matches)} columns match ec={ec}, stage={stage}, "
            f"hub={hub}; give 'stage'/'hub' in the parameter file"
        )
    col = matches[0]
    unit = header["unit"][col]
    series = [(row[0].strip(), float(row[col + 1])) for row in data_rows]
    return unit, series


def build_profiles(
    params: dict, demand: List[Tuple[str, float]]
) -> Dict[str, List[float]]:
    """theta_w * alpha_w * d_IT(t) per archetype id, in demand order."""
    out: Dict[str, List[float]] = {}
    for arch in params["archetypes"]:
        factor = float(arch["theta"]) * float(arch["alpha"])
        out[str(arch["id"])] = [factor * d for _, d in demand]
    return out


def write_csv(
    output_csv: str,
    time_ids: List[str],
    profiles: Dict[str, List[float]],
    unit: str,
) -> None:
    """
    ehubX load shifting profile CSV: header rows loadshift_id, profile_key,
    unit; then one row per time id. Two columns per archetype
    (arrival_flex, max_below_abs), both theta_w * alpha_w * d_IT(t).
    """
    ids = list(profiles)
    cols = [(ls, key) for ls in ids for key in PROFILE_KEYS]
    os.makedirs(os.path.dirname(os.path.abspath(output_csv)), exist_ok=True)
    with open(output_csv, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, lineterminator="\n")
        writer.writerow(["loadshift_id"] + [ls for ls, _ in cols])
        writer.writerow(["profile_key"] + [key for _, key in cols])
        writer.writerow(["unit"] + [unit for _ in cols])
        for i, t in enumerate(time_ids):
            writer.writerow([t] + [f"{profiles[ls][i]:.12g}" for ls, _ in cols])


def yaml_block(params: dict, output_csv_rel: str) -> str:
    """The `load_shifting:` block of demands.yaml matching the parameter file."""
    late = params.get("late_cost", "10 CHF/(kWh*h)")
    eps = params.get("backlog_cost", "0.0001 CHF/(kWh*h)")
    stage = params.get("stage", "S1")
    hub = params.get("hub", "H1")
    lines = ["load_shifting:"]
    for arch in params["archetypes"]:
        lines += [
            f"- load_shift_id: {arch['id']}",
            f"  stages: {stage}",
            f"  hubs: {hub}",
            f"  ec: {params['ec']}",
            "  mode: backlog",
            f"  deadline_type: {arch['deadline_type']}",
        ]
        if arch["deadline_type"] == "rolling":
            lines.append(f"  window: {arch['window']}")
        else:
            lines.append(f"  deadline_hours: {list(arch['deadline_hours'])}")
        lines += [
            f"  late_cost: {late}",
            f"  backlog_cost: {eps}",
            f"  profile_path: {output_csv_rel}",
        ]
    return "\n".join(lines) + "\n"


def run(params_path: str) -> dict:
    """
    Generate the profile CSV for a parameter file. Returns a summary dict:
    output path, demand unit, max d_IT, number of hours and, per archetype,
    theta, alpha and the annual deferrable work sum_t arrival_flex(t) * 1 h.
    """
    params = load_params(params_path)
    base = os.path.dirname(os.path.abspath(params_path))
    demands_csv = os.path.join(base, params["demands_csv"])
    output_csv = os.path.join(base, params["output_csv"])
    unit, demand = read_demand(
        demands_csv, str(params["ec"]), params.get("stage"), params.get("hub")
    )
    profiles = build_profiles(params, demand)
    write_csv(output_csv, [t for t, _ in demand], profiles, unit)
    summary = {
        "output_csv": output_csv,
        "unit": unit,
        "hours": len(demand),
        "max_demand": max(d for _, d in demand),
        "sum_demand": sum(d for _, d in demand),
        "archetypes": {
            str(a["id"]): {
                "alpha": float(a["alpha"]),
                "theta": float(a["theta"]),
                "sum_arrival_flex": sum(profiles[str(a["id"])]),
            }
            for a in params["archetypes"]
        },
    }
    return summary


def format_summary(summary: dict) -> str:
    u = summary["unit"]
    lines = [
        f"Wrote {summary['output_csv']}",
        f"  d_IT: {summary['hours']} h, max {summary['max_demand']:.4f} {u}, "
        f"sum_t d_IT * 1 h = {summary['sum_demand']:.1f} {u}h",
    ]
    for ls, info in summary["archetypes"].items():
        lines.append(
            f"  {ls}: alpha = {info['alpha']}, theta = {info['theta']}, "
            f"sum_t arrival_flex * 1 h = {info['sum_arrival_flex']:.1f} {u}h"
        )
    return "\n".join(lines)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[1])
    parser.add_argument("params", help="parameter file (YAML)")
    parser.add_argument(
        "--print-yaml",
        action="store_true",
        help="also print the matching load_shifting block for demands.yaml",
    )
    args = parser.parse_args(argv)
    summary = run(args.params)
    print(format_summary(summary))
    if args.print_yaml:
        params = load_params(args.params)
        # profile_path in demands.yaml is relative to the folder of
        # demands.yaml (default 'basic', seen from the parameter file in inputs/)
        rel = os.path.relpath(
            params["output_csv"], params.get("demands_yaml_dir", "basic")
        ).replace(os.sep, "/")
        print("\n" + yaml_block(params, rel))
    return 0


if __name__ == "__main__":
    sys.exit(main())
