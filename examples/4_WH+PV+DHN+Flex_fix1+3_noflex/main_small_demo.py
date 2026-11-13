"""
No-flex run for spec 05 v3 (docs/semester_project/formulation/05_workload_flexibility.md,
§5.3): the 4_WH+PV+DHN+Flex_fix1+3 case with load shifting removed. Same solver
settings as the reference cases (MIP focus 1, Method 0) plus MIP gap 0 and a
Gurobi log file. Run with PYTHONHASHSEED=0 (§5.5):

    PYTHONHASHSEED=0 python main_small_demo.py [results_dir]
"""

import os
import sys

from pyomo.core import Constraint, Model, NonNegativeReals, Var

from ehubx import EhubX, FileGranularity, Gurobi, ObjectiveType


# Custom model modification, kept identical to the reference case scripts
def my_modifications(model: Model) -> None:
    model.V_MyVar = Var(domain=NonNegativeReals)

    def _my_con(model):
        return model.V_MyVar == model.V_ImpCostTotal * 1.5

    model.C_MyCon = Constraint(rule=_my_con)


if __name__ == "__main__":
    results_dir = sys.argv[1] if len(sys.argv) > 1 else "results"
    model_dir = os.path.abspath(os.path.dirname(__file__))

    ehubx = EhubX()
    ehubx.model_dir_path = model_dir
    ehubx.parse()
    ehubx.build()
    ehubx.modify_model(my_modifications)

    solver = Gurobi()
    solver.set_mip_focus(1)
    solver.set_option_by_key("Method", 0)
    solver.set_mip_gap(0.0)  # spec 05 v3 §5.5
    solver.set_log_file(os.path.join(model_dir, f"gurobi_{results_dir}.log"))
    ehubx.set_solver(solver)

    ehubx.solve_single_obj(
        obj_type=ObjectiveType.COST,
        file_granularity=FileGranularity.MIN,
        results_dir_path=results_dir,
    )
