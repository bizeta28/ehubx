import pandas as pd
import numpy as np
import os

# Set the scenario folder (modify for other runs)
case_folder = "1_WH"
result_file = os.path.join("examples", case_folder, "results", "opt_vars.csv")
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

CS_HT = expand_and_fill_data(data[(data['S_Ec'] == 'HT') & (data['var_name'] == 'V_ConvTechOut') & (data['S_Tech'] == 'CS_hybrid')], 'HT', 'V_ConvTechOut', 'CS_hybrid')
CS_air = expand_and_fill_data(data[(data['S_Ec'] == 'Air') & (data['var_name'] == 'V_ConvTechOut') & (data['S_Tech'] == 'CS_hybrid')], 'Air', 'V_ConvTechOut', 'CS_hybrid')
DC_el = expand_and_fill_data(data[(data['S_Ec'] == 'El') & (data['var_name'] == 'V_ConvTechIn') & (data['S_Tech'] == 'DC')], 'El', 'V_ConvTechIn', 'DC')
CS_el = expand_and_fill_data(data[(data['S_Ec'] == 'El') & (data['var_name'] == 'V_ConvTechIn') & (data['S_Tech'] == 'CS_hybrid')], 'El', 'V_ConvTechIn', 'CS_hybrid')

# ======================================================
# --- CALCULATING ERF ----------------------------------

ERF_df = pd.DataFrame({
    'DC Electricity Consumption': DC_el['var_value'],
    'CS Electricity Consumption': CS_el['var_value'],
    'Total Produced HT': CS_HT['var_value'],
    'Total Produced Air': CS_air['var_value']
})

ERF_df['ERF'] = (ERF_df['Total Produced HT'] + ERF_df['Total Produced Air']) / (ERF_df['DC Electricity Consumption'] + ERF_df['CS Electricity Consumption'])

ERF_csv_path = os.path.join(output_folder, "ERF_values_ideal.csv")
ERF_df.to_csv(ERF_csv_path, index=False)
print("ERF values data saved to:", ERF_csv_path)
print(f"Ideal ERF {(ERF_df['Total Produced HT'] + ERF_df['Total Produced Air']).sum() / (ERF_df['DC Electricity Consumption'] + ERF_df['CS Electricity Consumption']).sum() * 100:.2f} %")



# ======================================================

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

# Calculate share of imported vs produced air
Air_Imp = expand_and_fill_data(data[(data['S_Ec'] == 'Air') & (data['var_name'] == 'V_Imp')], 'Air', 'V_Imp')
Air_Prod = expand_and_fill_data(data[(data['S_Ec'] == 'Air') & (data['S_Tech'] == 'CS_hybrid') & (data['var_name'] == 'V_ConvTechOut')], 'Air', 'V_ConvTechOut')

denominator_air = Air_Imp['var_value'] + Air_Prod['var_value']
r_prod = np.where(denominator_air != 0, Air_Prod['var_value'] / denominator_air, 0)

# Calculate share of imported vs produced heat
Heat_Imp = expand_and_fill_data(data[(data['S_Ec'] == 'HT') & (data['var_name'] == 'V_Imp')], 'HT', 'V_Imp')
Heat_Prod = expand_and_fill_data(data[(data['S_Ec'] == 'HT') & (data['S_Tech'] == 'CS_hybrid') & (data['var_name'] == 'V_ConvTechOut')], 'HT', 'V_ConvTechOut')

denominator_heat = Heat_Imp['var_value'] + Heat_Prod['var_value']
j_prod = np.where(denominator_heat != 0, Heat_Prod['var_value'] / denominator_heat, 0)

share_df = pd.DataFrame({
    'Share of Produced Air' : r_prod,
    'Share of Produced Heat' : j_prod,
})

csv_path = os.path.join(output_folder, "share_values_ideal.csv")
share_df.to_csv(csv_path, index=False)
print("Values data saved to:", csv_path)

# ---------------------------------------------
# --- MT Balance Calculations ---

HP_AW = expand_and_fill_data(data[(data['S_Ec'] == 'Air') & (data['S_Tech'] == 'HP_AW') & (data['var_name'] == 'V_ConvTechIn')], 'Air', 'V_ConvTechIn')
HE_WW = expand_and_fill_data(data[(data['S_Ec'] == 'MT') & (data['S_Tech'] == 'HE_WW') & (data['var_name'] == 'V_ConvTechOut')], 'MT', 'V_ConvTechOut')
HP_WW = expand_and_fill_data(data[(data['S_Ec'] == 'MT') & (data['S_Tech'] == 'HP_WW') & (data['var_name'] == 'V_ConvTechIn')], 'MT', 'V_ConvTechIn')
HE_LT = expand_and_fill_data(data[(data['S_Ec'] == 'MT') & (data['S_Tech'] == 'HE_LT') & (data['var_name'] == 'V_ConvTechIn')], 'MT', 'V_ConvTechIn')
TESin_MT = expand_and_fill_data(data[(data['S_Tech'] == 'TESMT') & (data['var_name'] == 'V_StorTechInflow')], 'MT', 'V_StorTechInflow')
TESout_MT = expand_and_fill_data(data[(data['S_Tech'] == 'TESMT') & (data['var_name'] == 'V_StorTechOutflow')], 'MT', 'V_StorTechOutflow')
MT_Demand = expand_and_fill_data(data[(data['S_Ec'] == 'MT') & (data['var_name'] == 'V_DemandSupply')], 'MT', 'V_DemandSupply')
TESMT_Balance = TESout_MT['var_value'] - TESin_MT['var_value']

TESMT_Balance = TESout_MT['var_value'] - TESin_MT['var_value']

#Share of produced air multiplied with HP_AW input gives the produced MT from HP_AW from produced air source
HP_AW_fromDC = HP_AW['var_value']*r_prod

# Share of produced heat to HE_WW multiplied with HE_WW output gives the produced MT from HE_WW from produced heat source
HE_WW_fromDC = HE_WW['var_value']*j_prod

# alpha_MT: DC-origin fraction of MT, derived as a weighted average of primary source shares.
# Rearranging the self-consistency equation alpha*(hp_aw+he_ww) = hp_aw*r_prod + he_ww*j_prod
# gives a closed-form solution that is always bounded in [0,1] and requires no iteration.
denom_MT = HP_AW['var_value'] + HE_WW['var_value']
alpha_MT = np.where(denom_MT > 1e-9,
    (HP_AW['var_value'] * r_prod + HE_WW['var_value'] * j_prod) / denom_MT,
    0)

HP_WW_fromDC = HP_WW['var_value'] * alpha_MT
HE_LT_fromDC = HE_LT['var_value'] * alpha_MT

MT_produced = (HP_AW_fromDC +
               HE_WW_fromDC -
               HP_WW_fromDC -
               HE_LT_fromDC)

# Attribute TES contribution using alpha_MT
TESMT_fromDC = TESMT_Balance*alpha_MT
MT_produced += TESMT_fromDC

MT_df = pd.DataFrame({
    'HP_AW from DC': HP_AW_fromDC,
    'HE_WW from DC': HE_WW_fromDC,
    'HP_WW from DC': HP_WW_fromDC,
    'HE_LT from DC': HE_LT_fromDC,
    'TES MT Balance' : TESMT_fromDC,
    'MT Demand' : MT_Demand['var_value'],
    'MT Produced' : MT_produced
})

# ---------------------------------------------
# --- HT Balance Calculations ---
CS_hybrid = expand_and_fill_data(data[(data['S_Ec'] == 'HT') & (data['S_Tech'] == 'CS_hybrid') & (data['var_name'] == 'V_ConvTechOut')], 'HT', 'V_ConvTechOut')
HP_WWout = expand_and_fill_data(data[(data['S_Ec'] == 'HT') & (data['S_Tech'] == 'HP_WW') & (data['var_name'] == 'V_ConvTechOut')], 'HT', 'V_ConvTechOut')
HE_WWin = expand_and_fill_data(data[(data['S_Ec'] == 'HT') & (data['S_Tech'] == 'HE_WW') & (data['var_name'] == 'V_ConvTechIn')], 'HT', 'V_ConvTechIn')
TESin_HT = expand_and_fill_data(data[(data['S_Tech'] == 'TESHT') & (data['var_name'] == 'V_StorTechInflow')], 'HT', 'V_StorTechInflow')
TESout_HT = expand_and_fill_data(data[(data['S_Tech'] == 'TESHT') & (data['var_name'] == 'V_StorTechOutflow')], 'HT', 'V_StorTechOutflow')
Export_HT = expand_and_fill_data(data[(data['S_Ec'] == 'HT') & (data['var_name'] == 'V_Exp')], 'HT', 'V_Exp')
HT_Demand = expand_and_fill_data(data[(data['S_Ec'] == 'HT') & (data['var_name'] == 'V_DemandSupply')], 'HT', 'V_DemandSupply')

TESHT_Balance = TESout_HT['var_value'] - TESin_HT['var_value']

HP_WWout_fromDC = HP_WWout['var_value']*r_prod
HE_WWin_fromDC = HE_WWin['var_value']*j_prod
Export_HT_fromDC = Export_HT['var_value']*j_prod

# Pass 1: exclude TESHT_Balance here; it will be attributed via alpha_HT below
HT_produced = (
    CS_hybrid['var_value'] +
    HP_WWout_fromDC -
    HE_WWin_fromDC -
    Export_HT_fromDC
)

HT_total = (
    CS_hybrid['var_value'] +
    HP_WWout['var_value'] -
    HE_WWin['var_value'] -
    Export_HT['var_value']
)

alpha_HT = np.where(np.abs(HT_total) > 1e-9, HT_produced / HT_total, 0)

# Attribute TES contribution using alpha_HT and add once
TESHT_Balance_fromDC = TESHT_Balance*alpha_HT
HT_produced += TESHT_Balance_fromDC

HT_df = pd.DataFrame({
    'CS_hybrid Output': CS_hybrid['var_value'],
    'HP_WW Output': HP_WWout_fromDC,
    'HE_WW Input' : HE_WWin_fromDC,
    'TES HT Balance' : TESHT_Balance_fromDC,
    'HT Demand' : HT_Demand['var_value'],
    'HT Produced' : HT_produced
})

# ---------------------------------------------
# --- COMBINED MT + HT DoC ---

# Ensure alignment
MT_produced_series = MT_df['MT Produced'].reset_index(drop=True)
HT_produced_series = HT_df['HT Produced'].reset_index(drop=True)

Combined_Produced = MT_produced_series + HT_produced_series

Combined_df = pd.DataFrame({
    'MT Produced': MT_produced_series,
    'HT Produced': HT_produced_series,
    'Total Produced': Combined_Produced,
})



# ======================================================
# --- CALCULATING REAL ERF -----------------------------

ERF_REAL_df = pd.DataFrame({
    'DC Electricity Consumption': DC_el['var_value'],
    'CS Electricity Consumption': CS_el['var_value'],
    'MT Produced': MT_produced_series,
    'HT Produced': HT_produced_series,
})

ERF_REAL_df['ERF'] = (ERF_REAL_df['MT Produced'] + ERF_REAL_df['HT Produced']) / (ERF_REAL_df['DC Electricity Consumption'] + ERF_REAL_df['CS Electricity Consumption'])

ERF_csv_path = os.path.join(output_folder, "ERF_values_real.csv")
ERF_REAL_df.to_csv(ERF_csv_path, index=False)
print("ERF values data saved to:", ERF_csv_path)
print(f"Real ERF {(ERF_REAL_df['MT Produced'] + ERF_REAL_df['HT Produced']).sum() / (ERF_REAL_df['DC Electricity Consumption'] + ERF_REAL_df['CS Electricity Consumption']).sum() * 100:.2f} %")

# ======================================================
# --- ERF SUMMARY --------------------------------------

total_el = ERF_REAL_df['DC Electricity Consumption'] + ERF_REAL_df['CS Electricity Consumption']
ideal_useful = ERF_df['Total Produced HT'] + ERF_df['Total Produced Air']
real_useful = ERF_REAL_df['MT Produced'] + ERF_REAL_df['HT Produced']

ideal_annual_erf = ideal_useful.sum() / total_el.sum() if total_el.sum() > 0 else 0.0
real_annual_erf = real_useful.sum() / total_el.sum() if total_el.sum() > 0 else 0.0

summary = pd.DataFrame({
    "Metric": [
        "Total Electricity Input",
        "Ideal Useful Energy",
        "Real Useful Energy",
        "Ideal ERF",
        "Real ERF"
    ],
    "Value": [
        total_el.sum(),
        ideal_useful.sum(),
        real_useful.sum(),
        ideal_annual_erf,
        real_annual_erf
    ]
})

summary_path = os.path.join(output_folder, "ERF_summary.csv")
summary.to_csv(summary_path, index=False)
print("ERF summary saved to:", summary_path)
