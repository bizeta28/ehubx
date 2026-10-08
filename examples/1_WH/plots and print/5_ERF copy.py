import pandas as pd
import numpy as np
import os

# =====================================================
# USER SETTINGS
# =====================================================

case_folder = "1_WH"

base_folder = os.path.join("examples", case_folder)
result_file = os.path.join(base_folder, "results", "opt_vars.csv")
output_folder = os.path.join(base_folder, "plots and print", "csv_files")

os.makedirs(output_folder, exist_ok=True)

# =====================================================
# LOAD DATA
# =====================================================

data = pd.read_csv(result_file, low_memory=False)

HOURS = range(1, 8761)

# =====================================================
# HELPER FUNCTIONS
# =====================================================

def hourly_series(
    df,
    s_ec=None,
    var_name=None,
    s_tech=None,
    fill_value=0.0
):
    """
    Returns aligned hourly series (8760 rows).
    """

    filt = pd.Series(True, index=df.index)

    if s_ec is not None:
        filt &= df["S_Ec"] == s_ec

    if var_name is not None:
        filt &= df["var_name"] == var_name

    if s_tech is not None:
        filt &= df["S_Tech"] == s_tech

    temp = df.loc[filt, ["S_Time", "var_value"]].copy()

    temp = (
        temp.groupby("S_Time", as_index=False)["var_value"]
        .sum()
    )

    full = pd.DataFrame({"S_Time": HOURS})

    temp = full.merge(temp, on="S_Time", how="left")
    temp["var_value"] = temp["var_value"].fillna(fill_value)

    return temp["var_value"].astype(float).reset_index(drop=True)


def safe_divide(num, den):
    """
    Safe division.
    Returns 0 where denominator <= 0.
    """
    return np.where(den > 0, num / den, 0.0)


def annual_ratio(num_series, den_series):
    """
    Correct annual KPI:
    sum(num) / sum(den)
    """
    num = np.sum(num_series)
    den = np.sum(den_series)

    if den <= 0:
        return 0.0

    return num / den


# =====================================================
# ELECTRICITY INPUTS
# =====================================================

dc_el = hourly_series(
    data,
    s_ec="El",
    var_name="V_ConvTechIn",
    s_tech="DC"
)

cs_el = hourly_series(
    data,
    s_ec="El",
    var_name="V_ConvTechIn",
    s_tech="CS_hybrid"
)

total_el = dc_el + cs_el

# =====================================================
# DIRECT RECOVERED OUTPUTS
# =====================================================

ht_direct = hourly_series(
    data,
    s_ec="HT",
    var_name="V_ConvTechOut",
    s_tech="CS_hybrid"
)

air_direct = hourly_series(
    data,
    s_ec="Air",
    var_name="V_ConvTechOut",
    s_tech="CS_hybrid"
)

# =====================================================
# IDEAL ERF
# =====================================================

ideal_output = ht_direct + air_direct

ideal_hourly_erf = safe_divide(ideal_output, total_el)
ideal_annual_erf = annual_ratio(ideal_output, total_el)

ideal_df = pd.DataFrame({
    "DC Electricity": dc_el,
    "CS Electricity": cs_el,
    "Total Electricity": total_el,
    "HT Output": ht_direct,
    "Air Output": air_direct,
    "Useful Output": ideal_output,
    "Hourly ERF": ideal_hourly_erf
})

ideal_path = os.path.join(output_folder, "ERF_values_ideal.csv")
ideal_df.to_csv(ideal_path, index=False)

print("Saved:", ideal_path)
print(f"Ideal Annual ERF = {ideal_annual_erf*100:.2f}%")

# =====================================================
# IMPORT / PRODUCTION SHARES
# =====================================================

air_imp = hourly_series(
    data,
    s_ec="Air",
    var_name="V_Imp"
)

heat_imp = hourly_series(
    data,
    s_ec="HT",
    var_name="V_Imp"
)

air_total_supply = air_imp + air_direct
heat_total_supply = heat_imp + ht_direct

share_air_prod = safe_divide(air_direct, air_total_supply)
share_heat_prod = safe_divide(ht_direct, heat_total_supply)

share_df = pd.DataFrame({
    "Produced Air Share": share_air_prod,
    "Produced Heat Share": share_heat_prod
})

share_path = os.path.join(output_folder, "share_values.csv")
share_df.to_csv(share_path, index=False)

print("Saved:", share_path)

# =====================================================
# MT NETWORK
# =====================================================

hp_aw_in = hourly_series(
    data,
    s_ec="Air",
    var_name="V_ConvTechIn",
    s_tech="HP_AW"
)

he_ww_out = hourly_series(
    data,
    s_ec="MT",
    var_name="V_ConvTechOut",
    s_tech="HE_WW"
)

hp_ww_in = hourly_series(
    data,
    s_ec="MT",
    var_name="V_ConvTechIn",
    s_tech="HP_WW"
)

he_lt_out = hourly_series(
    data,
    s_ec="MT",
    var_name="V_ConvTechOut",
    s_tech="HE_LT"
)

tesmt_in = hourly_series(
    data,
    var_name="V_StorTechInflow",
    s_tech="TESMT"
)

tesmt_out = hourly_series(
    data,
    var_name="V_StorTechOutflow",
    s_tech="TESMT"
)

tesmt_balance = tesmt_out - tesmt_in

# attributed reuse share
mt_generated = (
    hp_aw_in * share_air_prod +
    he_ww_out * share_heat_prod -
    hp_ww_in * share_air_prod -
    he_lt_out * share_air_prod
)

mt_total = (
    hp_aw_in +
    he_ww_out -
    hp_ww_in -
    he_lt_out
)

alpha_mt = safe_divide(mt_generated, mt_total)

# storage attribution only once
mt_storage_reuse = tesmt_balance * alpha_mt

mt_useful = np.maximum(0, mt_generated + mt_storage_reuse)

# =====================================================
# HT NETWORK
# =====================================================

hp_ww_out = hourly_series(
    data,
    s_ec="HT",
    var_name="V_ConvTechOut",
    s_tech="HP_WW"
)

he_ww_in = hourly_series(
    data,
    s_ec="HT",
    var_name="V_ConvTechIn",
    s_tech="HE_WW"
)

tesht_in = hourly_series(
    data,
    var_name="V_StorTechInflow",
    s_tech="TESHT"
)

tesht_out = hourly_series(
    data,
    var_name="V_StorTechOutflow",
    s_tech="TESHT"
)

export_ht = hourly_series(
    data,
    s_ec="HT",
    var_name="V_Exp"
)

tesht_balance = tesht_out - tesht_in

ht_generated = (
    ht_direct +
    hp_ww_out * share_air_prod -
    he_ww_in * share_heat_prod -
    export_ht * share_heat_prod
)

ht_total = (
    ht_direct +
    hp_ww_out -
    he_ww_in -
    export_ht
)

alpha_ht = safe_divide(ht_generated, ht_total)

ht_storage_reuse = tesht_balance * alpha_ht

ht_useful = np.maximum(0, ht_generated + ht_storage_reuse)

# =====================================================
# REAL ERF
# =====================================================

real_output = mt_useful + ht_useful

real_hourly_erf = safe_divide(real_output, total_el)
real_annual_erf = annual_ratio(real_output, total_el)

real_df = pd.DataFrame({
    "DC Electricity": dc_el,
    "CS Electricity": cs_el,
    "Total Electricity": total_el,
    "MT Useful": mt_useful,
    "HT Useful": ht_useful,
    "Total Useful": real_output,
    "Hourly ERF": real_hourly_erf
})

real_path = os.path.join(output_folder, "ERF_values_real.csv")
real_df.to_csv(real_path, index=False)

print("Saved:", real_path)
print(f"Real Annual ERF = {real_annual_erf*100:.2f}%")

# =====================================================
# SUMMARY
# =====================================================

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
        ideal_output.sum(),
        real_output.sum(),
        ideal_annual_erf,
        real_annual_erf
    ]
})

summary_path = os.path.join(output_folder, "ERF_summary.csv")
summary.to_csv(summary_path, index=False)

print("Saved:", summary_path)
print("Done.")
