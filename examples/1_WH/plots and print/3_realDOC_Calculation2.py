import pandas as pd
import numpy as np
import os

# =====================================================
# USER SETTINGS
# =====================================================

case_folder = "2_WH+PV"

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
    Returns aligned hourly series (8760 rows)
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
    return np.where(den > 0, num / den, 0.0)


def covered_energy(produced, demand):
    return np.minimum(np.maximum(produced, 0), np.maximum(demand, 0))


def annual_doc(produced, demand):
    covered = covered_energy(produced, demand).sum()
    total_demand = np.maximum(demand, 0).sum()

    if total_demand <= 0:
        return 0.0

    return 100 * covered / total_demand


# =====================================================
# SOURCE SHARES
# =====================================================

air_imp = hourly_series(data, s_ec="Air", var_name="V_Imp")
air_prod = hourly_series(
    data,
    s_ec="Air",
    var_name="V_ConvTechOut",
    s_tech="CS_hybrid"
)

ht_imp = hourly_series(data, s_ec="HT", var_name="V_Imp")
ht_prod = hourly_series(
    data,
    s_ec="HT",
    var_name="V_ConvTechOut",
    s_tech="CS_hybrid"
)

share_air = safe_divide(
    air_prod,
    air_prod + air_imp
)

share_ht = safe_divide(
    ht_prod,
    ht_prod + ht_imp
)

share_df = pd.DataFrame({
    "Produced Air Share": share_air,
    "Produced HT Share": share_ht
})

share_path = os.path.join(output_folder, "DoC_source_shares.csv")
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

mt_demand = hourly_series(
    data,
    s_ec="MT",
    var_name="V_DemandSupply"
)

tesmt_balance = tesmt_out - tesmt_in

# recovered MT production
mt_direct = (
    hp_aw_in * share_air +
    he_ww_out * share_ht -
    hp_ww_in * share_air -
    he_lt_out * share_air
)

mt_total = (
    hp_aw_in +
    he_ww_out -
    hp_ww_in -
    he_lt_out
)

alpha_mt = safe_divide(mt_direct, mt_total)

mt_storage = tesmt_balance * alpha_mt

mt_produced = np.maximum(0, mt_direct + mt_storage)

mt_covered = covered_energy(mt_produced, mt_demand)

mt_hourly_doc = safe_divide(mt_covered, mt_demand) * 100
mt_annual_doc = annual_doc(mt_produced, mt_demand)

mt_df = pd.DataFrame({
    "MT Produced": mt_produced,
    "MT Demand": mt_demand,
    "MT Covered": mt_covered,
    "MT DoC (%)": mt_hourly_doc
})

mt_path = os.path.join(output_folder, "MT_DoC.csv")
mt_df.to_csv(mt_path, index=False)

print("Saved:", mt_path)
print(f"Annual MT DoC = {mt_annual_doc:.2f}%")

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

ht_demand = hourly_series(
    data,
    s_ec="HT",
    var_name="V_DemandSupply"
)

tesht_balance = tesht_out - tesht_in

ht_direct_supply = (
    ht_prod +
    hp_ww_out * share_air -
    he_ww_in * share_ht -
    export_ht * share_ht
)

ht_total_supply = (
    ht_prod +
    hp_ww_out -
    he_ww_in -
    export_ht
)

alpha_ht = safe_divide(ht_direct_supply, ht_total_supply)

ht_storage = tesht_balance * alpha_ht

ht_produced = np.maximum(0, ht_direct_supply + ht_storage)

ht_covered = covered_energy(ht_produced, ht_demand)

ht_hourly_doc = safe_divide(ht_covered, ht_demand) * 100
ht_annual_doc = annual_doc(ht_produced, ht_demand)

ht_df = pd.DataFrame({
    "HT Produced": ht_produced,
    "HT Demand": ht_demand,
    "HT Covered": ht_covered,
    "HT DoC (%)": ht_hourly_doc
})

ht_path = os.path.join(output_folder, "HT_DoC.csv")
ht_df.to_csv(ht_path, index=False)

print("Saved:", ht_path)
print(f"Annual HT DoC = {ht_annual_doc:.2f}%")

# =====================================================
# COMBINED MT + HT
# =====================================================

combined_produced = mt_produced + ht_produced
combined_demand = mt_demand + ht_demand

combined_covered = covered_energy(
    combined_produced,
    combined_demand
)

combined_hourly_doc = (
    safe_divide(combined_covered, combined_demand) * 100
)

combined_annual_doc = annual_doc(
    combined_produced,
    combined_demand
)

combined_df = pd.DataFrame({
    "MT Produced": mt_produced,
    "HT Produced": ht_produced,
    "Total Produced": combined_produced,
    "MT Demand": mt_demand,
    "HT Demand": ht_demand,
    "Total Demand": combined_demand,
    "Covered Demand": combined_covered,
    "Combined DoC (%)": combined_hourly_doc
})

combined_path = os.path.join(
    output_folder,
    "Combined_MT_HT_DoC.csv"
)

combined_df.to_csv(combined_path, index=False)

print("Saved:", combined_path)
print(f"Annual Combined DoC = {combined_annual_doc:.2f}%")

# =====================================================
# SUMMARY
# =====================================================

summary = pd.DataFrame({
    "Metric": [
        "Annual MT DoC (%)",
        "Annual HT DoC (%)",
        "Annual Combined DoC (%)",
        "Total MT Demand",
        "Total HT Demand",
        "Total Combined Demand"
    ],
    "Value": [
        mt_annual_doc,
        ht_annual_doc,
        combined_annual_doc,
        mt_demand.sum(),
        ht_demand.sum(),
        combined_demand.sum()
    ]
})

summary_path = os.path.join(
    output_folder,
    "DoC_summary.csv"
)

summary.to_csv(summary_path, index=False)

print("Saved:", summary_path)
print("Done.")
