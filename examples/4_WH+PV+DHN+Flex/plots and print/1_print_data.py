import pandas as pd
import numpy as np
import os
import glob

# --------- Set the scenario folder (modify for other runs) ---------
case_folder = "4_WH+PV+DHN+Flex"

# --------- Define paths ---------
results_folder = os.path.join("examples", case_folder, "results")
no_util_folder = os.path.join("examples", "0_NoUtilisation", "results")  # reference no-util scenario
output_folder = os.path.join("examples", case_folder, "plots and print", "csv_files")
os.makedirs(output_folder, exist_ok=True)

# --------- Helper Functions ---------
def safe_get_value(df, mask, default=0):
    subset = df[mask]
    if subset.empty:
        return default
    # Returns first matching var_value, 0 if index 0 to avoid possible header issues
    idx = subset.index[0]
    return 0 if idx == 0 else subset.iloc[0]['var_value']

def safe_format(value):
    try:
        return f"{value:.2f}"
    except Exception:
        return "N/A"

def load_and_concat_csv_folder(folder):
    files = glob.glob(os.path.join(folder, "*.csv"))
    dfs = [pd.read_csv(f, low_memory=False) for f in files]
    return pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()

# --------- Data Loading ---------
data = load_and_concat_csv_folder(results_folder)
data_no_util = load_and_concat_csv_folder(no_util_folder)

output_lines = []

# --------- Summary Calculations ---------
# Total import cost for system
val_imp_cost_total = safe_get_value(data, data['var_name'] == 'V_ImpCostTotal')
output_lines.append({"Description": "Total import cost for the system", "Value": safe_format(val_imp_cost_total), "Unit": "CHF"})

# Total technology cost
val_tech_cost_total = safe_get_value(data, data['var_name'] == 'V_TechCostTotal')
output_lines.append({"Description": "Total cost of the technologies", "Value": safe_format(val_tech_cost_total), "Unit": "CHF"})

# Detailed import cost (electricity and high temp)
val_imp_cost_el = safe_get_value(data, (data['var_name'] == 'V_ImpCost') & (data['S_Ec'] == 'El'))
val_imp_cost_ht = safe_get_value(data, (data['var_name'] == 'V_ImpCost') & (data['S_Ec'] == 'HT'))
output_lines.append({"Description": "Total import cost for electricity", "Value": safe_format(val_imp_cost_el), "Unit": "CHF"})
output_lines.append({"Description": "Total import cost for high temp", "Value": safe_format(val_imp_cost_ht), "Unit": "CHF"})

# Total system cost
val_system_cost = safe_get_value(data, data['var_name'] == 'V_SystemCost')
output_lines.append({"Description": "Total cost of the system", "Value": safe_format(val_system_cost), "Unit": "CHF"})

# Technologies (tech code, description)
technologies = [
    ('DC', 'data centre'),
    ('HP_WW', 'WW heat pump'),
    ('HE_WW', 'WW heat exchanger'),
    ('HP_AW', 'AW heat pump'),
    ('HE_AW', 'AW heat exchanger'),
    ('Chiller', 'Chiller'),
    ('HE_LT', 'LT heat exchanger'),
    ('HE_Air', 'Air heat exchanger'),
    ('BES', 'battery energy storage'),
    ('PV', 'solar panel'),
    ('CS_air', 'air cooling system'),
    ('CS_hybrid', 'hybrid cooling system'),
    ('CS_liquid', 'liquid cooling system'),
    ('TESHT', 'high storage'),
    ('TESMT', 'medium storage'),
    ('TESLT', 'low storage'),
]

# Installed capacities (kW)
for tech, desc in technologies:
    val = safe_get_value(data, (data['var_name'] == 'V_TechCap') & (data['S_Tech'] == tech))
    output_lines.append({"Description": f"Maximum installed capacity of the {desc}", "Value": safe_format(val), "Unit": "kW"})

# CAPEX costs (CHF)
for tech, desc in technologies:
    val = safe_get_value(data, (data['var_name'] == 'V_TechCostCapex') & (data['S_Tech'] == tech))
    output_lines.append({"Description": f"Total capex cost of the {desc}", "Value": safe_format(val), "Unit": "CHF"})

# OPEX costs (CHF)
for tech, desc in technologies:
    val = safe_get_value(data, (data['var_name'] == 'V_TechCostOpexCap') & (data['S_Tech'] == tech))
    output_lines.append({"Description": f"Total opex cost of the {desc}", "Value": safe_format(val), "Unit": "CHF"})

# --------- Save Summary ---------
df_output = pd.DataFrame(output_lines)
output_csv_path = os.path.join(output_folder, "summary_outputs.csv")
df_output.to_csv(output_csv_path, index=False)
print(f"Summary outputs saved to {output_csv_path}")

print("The Total Annualised Cost (TAC) of the system is:", safe_format(val_system_cost), "CHF")
# --------- Optional CO2 Data (Commented) ---------
"""
# Uncomment to include CO2 emissions summaries

val_imp_co2_total = safe_get_value(data, data['var_name'] == 'V_ImpCo2Total')
output_lines.append({"Description": "Total imported CO2", "Value": safe_format(val_imp_co2_total), "Unit": "kg"})

for tech, desc in technologies:
    val = safe_get_value(data, (data['var_name'] == 'V_TechCo2Instl') & (data['S_Tech'] == tech))
    output_lines.append({"Description": f"CO2 associated with {desc} installation", "Value": safe_format(val), "Unit": "kg"})

val_tech_co2_total = safe_get_value(data, data['var_name'] == 'V_TechCo2Total')
output_lines.append({"Description": "Total CO2 associated with installed technologies", "Value": safe_format(val_tech_co2_total), "Unit": "kg"})

val_system_co2 = safe_get_value(data, data['var_name'] == 'V_SystemCo2')
output_lines.append({"Description": "Total CO2 in the system", "Value": safe_format(val_system_co2), "Unit": "kg"})
"""
