import matplotlib
matplotlib.use('Agg')  # ensures plots work in scripts

import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import os

# ======================================================
# SETTINGS
# ======================================================

case_folder = "4_WH+PV+DHN+Flex"

# --- USER OPTIONS ---
# Set one of these to a value to plot a specific period. Leave others as None.
plot_day = None      # 1-365 (e.g., 15 for Jan 15)
plot_month = 1       # 1-12 (e.g., 1 for Jan, 12 for Dec)
plot_week = None     # 1-52 (e.g., 5 for week 5)

# Paths
result_file = os.path.join("examples", case_folder, "results", "opt_vars.csv")
output_folder = os.path.join("examples", case_folder, "plots and print", "plots", "other plots")
os.makedirs(output_folder, exist_ok=True)

print("Result file:", os.path.abspath(result_file))
print("Output folder:", os.path.abspath(output_folder))

# ======================================================
# LOAD DATA
# ======================================================

data = pd.read_csv(result_file, low_memory=False)

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

IT_Profile = expand_and_fill_data(
    data[(data['S_Ec'] == 'IT') & (data['var_name'] == 'V_DemandSupply')],
    'IT', 'V_DemandSupply'
)

Load_shifting = expand_and_fill_data(
    data[(data['S_Ec'] == 'IT') & (data['var_name'] == 'V_LoadShifting')],
    'IT', 'V_LoadShifting'
)

# ======================================================
# MAIN ANALYSIS FUNCTION
# ======================================================

def run_correlation_analysis():

    print("\n==============================")
    print("RUNNING CORRELATION ANALYSIS")
    print("==============================")

    import statsmodels.api as sm
    from sklearn.preprocessing import StandardScaler

    # Load external data
    profiles_folder = os.path.join("examples", case_folder, "inputs", "basic", "profiles")
    demands_path = os.path.join(profiles_folder, "demands.csv")
    imports_path = os.path.join(profiles_folder, "imports.csv")

    demands_df = pd.read_csv(demands_path, skiprows=4, header=None,
                             names=['S_Time', 'HT', 'MT', 'LT', 'IT', 'El'])
    imports_df = pd.read_csv(imports_path, skiprows=5, header=None,
                             names=['S_Time', 'price', 'co2'])

    MT_demand = demands_df['MT'].values[:8760]
    price = imports_df['price'].values[:8760]
    flexibility = Load_shifting['var_value'].values[:8760]

    # Period selection
    if plot_day:
        start = (plot_day - 1) * 24
        end = start + 24
    elif plot_month:
        month_starts = pd.date_range('2023-01-01', periods=12, freq='MS')
        month_ends = pd.date_range('2023-01-01', periods=12, freq='ME')
        start = (month_starts[plot_month-1] - month_starts[0]).days * 24
        end = (month_ends[plot_month-1] - month_starts[0]).days * 24 + 24
    elif plot_week:
        start = (plot_week - 1) * 168
        end = start + 168
    else:
        start, end = 0, 8760

    df = pd.DataFrame({
        "Flexibility": flexibility[start:end],
        "Electricity price": price[start:end],
        "Heat demand": MT_demand[start:end]
    }).dropna()

    print("DF shape:", df.shape)

    if df.empty:
        raise ValueError("DataFrame is empty — check inputs.")


    # ==================================================
    # COMBINED TRIANGLE HEATMAP (Pearson + Spearman)
    # ==================================================

    corr_pearson = df.corr()
    corr_spearman = df.corr(method="spearman")

    # Only keep flexibility correlations
    labels = ["Flexibility", "Electricity price", "Heat demand"]
    n = len(labels)
    combined = np.full((n, n), np.nan)

    # Only fill correlations with flexibility
    for i in range(n):
        for j in range(n):
            if i == 0 and j > 0:
                combined[i, j] = corr_pearson.iloc[i, j]
            elif j == 0 and i > 0:
                combined[i, j] = corr_spearman.iloc[i, j]
            elif i == j:
                combined[i, j] = 1.0

    # Plot
    plt.figure(figsize=(6, 5))
    im = plt.imshow(combined, vmin=-1, vmax=1)

    # Draw separator lines
    plt.plot([-0.5, n - 0.5], [-0.5, n - 0.5], color='black', linewidth=2)

    plt.colorbar(im)
    plt.xticks(range(n), labels, rotation=45, ha="right")
    plt.yticks(range(n), labels)

    # Annotate values
    for i in range(n):
        for j in range(n):
            if np.isnan(combined[i, j]):
                continue
            value = combined[i, j]
            text = f"{value:.2f}" if i != j else "—"
            color = 'white' if abs(value) > 0.4 else 'black'
            plt.text(j, i, text, ha='center', va='center', color=color)

    plt.tight_layout()
    filepath = os.path.join(output_folder, "correlation_heatmap_combined_triangle.png")
    plt.savefig(filepath)
    plt.close()
    print("Saved:", filepath)

    # ==================================================
    # BAR PLOT: Pearson + Spearman correlations
    # ==================================================
    # Flexibility vs Electricity price (Pearson and Spearman)
    pearson_flex_price = corr_pearson.loc["Flexibility", "Electricity price"]
    spearman_flex_price = corr_spearman.loc["Flexibility", "Electricity price"]
    # Flexibility vs Heat demand (Pearson and Spearman)
    pearson_flex_heat = corr_pearson.loc["Flexibility", "Heat demand"]
    spearman_flex_heat = corr_spearman.loc["Flexibility", "Heat demand"]

    bar_labels = [
        "Flexibility vs Electricity price (Pearson)",
        "Flexibility vs Electricity price (Spearman)",
        "Flexibility vs Heat demand (Pearson)",
        "Flexibility vs Heat demand (Spearman)"
    ]
    bar_values = [pearson_flex_price, spearman_flex_price, pearson_flex_heat, spearman_flex_heat]

    plt.figure(figsize=(8, 5))
    bars = plt.bar(bar_labels, bar_values, color=["#377eb8", "#ff7f00", "#4daf4a", "#f781bf"])
    plt.ylim(-1, 1)
    plt.ylabel("Correlation Coefficient", fontsize=12, fontweight='bold')
    plt.xlabel("Correlation Pair", fontsize=12, fontweight='bold')
    # plt.title("Pearson and Spearman Correlations with Flexibility")
    plt.xticks(rotation=25, ha="right", fontsize=12)
    plt.yticks(fontsize=12)
    # Annotate values on bars
    for bar, value in zip(bars, bar_values):
        plt.text(bar.get_x() + bar.get_width()/2, value + 0.05 * np.sign(value), f"{value:.2f}",
                 ha='center', va='bottom' if value >= 0 else 'top', fontsize=12, fontweight='bold')
    plt.tight_layout()
    filepath = os.path.join(output_folder, "correlation_barplot_pearson_spearman.png")
    plt.savefig(filepath)
    plt.close()
    print("Saved:", filepath)

    # ==================================================
    # SCATTER PLOTS
    # ==================================================

    # Price vs Flexibility
    plt.figure()
    plt.scatter(df['Electricity price'], df['Flexibility'], alpha=0.3)

    x = np.sort(df['Electricity price'])
    m, b = np.polyfit(df['Electricity price'], df['Flexibility'], 1)
    plt.plot(x, m*x + b)

    plt.xlabel("Price")
    plt.ylabel("Flexibility")

    filepath = os.path.join(output_folder, "scatter_price_vs_flexibility.png")
    plt.savefig(filepath)
    plt.close()
    print("Saved:", filepath)

    # Heat vs Flexibility
    plt.figure()
    plt.scatter(df['Heat demand'], df['Flexibility'], alpha=0.3)

    x = np.sort(df['Heat demand'])
    m, b = np.polyfit(df['Heat demand'], df['Flexibility'], 1)
    plt.plot(x, m*x + b)

    plt.xlabel("Heat Demand")
    plt.ylabel("Flexibility")

    filepath = os.path.join(output_folder, "scatter_heat_vs_flexibility.png")
    plt.savefig(filepath)
    plt.close()
    print("Saved:", filepath)

    # ==================================================
    # LAGGED CORRELATION
    # ==================================================
    lags = range(-24, 25)
    corrs = [df["Flexibility"].corr(df["Electricity price"].shift(l)) for l in lags]

    plt.figure()
    plt.plot(lags, corrs)
    plt.axvline(0)

    filepath = os.path.join(output_folder, "lagged_correlation.png")
    plt.savefig(filepath)
    plt.close()
    print("Saved:", filepath)

    # ==================================================
    # REGRESSION
    # ==================================================
    scaler = StandardScaler()
    df_scaled = pd.DataFrame(scaler.fit_transform(df), columns=df.columns)

    X = sm.add_constant(df_scaled[["Electricity price", "Heat demand"]])
    y = df_scaled["Flexibility"]

    model = sm.OLS(y, X).fit()
    print(model.summary())

    # ==================================================
    # WEEKDAY VS WEEKEND
    # ==================================================
    time_index = pd.date_range(start='2023-01-01', periods=len(df), freq='h')
    df["weekday"] = time_index.weekday
    df["is_weekend"] = df["weekday"] >= 5

    weekday_corr = df[~df["is_weekend"]][["Flexibility", "Electricity price"]].corr().iloc[0,1]
    weekend_corr = df[df["is_weekend"]][["Flexibility", "Electricity price"]].corr().iloc[0,1]

    plt.figure()
    plt.bar(["Weekday", "Weekend"], [weekday_corr, weekend_corr])

    filepath = os.path.join(output_folder, "weekday_vs_weekend.png")
    plt.savefig(filepath)
    plt.close()
    print("Saved:", filepath)

    # ==================================================
    # HIGH VS NORMAL PRICE
    # ==================================================
    threshold = df["Electricity price"].quantile(0.9)

    high_corr = df[df["Electricity price"] > threshold][["Flexibility", "Electricity price"]].corr().iloc[0,1]
    normal_corr = df[df["Electricity price"] <= threshold][["Flexibility", "Electricity price"]].corr().iloc[0,1]

    plt.figure()
    plt.bar(["Normal", "High"], [normal_corr, high_corr])

    filepath = os.path.join(output_folder, "high_vs_normal_price.png")
    plt.savefig(filepath)
    plt.close()
    print("Saved:", filepath)

    print("\nAnalysis complete.")
    print("================================\n")


    # ==================================================
    # COEFFICIENT PLOT
    # ==================================================

    coefs = model.params
    conf = model.conf_int()

    # Remove intercept (optional but recommended for clarity)
    coefs = coefs.drop("const")
    conf = conf.drop("const")

    variables = coefs.index
    values = coefs.values
    lower = conf[0].values
    upper = conf[1].values

    # Convert to error bars
    errors = [values - lower, upper - values]

    plt.figure()

    # Plot coefficients with confidence intervals
    plt.errorbar(values, range(len(values)),
                 xerr=errors,
                 fmt='o')

    # Vertical line at zero
    plt.axvline(0)

    plt.yticks(range(len(values)), variables)
    plt.xlabel("Coefficient Value")
    # plt.title("Regression Coefficients with 95% CI")

    plt.tight_layout()

    filepath = os.path.join(output_folder, "coefficient_plot.png")
    plt.savefig(filepath)
    plt.close()

    print("Saved:", filepath)

    # ==================================================
    # COEFFICIENT BAR PLOT (NICE VERSION)
    # ==================================================

    coefs = model.params
    conf = model.conf_int()

    # Drop intercept for clarity
    coefs = coefs.drop("const")
    conf = conf.drop("const")

    variables = coefs.index
    values = coefs.values
    lower = conf[0].values
    upper = conf[1].values

    # Sort by absolute importance (optional but recommended)
    order = np.argsort(np.abs(values))
    variables = variables[order]
    values = values[order]
    lower = lower[order]
    upper = upper[order]

    # Error bars
    errors = [values - lower, upper - values]

    plt.figure(figsize=(6, 4))

    # Horizontal bars
    plt.barh(variables, values, xerr=errors)

    # Zero reference line
    plt.axvline(0)

    plt.xlabel("Standardized Coefficient")
    # plt.title("Regression Coefficients (with 95% CI)")

    plt.tight_layout()

    filepath = os.path.join(output_folder, "coefficient_barplot.png")
    plt.savefig(filepath)
    plt.close()

    print("Saved:", filepath)


# ======================================================
# RUN SCRIPT
# ======================================================

if __name__ == "__main__":

    # test plot (guarantees matplotlib works)
    plt.figure()
    plt.plot([1,2,3],[1,4,9])
    test_path = os.path.join(output_folder, "test_plot.png")
    plt.savefig(test_path)
    plt.close()
    print("Test plot saved:", test_path)

    run_correlation_analysis()
