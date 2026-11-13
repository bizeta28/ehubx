"""
Workload flexibility case, spec 05 v3
(docs/semester_project/formulation/05_workload_flexibility.md). Copy of
4_WH+PV+DHN+Flex_fix1+3 with two backlog-mode archetypes (inputs/basic/demands.yaml).

Before parsing, the load shifting profiles (arrival_flex = max_below_abs =
theta_w * alpha_w * d_IT(t)) are regenerated from a parameter file with
scripts/make_workload_profiles.py (§4). Solver settings as the reference cases
(MIP focus 1, Method 0) plus MIP gap 0 and a Gurobi log file (§5.5).

    PYTHONHASHSEED=0 python main_small_demo.py [params_yaml] [results_dir]

Defaults: inputs/workload_params.yaml (§6.2 smoke run) and results.
theta = 0 regression (§5.3):
    PYTHONHASHSEED=0 python main_small_demo.py inputs/workload_params_theta0.yaml results_theta0
"""

import os
import sys

from pyomo.core import Constraint, Model, NonNegativeReals, Var

from ehubx import EhubX, FileGranularity, Gurobi, ObjectiveType

MODEL_DIR = os.path.abspath(os.path.dirname(__file__))
REPO_ROOT = os.path.abspath(os.path.join(MODEL_DIR, os.pardir, os.pardir))
sys.path.insert(0, os.path.join(REPO_ROOT, "scripts"))

import make_workload_profiles  # noqa: E402


# Custom model modification, kept identical to the reference case scripts
def my_modifications(model: Model) -> None:
    model.V_MyVar = Var(domain=NonNegativeReals)

    def _my_con(model):
        return model.V_MyVar == model.V_ImpCostTotal * 1.5

    model.C_MyCon = Constraint(rule=_my_con)


if __name__ == "__main__":
    params_path = sys.argv[1] if len(sys.argv) > 1 else "inputs/workload_params.yaml"
    results_dir = sys.argv[2] if len(sys.argv) > 2 else "results"
    params_path = os.path.join(MODEL_DIR, params_path)

    # Step 0: profiles from the parameter file (spec §4, checks sum alpha = 1)
    summary = make_workload_profiles.run(params_path)
    print(make_workload_profiles.format_summary(summary))

    ehubx = EhubX()
    ehubx.model_dir_path = MODEL_DIR
    ehubx.parse()
    ehubx.build()
    ehubx.modify_model(my_modifications)

    solver = Gurobi()
    solver.set_mip_focus(1)
    solver.set_option_by_key("Method", 0)
    solver.set_mip_gap(0.0)  # spec 05 v3 §5.5
    solver.set_log_file(os.path.join(MODEL_DIR, f"gurobi_{results_dir}.log"))
    ehubx.set_solver(solver)

    ehubx.solve_single_obj(
        obj_type=ObjectiveType.COST,
        file_granularity=FileGranularity.MIN,
        results_dir_path=results_dir,
    )
