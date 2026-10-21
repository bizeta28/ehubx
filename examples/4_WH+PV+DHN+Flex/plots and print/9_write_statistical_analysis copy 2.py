
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import os
import matplotlib.dates as mdates


# Set the scenario folder (modify for new runs)
case_folder = "4_WH+PV+DHN+Flex"

# --- USER OPTIONS ---
# Set one of these to a value to plot a specific period. Leave others as None.
plot_day = None      # 1-365 (e.g., 15 for Jan 15)
plot_month = None    # 1-12 (e.g., 1 for Jan, 12 for Dec)
plot_week = None     # 1-52 (e.g., 5 for week 5)

# Paths
result_file = os.path.join("examples", case_folder, "results", "opt_vars.csv")
output_folder = os.path.join("examples", case_folder, "plots and print", "plots", "other plots")
csv_folder = os.path.join("examples", case_folder, "plots and print", "csv_files", "statistical_analysis")
os.makedirs(output_folder, exist_ok=True)
os.makedirs(csv_folder, exist_ok=True)

# Load data
data = pd.read_csv(result_file, low_memory=False)

# Function to expand and fill time series data
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

IT_Profile = expand_and_fill_data(data[(data['S_Ec'] == 'IT') & (data['var_name'] == 'V_DemandSupply')], 'IT', 'V_DemandSupply')
Load_shifting = expand_and_fill_data(data[(data['S_Ec'] == 'IT') & (data['var_name'] == 'V_LoadShifting')], 'IT', 'V_LoadShifting')
Load_shifting_above = expand_and_fill_data(data[(data['S_Ec'] == 'IT') & (data['var_name'] == 'V_LoadShiftingAbove')], 'IT', 'V_LoadShiftingAbove')
Load_shifting_below = expand_and_fill_data(data[(data['S_Ec'] == 'IT') & (data['var_name'] == 'V_LoadShiftingBelow')], 'IT', 'V_LoadShiftingBelow')

Load_shifting_forplot = IT_Profile['var_value']+Load_shifting['var_value']

time_index = pd.date_range(start='2023-01-01', periods=8760, freq='h')

# --- PERIOD SELECTION LOGIC ---
def get_period_indices():
    if plot_day is not None:
        start = (plot_day - 1) * 24
        end = start + 24
        label = f"Day_{plot_day}"
        return slice(start, end), label
    elif plot_month is not None:
        month_starts = pd.date_range('2023-01-01', periods=12, freq='MS')
        month_ends = pd.date_range('2023-01-01', periods=12, freq='ME')
        start = (month_starts[plot_month-1] - time_index[0]).days * 24
        end = (month_ends[plot_month-1] - time_index[0]).days * 24 + 24
        label = month_starts[plot_month-1].strftime('%B')
        return slice(start, end), label
    elif plot_week is not None:
        start = (plot_week - 1) * 168
        end = start + 168
        label = f"Week_{plot_week}"
        return slice(start, end), label
    else:
        return slice(0, 8760), "Full_Year"

period_slice, period_label = get_period_indices()

# ======================================================
# ---------------- CORRELATION ANALYSIS ----------------
# ======================================================

import statsmodels.api as sm
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.model_selection import cross_val_score


def ols_coef_table(model, label):
    """Tidy coefficient table (for CSV export) from a fitted statsmodels OLS model."""
    table = model.summary2().tables[1].reset_index().rename(columns={"index": "term"})
    table.insert(0, "model", label)
    table.insert(1, "r_squared", model.rsquared)
    table.insert(2, "adj_r_squared", model.rsquared_adj)
    return table


def run_correlation_analysis(plot_day=None, plot_week=None, plot_month=None):

    print("\n==============================")
    print("RUNNING CORRELATION ANALYSIS")
    print(f"All detailed output saved to: {csv_folder}")
    print("==============================")

    # --------------------------------------------
    # 1) Load MT demand, electricity price, and the flexibility variable
    # --------------------------------------------
    profiles_folder = os.path.join("examples", case_folder, "inputs", "basic", "profiles")
    demands_path = os.path.join(profiles_folder, "demands.csv")
    imports_path = os.path.join(profiles_folder, "imports.csv")

    demand_columns = ['S_Time', 'HT', 'MT', 'LT', 'IT', 'El']
    demands_df = pd.read_csv(demands_path, skiprows=4, header=None, names=demand_columns)
    MT_demand = demands_df['MT'].values[:8760]

    imports_columns = ['S_Time', 'price', 'co2']
    imports_df = pd.read_csv(imports_path, skiprows=5, header=None, names=imports_columns)
    price = imports_df['price'].values[:8760]

    flexibility = Load_shifting['var_value'].values[:8760]
    flexibility_above = Load_shifting_above['var_value'].values[:8760]
    flexibility_below = Load_shifting_below['var_value'].values[:8760]

    # --------------------------------------------
    # 1b) Additional drivers: PV output/curtailment, TESLT/BES state,
    # HP_AW COP, DHN export volume
    # --------------------------------------------
    pv_out = expand_and_fill_data(
        data[(data['S_Ec'] == 'El') & (data['S_Tech'] == 'PV') & (data['var_name'] == 'V_ConvTechOut')],
        'El', 'V_ConvTechOut'
    )['var_value'].values[:8760]

    # V_StorTechEnergy is indexed on S_TimeHorizon, not S_Time - reindex directly
    tes_lt_raw = data[(data['S_Tech'] == 'TESLT') & (data['var_name'] == 'V_StorTechEnergy')]
    tes_lt_series = tes_lt_raw.set_index('S_TimeHorizon')['var_value'].reindex(range(1, 8761)).ffill().bfill()
    tes_lt = tes_lt_series.values

    # BES state of charge - same S_TimeHorizon indexing as TESLT
    bes_raw = data[(data['S_Tech'] == 'BES') & (data['var_name'] == 'V_StorTechEnergy')]
    bes_series = bes_raw.set_index('S_TimeHorizon')['var_value'].reindex(range(1, 8761)).ffill().bfill()
    bes_soc = bes_series.values

    # PV curtailment: incident solar potential minus what's actually converted
    pv_incident = expand_and_fill_data(
        data[(data['S_Tech'] == 'PV') & (data['var_name'] == 'V_SolarTechIncident')],
        'Solar', 'V_SolarTechIncident'
    )['var_value'].values[:8760]
    pv_used = expand_and_fill_data(
        data[(data['S_Ec'] == 'Solar') & (data['S_Tech'] == 'PV') & (data['var_name'] == 'V_ConvTechIn')],
        'Solar', 'V_ConvTechIn'
    )['var_value'].values[:8760]
    pv_curtailment = np.clip(pv_incident - pv_used, a_min=0, a_max=None)

    # DHN export volume (HT exported to the district heating network)
    dhn_export = expand_and_fill_data(
        data[(data['S_Ec'] == 'HT') & (data['var_name'] == 'V_Exp')],
        'HT', 'V_Exp'
    )['var_value'].values[:8760]

    hp_cop_path = os.path.join(profiles_folder, "HPCOPprofile.csv")
    hp_cop_df = pd.read_csv(hp_cop_path, skiprows=3, header=None,
                             names=['S_Time', 'HP_AW_COP', 'HP_WW_COP'])
    hp_aw_cop = hp_cop_df['HP_AW_COP'].values[:8760]

    # Daily price rank (0-1 percentile within each day) to capture the
    # daily-relative signal that the 24h load-shifting neutrality window
    # actually responds to, rather than the absolute price level
    price_daily_rank = (
        pd.Series(price)
        .groupby(np.arange(8760) // 24)
        .rank(pct=True)
        .values
    )

    # --------------------------------------------
    # 1c) Hourly shift envelope (the capacity ceiling), from the
    # load_shift_id used in demands.yaml ("ls3")
    # --------------------------------------------
    loadshift_path = os.path.join(profiles_folder, "loadshifting_profiles.csv")
    loadshift_raw = pd.read_csv(loadshift_path, header=None, skiprows=3)
    env_above = loadshift_raw[4].values[:8760].astype(float)
    env_below = loadshift_raw[5].values[:8760].astype(float)

    time_index = pd.date_range(start='2023-01-01', periods=8760, freq='h')

    # --------------------------------------------
    # 2) Period selection (reuse logic)
    # --------------------------------------------
    def get_period():
        if plot_day is not None:
            start = (plot_day - 1) * 24
            end = start + 24
        elif plot_month is not None:
            month_starts = pd.date_range('2023-01-01', periods=12, freq='MS')
            month_ends = pd.date_range('2023-01-01', periods=12, freq='ME')
            start = (month_starts[plot_month-1] - time_index[0]).days * 24
            end = (month_ends[plot_month-1] - time_index[0]).days * 24 + 24
        elif plot_week is not None:
            start = (plot_week - 1) * 168
            end = start + 168
        else:
            start = 0
            end = 8760
        return slice(start, end)

    period_slice = get_period()

    # --------------------------------------------
    # 3) Build analysis dataframe
    # --------------------------------------------
    df = pd.DataFrame({
        "flexibility": flexibility[period_slice],
        "flexibility_above": flexibility_above[period_slice],
        "flexibility_below": flexibility_below[period_slice],
        "price": price[period_slice],
        "heat_demand": MT_demand[period_slice],
        "pv_out": pv_out[period_slice],
        "tes_lt": tes_lt[period_slice],
        "hp_aw_cop": hp_aw_cop[period_slice],
        "price_daily_rank": price_daily_rank[period_slice],
        "env_above": env_above[period_slice],
        "env_below": env_below[period_slice],
        "bes_soc": bes_soc[period_slice],
        "pv_curtailment": pv_curtailment[period_slice],
        "dhn_export": dhn_export[period_slice],
    }).dropna()

    # Utilization ratios: how much of the available shift capacity was used.
    # Bounded in [0, 1] and should be more linearly explainable than the raw
    # kW magnitude, since it removes the hour-to-hour ceiling effect.
    df["util_above"] = np.where(df["env_above"] > 1e-9, df["flexibility_above"] / df["env_above"], 0.0)
    df["util_below"] = np.where(df["env_below"] > 1e-9, df["flexibility_below"] / df["env_below"], 0.0)

    # --------------------------------------------
    # 3b) Raw hourly dataset export - all variables used in the analysis,
    # one row per hour, so correlation/regression can be reproduced or
    # extended manually (e.g. in Excel or R) without rerunning this script.
    # --------------------------------------------
    raw_export = df.copy()
    raw_export.insert(0, "datetime", time_index[period_slice])
    raw_export.insert(1, "hour_of_year", np.arange(1, len(raw_export) + 1))
    raw_export.to_csv(os.path.join(csv_folder, "raw_hourly_dataset.csv"), index=False)

    # --------------------------------------------
    # 4) Correlation matrices -> CSV only (large, not console-friendly)
    # --------------------------------------------
    df.corr(method="pearson").to_csv(os.path.join(csv_folder, "correlation_pearson_full.csv"))
    df.corr(method="spearman").to_csv(os.path.join(csv_folder, "correlation_spearman_full.csv"))

    # --------------------------------------------
    # 4b) Shift-up vs shift-down correlation table against system drivers
    # --------------------------------------------
    # Splitting into above/below avoids the sign cancellation that happens
    # when correlating these drivers against the combined signed
    # flexibility variable (shift-up and shift-down can have opposite-sign
    # relationships that wash each other out in a single correlation).
    driver_vars = ["heat_demand", "pv_out", "bes_soc", "dhn_export"]
    shift_vars = ["flexibility_above", "flexibility_below"]

    rows = []
    for driver in driver_vars:
        for shift in shift_vars:
            pearson_r = df[shift].corr(df[driver], method="pearson")
            spearman_rho = df[shift].corr(df[driver], method="spearman")
            rows.append({
                "driver": driver,
                "shift_direction": shift,
                "pearson_r": pearson_r,
                "pearson_r2": pearson_r ** 2,
                "spearman_rho": spearman_rho,
            })
    shift_corr_table = pd.DataFrame(rows)
    shift_corr_table.to_csv(os.path.join(csv_folder, "shift_up_down_correlation_table.csv"), index=False)

    # --------------------------------------------
    # 5) Lagged correlation (+/-24h) -> CSV + plot, console gets only the peak
    # --------------------------------------------
    lag_range = range(-24, 25)
    lag_results = []
    for lag in lag_range:
        corr = df["flexibility"].corr(df["price"].shift(lag))
        lag_results.append((lag, corr))

    lag_df = pd.DataFrame(lag_results, columns=["lag_hours", "correlation"])
    lag_df.to_csv(os.path.join(csv_folder, "lagged_correlation_price.csv"), index=False)
    best_lag = lag_df.iloc[lag_df["correlation"].abs().idxmax()]

    plt.figure(figsize=(8, 5))
    plt.plot(lag_df["lag_hours"], lag_df["correlation"])
    plt.axvline(0, linestyle="--")
    plt.xlabel("Lag (hours)")
    plt.ylabel("Correlation")
    plt.title("Lagged Correlation: Flexibility vs Price")
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(os.path.join(output_folder, "lagged_correlation_price.png"))
    plt.close()

    # --------------------------------------------
    # 6) Standardization (for regression robustness)
    # --------------------------------------------
    # Only scale continuous numeric columns; util_above/below and the
    # occurs-flags used later are left on their natural [0,1]/{0,1} scale.
    scale_cols = ["flexibility", "flexibility_above", "flexibility_below",
                  "price", "heat_demand", "pv_out", "tes_lt", "hp_aw_cop",
                  "price_daily_rank", "env_above", "env_below",
                  "bes_soc", "pv_curtailment", "dhn_export"]
    scaler = StandardScaler()
    df_scaled = pd.DataFrame(
        scaler.fit_transform(df[scale_cols]),
        columns=scale_cols
    )
    df_scaled["util_above"] = df["util_above"].values
    df_scaled["util_below"] = df["util_below"].values

    # Interaction terms: driver x envelope, to capture "same incentive,
    # different ceiling" rather than assuming a purely additive relationship
    df_scaled["price_daily_rank_x_env_above"] = df_scaled["price_daily_rank"] * df_scaled["env_above"]
    df_scaled["pv_out_x_env_above"] = df_scaled["pv_out"] * df_scaled["env_above"]
    df_scaled["price_daily_rank_x_env_below"] = df_scaled["price_daily_rank"] * df_scaled["env_below"]
    df_scaled["pv_out_x_env_below"] = df_scaled["pv_out"] * df_scaled["env_below"]

    # Collect full regression coefficient tables here, write once at the end
    all_model_tables = []

    # --------------------------------------------
    # 7) Baseline regression: price + heat_demand only
    # --------------------------------------------
    X = sm.add_constant(df_scaled[["price", "heat_demand"]])
    y = df_scaled["flexibility"]
    model_baseline = sm.OLS(y, X).fit()
    all_model_tables.append(ols_coef_table(model_baseline, "baseline_price_heatdemand"))

    # --------------------------------------------
    # 7b) Extended regression with additional drivers + envelope
    # --------------------------------------------
    base_features = ["price", "heat_demand", "pv_out", "tes_lt", "hp_aw_cop", "price_daily_rank",
                      "bes_soc", "pv_curtailment", "dhn_export"]
    env_features = base_features + ["env_above", "env_below"]

    X_ext = sm.add_constant(df_scaled[env_features])
    y_ext = df_scaled["flexibility"]
    model_ext = sm.OLS(y_ext, X_ext).fit()
    all_model_tables.append(ols_coef_table(model_ext, "extended_all_drivers_envelope"))

    # --------------------------------------------
    # 7c) Separate regressions for the above/below components,
    # with driver x envelope interaction terms
    # --------------------------------------------
    above_features = base_features + ["env_above", "price_daily_rank_x_env_above", "pv_out_x_env_above"]
    below_features = base_features + ["env_below", "price_daily_rank_x_env_below", "pv_out_x_env_below"]

    component_r2 = {}
    for component, feats in [("flexibility_above", above_features), ("flexibility_below", below_features)]:
        X_comp = sm.add_constant(df_scaled[feats])
        y_comp = df_scaled[component]
        model_comp = sm.OLS(y_comp, X_comp).fit()
        all_model_tables.append(ols_coef_table(model_comp, f"{component}_envelope_interactions"))
        component_r2[component] = model_comp.rsquared

    # --------------------------------------------
    # 7d) Utilization-ratio regression (flexibility normalized by its
    # hourly capacity ceiling)
    # --------------------------------------------
    util_r2 = {}
    for component in ["util_above", "util_below"]:
        X_util = sm.add_constant(df_scaled[base_features])
        y_util = df_scaled[component]
        model_util = sm.OLS(y_util, X_util).fit()
        all_model_tables.append(ols_coef_table(model_util, f"{component}_utilization_ratio"))
        util_r2[component] = model_util.rsquared

    # --------------------------------------------
    # 7e) Two-stage (Heckman-style) model for the above/below components:
    # Stage A - logistic regression on whether shifting occurs at all
    #           (captures the binary V_YLoadShifting gate / threshold effect)
    # Stage B - OLS on magnitude, conditional on shifting occurring
    # --------------------------------------------
    two_stage_results = {}
    for raw_component, comp_label in [("flexibility_above", "above"), ("flexibility_below", "below")]:
        occurs = (df[raw_component].values[: len(df_scaled)] > 1e-9).astype(int)
        X_stage = df_scaled[base_features].values

        logit = LogisticRegression(max_iter=1000)
        logit.fit(X_stage, occurs)
        auc = roc_auc_score(occurs, logit.predict_proba(X_stage)[:, 1])

        mask = occurs == 1
        X_b = sm.add_constant(df_scaled.loc[mask, base_features])
        y_b = df_scaled.loc[mask, raw_component]
        model_b = sm.OLS(y_b, X_b).fit()
        all_model_tables.append(ols_coef_table(model_b, f"{raw_component}_stageB_magnitude_given_occurs"))

        two_stage_results[comp_label] = {
            "share_nonzero": occurs.mean(),
            "stageA_auc": auc,
            "stageB_r2": model_b.rsquared,
        }

    # --------------------------------------------
    # 7e-2) Per-driver summary table matching the four analysis stages:
    # shift-up vs driver, shift-down vs driver, did-it-happen (AUC/pseudo-R2),
    # and how-much-given-it-happened (R2), for each driver individually.
    # --------------------------------------------
    summary_drivers = ["price", "heat_demand", "pv_out", "bes_soc", "dhn_export"]
    summary_rows = []

    for driver in summary_drivers:
        for raw_component, comp_label in [("flexibility_above", "up"), ("flexibility_below", "down")]:
            pearson_r = df[raw_component].corr(df[driver], method="pearson")
            spearman_rho = df[raw_component].corr(df[driver], method="spearman")
            summary_rows.append({
                "question": f"Shift {comp_label} vs {driver}",
                "pearson_r": pearson_r,
                "pearson_r2": pearson_r ** 2,
                "spearman_rho": spearman_rho,
                "auc": np.nan,
                "note": "continuous, normal R2",
            })

            occurs = (df[raw_component].values[: len(df_scaled)] > 1e-9).astype(int)
            pb_r = pd.Series(occurs).corr(df_scaled[driver], method="pearson")
            X_occ = sm.add_constant(df_scaled[[driver]])
            logit_sm = sm.Logit(occurs, X_occ).fit(disp=0)
            mcfadden_pseudo_r2 = logit_sm.prsquared
            X_stage = df_scaled[[driver]].values
            logit_sk = LogisticRegression(max_iter=1000)
            logit_sk.fit(X_stage, occurs)
            auc = roc_auc_score(occurs, logit_sk.predict_proba(X_stage)[:, 1])
            summary_rows.append({
                "question": f"Did shift {comp_label} happen vs {driver}",
                "pearson_r": pb_r,
                "pearson_r2": pb_r ** 2,
                "spearman_rho": pd.Series(occurs).corr(df_scaled[driver], method="spearman"),
                "auc": auc,
                "note": f"binary, McFadden pseudo-R2={mcfadden_pseudo_r2:.3f}",
            })

            mask = occurs == 1
            if mask.sum() > 2:
                sub_r = df.loc[mask, raw_component].corr(df.loc[mask, driver], method="pearson")
                sub_rho = df.loc[mask, raw_component].corr(df.loc[mask, driver], method="spearman")
            else:
                sub_r, sub_rho = np.nan, np.nan
            summary_rows.append({
                "question": f"Magnitude {comp_label} | occurs vs {driver}",
                "pearson_r": sub_r,
                "pearson_r2": sub_r ** 2 if pd.notna(sub_r) else np.nan,
                "spearman_rho": sub_rho,
                "auc": np.nan,
                "note": "continuous subset, normal R2",
            })

    summary_table = pd.DataFrame(summary_rows)
    summary_table.to_csv(os.path.join(csv_folder, "driver_summary_table.csv"), index=False)

    # --------------------------------------------
    # 7f) Tree-based diagnostic: ceiling R^2 and feature importance
    # --------------------------------------------
    gbr_results = {}
    importance_rows = []
    for component in ["flexibility_above", "flexibility_below"]:
        X_gb = df_scaled[base_features + ["env_above", "env_below"]]
        y_gb = df_scaled[component]

        gbr = GradientBoostingRegressor(random_state=0)
        cv_r2 = cross_val_score(gbr, X_gb, y_gb, cv=5, scoring="r2")
        gbr.fit(X_gb, y_gb)
        gbr_results[component] = {"cv_r2_mean": cv_r2.mean(), "cv_r2_std": cv_r2.std()}

        for name, imp in zip(X_gb.columns, gbr.feature_importances_):
            importance_rows.append({"component": component, "feature": name, "importance": imp})

    importance_df = pd.DataFrame(importance_rows).sort_values(["component", "importance"], ascending=[True, False])
    importance_df.to_csv(os.path.join(csv_folder, "gradient_boosting_feature_importance.csv"), index=False)

    # --------------------------------------------
    # 8) Weekday vs Weekend / high-price vs normal-price correlation -> CSV only
    # --------------------------------------------
    df["datetime"] = time_index[period_slice]
    df["weekday"] = df["datetime"].dt.weekday
    df["is_weekend"] = df["weekday"] >= 5

    df[df["is_weekend"]].corr(numeric_only=True).to_csv(os.path.join(csv_folder, "correlation_weekend.csv"))
    df[~df["is_weekend"]].corr(numeric_only=True).to_csv(os.path.join(csv_folder, "correlation_weekday.csv"))

    threshold = df["price"].quantile(0.9)
    df["high_price"] = df["price"] > threshold
    df[df["high_price"]].corr(numeric_only=True).to_csv(os.path.join(csv_folder, "correlation_high_price.csv"))
    df[~df["high_price"]].corr(numeric_only=True).to_csv(os.path.join(csv_folder, "correlation_normal_price.csv"))

    # --------------------------------------------
    # Write all regression coefficient tables to a single CSV
    # --------------------------------------------
    pd.concat(all_model_tables, ignore_index=True).to_csv(
        os.path.join(csv_folder, "regression_models_full.csv"), index=False
    )

    # ==============================================================
    # CONSOLE SUMMARY - short, curated, easy to read at a glance
    # ==============================================================
    print("\n--- Headline R-squared progression (combined flexibility variable) ---")
    print(f"  Baseline (price + heat_demand):        R2 = {model_baseline.rsquared:.3f}")
    print(f"  Extended (+ all drivers + envelope):    R2 = {model_ext.rsquared:.3f}")

    print("\n--- Shift-up / shift-down regressions (+ envelope, interactions) ---")
    for component, r2 in component_r2.items():
        print(f"  {component:20s} R2 = {r2:.3f}")

    print("\n--- Utilization ratio regressions (flexibility / hourly capacity) ---")
    for component, r2 in util_r2.items():
        print(f"  {component:20s} R2 = {r2:.3f}")

    print("\n--- Two-stage model: does shifting happen (AUC) vs how much (R2) ---")
    for comp_label, res in two_stage_results.items():
        print(f"  {comp_label:6s} | nonzero hours: {res['share_nonzero']:.1%} | "
              f"Stage A AUC = {res['stageA_auc']:.3f} | Stage B R2 = {res['stageB_r2']:.3f}")

    print("\n--- Gradient boosting ceiling R2 (5-fold CV) ---")
    for component, res in gbr_results.items():
        print(f"  {component:20s} R2 = {res['cv_r2_mean']:.3f} (+/- {res['cv_r2_std']:.3f})")

    print("\n--- Driver summary table (price, heat_demand, pv_out, bes_soc, dhn_export) ---")
    print(summary_table.to_string(index=False))

    print(f"\nFull correlation matrices, all regression coefficient tables, weekday/weekend and "
          f"high/normal price correlations, and lag correlation data written to:\n  {csv_folder}")

    print("\nAnalysis complete.")
    print("================================\n")


# -------------------------------------------------------
# Run full workflow
# -------------------------------------------------------
run_correlation_analysis(
    plot_day=plot_day,
    plot_week=plot_week,
    plot_month=plot_month
)
