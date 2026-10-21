import pandas as pd
import numpy as np
import os

# Set the scenario folder (modify for other runs)
case_folder = "4_WH+PV+DHN+Flex"

# Define paths
result_file = os.path.join("examples", case_folder, "results", "opt_vars.csv")
output_folder = os.path.join("examples", case_folder, "plots and print", "csv_files")
os.makedirs(output_folder, exist_ok=True)

# Load data
data = pd.read_csv(result_file, low_memory=False)

# Function to expand and fill missing time series data for given conditions
def expand_and_fill_data(df, ec_value, var_name):
    full_range = pd.DataFrame({'S_Time': range(1, 8761)})
    expanded_df = pd.merge(full_range, df, on='S_Time', how='left')
    expanded_df['var_name'] = expanded_df['var_name'].fillna(var_name)
    expanded_df['var_value'] = expanded_df['var_value'].fillna(0)
    expanded_df['S_Stage'] = expanded_df['S_Stage'].fillna('S1')
    expanded_df['S_Hub'] = expanded_df['S_Hub'].fillna('H1')
    expanded_df['S_Ec'] = expanded_df['S_Ec'].fillna(ec_value)
    expanded_df.sort_values('S_Time', inplace=True)
    expanded_df.reset_index(drop=True, inplace=True)
    return expanded_df

Air_prod = expand_and_fill_data(data[(data['S_Ec'] == 'Air') & (data['S_Tech'] == 'CS_hybrid') & (data['var_name'] == 'V_ConvTechOut')], 'Air', 'V_ConvTechOut')
Heat_prod = expand_and_fill_data(data[(data['S_Ec'] == 'HT') & (data['S_Tech'] == 'CS_hybrid') & (data['var_name'] == 'V_ConvTechOut')], 'HT', 'V_ConvTechOut')
MT_Demand = expand_and_fill_data(data[(data['S_Ec'] == 'MT') & (data['var_name'] == 'V_DemandSupply')], 'MT', 'V_DemandSupply')
HT_Demand = expand_and_fill_data(data[(data['S_Ec'] == 'HT') & (data['var_name'] == 'V_DemandSupply')], 'HT', 'V_DemandSupply')

numerator = Air_prod['var_value'] + Heat_prod['var_value']
denominator = MT_Demand['var_value'] + HT_Demand['var_value']
# Calculate share of produced vs imported air and heat
# Assuming all air and heat is produced in this ideal DOC scenario

DoC_ratio = numerator / denominator.replace({0: np.nan})  # Avoid division by zero, set DoC to NaN where demand is zero
DoC_ideal = np.clip(DoC_ratio, 0, 1)*100  # Cap DoC at 100%
Average_DoC = (DoC_ideal).mean()

DoC_df = pd.DataFrame({
    'Air Produced': Air_prod['var_value'],
    'Heat Produced': Heat_prod['var_value'],
    'MT Demand': MT_Demand['var_value'],
    'HT Demand': HT_Demand['var_value'],
    'DoC Ratio': DoC_ratio,
    'Ideal DoC (%)': DoC_ideal,
    'Average DoC (%)': Average_DoC
})

csv_path = os.path.join(output_folder, "ideal_DOC_values.csv")
DoC_df.to_csv(csv_path, index=False)

print("Values data saved to:", csv_path)
print(f"Average Ideal Degree of Coverage (DoC): {Average_DoC:.2f} %")

# # === Load hourly COP profile (second column, from row 4) ===

# cop_file = os.path.join("examples", case_folder, "inputs", "basic", "profiles", "HPCOPprofile.csv")


# # Read CSV:
# # - skip first 3 rows (so row 4 becomes first data row)
# # - no header assumed
# cop_raw = pd.read_csv(cop_file, skiprows=3, header=None)

# # Select second column (index 1)
# cop_values = cop_raw.iloc[:, 1].reset_index(drop=True)

# # Ensure we have 8760 hourly values
# if len(cop_values) != 8760:
#     raise ValueError(f"COP profile must contain 8760 hourly values, but found {len(cop_values)}")

# # Store as DataFrame with S_Time and var_value
# COP_profile = pd.DataFrame({
#     'S_Time': range(1, 8761),
#     'var_name': 'COP',
#     'var_value': cop_values
# })



# # ---------------------------------------------
# # Calculate share of imported vs produced air
# r_prod = 1
# j_prod = 1

# # ---------------------------------------------
# # --- MT Balance Calculations ---

# HP_AW = expand_and_fill_data(data[(data['S_Ec'] == 'MT') & (data['S_Tech'] == 'HP_AW') & (data['var_name'] == 'V_ConvTechOut')], 'MT', 'V_ConvTechOut')
# HE_WW = expand_and_fill_data(data[(data['S_Ec'] == 'MT') & (data['S_Tech'] == 'HE_WW') & (data['var_name'] == 'V_ConvTechOut')], 'MT', 'V_ConvTechOut')
# HP_WWin = expand_and_fill_data(data[(data['S_Ec'] == 'MT') & (data['S_Tech'] == 'HP_WW') & (data['var_name'] == 'V_HpTechIn')], 'MT', 'V_HpTechIn')
# TESin_MT = expand_and_fill_data(data[(data['S_Tech'] == 'TESMT') & (data['var_name'] == 'V_StorTechInflow')], 'MT', 'V_StorTechInflow')
# TESout_MT = expand_and_fill_data(data[(data['S_Tech'] == 'TESMT') & (data['var_name'] == 'V_StorTechOutflow')], 'MT', 'V_StorTechOutflow')
# MT_Demand = expand_and_fill_data(data[(data['S_Ec'] == 'MT') & (data['var_name'] == 'V_DemandSupply')], 'MT', 'V_DemandSupply')

# TESMT_Balance = TESout_MT['var_value'] - TESin_MT['var_value']

# MT_produced = (HP_AW['var_value']*r_prod +
#                HE_WW['var_value']*j_prod -
#                HP_WWin['var_value']*r_prod +
#                TESMT_Balance* np.minimum(r_prod + j_prod, 1))

# MT_df = pd.DataFrame({
#     'HP_AW Output': HP_AW['var_value'],
#     'HE_WW Output': HE_WW['var_value'],
#     'TES MT Balance' : TESMT_Balance,
#     'MT Demand' : MT_Demand['var_value'],
#     'MT Produced' : MT_produced
# })

# # Compute DOC and store in data frame
# MT_df['MT DoC (%)'] = np.where(MT_df['MT Demand'] != 0,
#                                (MT_df['MT Produced'] / MT_df['MT Demand']) * 100,
#                                np.nan)

# csv_path = os.path.join(output_folder, "MT_values_realDOC.csv")
# MT_df.to_csv(csv_path, index=False)
# print("Values data saved to:", csv_path)

# # ---------------------------------------------
# # --- HT Balance Calculations ---
# CS_hybrid = expand_and_fill_data(data[(data['S_Ec'] == 'HT') & (data['S_Tech'] == 'CS_hybrid') & (data['var_name'] == 'V_ConvTechOut')], 'HT', 'V_ConvTechOut')
# HP_WWout = expand_and_fill_data(data[(data['S_Ec'] == 'HT') & (data['S_Tech'] == 'HP_WW') & (data['var_name'] == 'V_HpTechOut')], 'HT', 'V_HpTechOut')
# HE_WWin = expand_and_fill_data(data[(data['S_Ec'] == 'HT') & (data['S_Tech'] == 'HP_WW') & (data['var_name'] == 'V_HpTechIn')], 'HT', 'V_HpTechIn')
# TESin_HT = expand_and_fill_data(data[(data['S_Tech'] == 'TESHT') & (data['var_name'] == 'V_StorTechInflow')], 'HT', 'V_StorTechInflow')
# TESout_HT = expand_and_fill_data(data[(data['S_Tech'] == 'TESHT') & (data['var_name'] == 'V_StorTechOutflow')], 'HT', 'V_StorTechOutflow')
# Export_HT = expand_and_fill_data(data[(data['S_Ec'] == 'HT') & (data['var_name'] == 'V_Exp')], 'HT', 'V_Exp')
# HT_Demand = expand_and_fill_data(data[(data['S_Ec'] == 'HT') & (data['var_name'] == 'V_DemandSupply')], 'HT', 'V_DemandSupply')

# TESHT_Balance = TESout_HT['var_value'] - TESin_HT['var_value']

# HT_produced = (CS_hybrid['var_value'] +
#                HP_WWout['var_value']*r_prod -
#                HE_WWin['var_value']*j_prod +
#                TESHT_Balance*np.minimum(r_prod + j_prod, 1) -
#                Export_HT['var_value']*j_prod)

# HT_df = pd.DataFrame({
#     'CS_hybrid Output': CS_hybrid['var_value'],
#     'HP_WW Output': HP_WWout['var_value'],
#     'HE_WW Input' : HE_WWin['var_value'],
#     'TES LT Balance' : TESHT_Balance,
#     'HT Demand' : HT_Demand['var_value'],
#     'HT Produced' : HT_produced
# })

# HT_df['HT DoC (%)'] = np.where(HT_df['HT Demand'] != 0,
#                                (HT_df['HT Produced'] / HT_df['HT Demand']) * 100,
#                                np.nan)

# csv_path = os.path.join(output_folder, "HT_values_realDOC.csv")
# HT_df.to_csv(csv_path, index=False)
# print("Values data saved to:", csv_path)

# # --- Combined MT + HT Degree of Coverage ---
# combined_produced = MT_produced + HT_produced
# combined_demand = MT_Demand['var_value'] + HT_Demand['var_value']

# combined_DOC = np.where(
#     combined_produced > combined_demand,
#     100.0,
#     np.where(
#         combined_demand != 0,
#         (combined_produced / combined_demand) * 100,
#         np.nan
#     )
# )

# combined_df = pd.DataFrame({
#     'Combined MT+HT Produced': combined_produced,
#     'Combined MT+HT Demand': combined_demand,
#     'Combined MT+HT DoC (%)': combined_DOC
# })

# csv_path = os.path.join(output_folder, "combined_values_realDOC.csv")
# combined_df.to_csv(csv_path, index=False)
# print("Values data saved to:", csv_path)

# average_DoC_MTHT = np.nanmean(combined_DOC)
# print(f"Average Degree of Coverage (DoC) MT+HT combined: {average_DoC_MTHT:.2f} %")
