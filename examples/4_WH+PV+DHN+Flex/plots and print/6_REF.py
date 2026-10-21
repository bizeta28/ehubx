import pandas as pd
import numpy as np
import os

# Set the scenario folder (modify for other runs)
case_folder = "4_WH+PV+DHN+Flex"
result_file = os.path.join("examples", case_folder, "results_flex", "10_flex", "opt_vars.csv")
output_folder = os.path.join("examples", case_folder, "plots and print", "csv_files")
COP_folder = os.path.join("examples", case_folder, "inputs", "basic", "profiles", "HPCOPprofile.csv")
os.makedirs(output_folder, exist_ok=True)
data = pd.read_csv(result_file, low_memory=False)

# Function to expand and fill missing time series data for given conditions
def expand_and_fill_data(df, ec_value, var_name, tech_value):
    full_range = pd.DataFrame({'S_Time': range(1, 8761)})
    expanded_df = pd.merge(full_range, df, on='S_Time', how='left')
    expanded_df['var_name'] = expanded_df['var_name'].fillna(var_name)
    expanded_df['var_value'] = expanded_df['var_value'].fillna(0)
    expanded_df['S_Stage'] = expanded_df['S_Stage'].fillna('S1')
    expanded_df['S_Hub'] = expanded_df['S_Hub'].fillna('H1')
    expanded_df['S_Ec'] = expanded_df['S_Ec'].fillna(ec_value)
    expanded_df['S_Tech'] = expanded_df['S_Tech'].fillna(tech_value)
    expanded_df.sort_values('S_Time', inplace=True)
    expanded_df.reset_index(drop=True, inplace=True)
    return expanded_df

El_PV = expand_and_fill_data(data[(data['S_Ec'] == 'El') & (data['S_Tech'] == 'PV') & (data['var_name'] == 'V_ConvTechOut')], 'El', 'V_ConvTechOut', 'PV')
El_import = expand_and_fill_data(data[(data['S_Ec'] == 'El') & (data['var_name'] == 'V_Imp')], 'El', 'V_Imp', 'Import')

denominator_el = El_PV['var_value'] + El_import['var_value']
r_PV = np.where(denominator_el != 0, (El_PV['var_value'] / denominator_el), 0)
r_import = np.where(denominator_el != 0, (El_import['var_value'] / denominator_el), 0)

# Renewable share of electricity at each timestep
renewable_share = r_PV * 1.0 + r_import * 0.706

DC_el = expand_and_fill_data(data[(data['S_Ec'] == 'El') & (data['var_name'] == 'V_ConvTechIn') & (data['S_Tech'] == 'DC')], 'El', 'V_ConvTechIn', 'DC')
CS_el = expand_and_fill_data(data[(data['S_Ec'] == 'El') & (data['var_name'] == 'V_ConvTechIn') & (data['S_Tech'] == 'CS_hybrid')], 'El', 'V_ConvTechIn', 'CS_hybrid')

# Apply to total electricity consumption
DC_el_renewable = DC_el['var_value'] * renewable_share
CS_el_renewable = CS_el['var_value'] * renewable_share

# ======================================================
# --- CALCULATING ERF ----------------------------------

REF_df = pd.DataFrame({
    'DC Renewable Electricity Consumption': DC_el_renewable,
    'CS Renewable Electricity Consumption': CS_el_renewable,
    'DC Electricity Consumption': DC_el['var_value'],
    'CS Electricity Consumption': CS_el['var_value']
})

REF_df['REF'] = (REF_df['DC Renewable Electricity Consumption'] + REF_df['CS Renewable Electricity Consumption']) / (REF_df['DC Electricity Consumption'] + REF_df['CS Electricity Consumption'])

REF = os.path.join(output_folder, "REF_values.csv")
REF_df.to_csv(REF, index=False)
print("REF values data saved to:", REF)
print(f"Average REF {np.nanmean(REF_df['REF'])*100:.2f} %")

