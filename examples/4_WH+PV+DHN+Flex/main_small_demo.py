import os

from pyomo.core import Constraint, Model, NonNegativeReals, Var

from ehubx import EhubX, FileGranularity, Gurobi, ObjectiveType


# Function for custom model modifications, used in step 4 of main method
def my_modifications(model: Model) -> None:
    # Add a variable
    model.V_MyVar = Var(domain=NonNegativeReals)

    # Add a constraint
    def _my_con(model):
        return model.V_MyVar == model.V_ImpCostTotal * 1.5

    model.C_MyCon = Constraint(rule=_my_con)


if __name__ == "__main__":
    # Step 0: Create EhubX object and set path
    ehubx = EhubX()
    # Set model path and parse
    ehubx.model_dir_path = os.path.abspath(os.path.dirname(__file__))
    ehubx.parse()
    # Step 2 (optional): Deactivate or reactivate modules
    #ehubx.energy_system.deactivate_solar_techs()
    #ehubx.energy_system.reactivate_solar_techs()
    # Step 3: Build the model. Use optional arguments to specify normalization
    #         and clustering
    ehubx.build()
    # Step 4 (optional): Add custom model modifications
    ehubx.modify_model(my_modifications)
    # Step 5 (optional): Manually set a solver and specify options
    solver = Gurobi()
    solver.set_mip_focus(1)
    solver.set_option_by_key("Method", 0)
    ehubx.set_solver(solver)
    # Step 6: Solve the model.
    ehubx.solve_single_obj(
        obj_type=ObjectiveType.COST, file_granularity=FileGranularity.MIN
    )
    """
    ehubx.solve_double_obj(
    #    obj_type_1=ObjectiveType.COST,
    #    obj_type_2=ObjectiveType.CO2,
    #    num_pareto_points=10,
    )

"""

    # Step 7 (optional): EhubX object can still be used to perform actions,
    #                    e.g.; modifying parameters and rebuilding the model
