"""
11_plot_statistical_results.py
-------------------------------
Visualises the OLS regression and correlation analysis from
9_write_statistical_analysis copy 2.py.

Four publication-ready figures are saved to:
  examples/4_WH+PV+DHN+Flex/plots and print/plots/statistical_results/

Usage:  python 11_plot_statistical_results.py
        (run from the project root, i.e. edge-dc-model/)
"""

import matplotlib
matplotlib.use('Agg')

import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.lines import Line2D
from scipy import stats
import statsmodels.api as sm
from sklearn.preprocessing import StandardScaler

# ======================================================
# SETTINGS  –  change these to select a different period
# ======================================================
case_folder = "4_WH+PV+DHN+Flex"

plot_day   = None   # 1-365
plot_month = None   # 1-12  (None = full year)
plot_week  = None   # 1-52

# ======================================================
# PATHS
# ======================================================
result_file     = os.path.join("examples", case_folder, "results", "opt_vars.csv")
profiles_folder = os.path.join("examples", case_folder, "inputs", "basic", "profiles")
output_folder   = os.path.join("examples", case_folder, "plots and print",
                                "plots", "statistical_results")
os.makedirs(output_folder, exist_ok=True)

# ======================================================
# STYLE
# ======================================================
BLUE   = "#014DF1"
ORANGE = "#F18F01"
RED    = "#F1014D"
GREEN  = "#01A3F1"
GREY   = "#555555"

plt.rcParams.update({
    "font.family": "sans-serif",
    "font.size": 11,
    "axes.titlesize": 12,
    "axes.titleweight": "bold",
    "axes.labelweight": "bold",
    "axes.grid": True,
    "grid.alpha": 0.3,
    "grid.linestyle": "--",
    "figure.dpi": 150,
    "savefig.dpi": 300,
    "savefig.bbox": "tight",
})

# ======================================================
# DATA LOADING
# ======================================================

def expand_and_fill(df, ec_value, var_name):
    full = pd.DataFrame({"S_Time": range(1, 8761)})
    out  = pd.merge(full, df, on="S_Time", how="left")
    out["var_value"] = out["var_value"].fillna(0)
    out.sort_values("S_Time", inplace=True)
    out.reset_index(drop=True, inplace=True)
    return out


data = pd.read_csv(result_file, low_memory=False)

Load_shifting = expand_and_fill(
    data[(data["S_Ec"] == "IT") & (data["var_name"] == "V_LoadShifting")],
    "IT", "V_LoadShifting"
)

demands_df = pd.read_csv(
    os.path.join(profiles_folder, "demands.csv"),
    skiprows=4, header=None,
    names=["S_Time", "HT", "MT", "LT", "IT", "El"]
)
imports_df = pd.read_csv(
    os.path.join(profiles_folder, "imports.csv"),
    skiprows=5, header=None,
    names=["S_Time", "price", "co2"]
)

flexibility = Load_shifting["var_value"].values[:8760]
MT_demand   = demands_df["MT"].values[:8760]
price       = imports_df["price"].values[:8760]
time_index  = pd.date_range(start="2023-01-01", periods=8760, freq="h")

# ======================================================
# PERIOD SELECTION
# ======================================================

def get_period(plot_day, plot_month, plot_week):
    if plot_day is not None:
        start = (plot_day - 1) * 24
        end   = start + 24
        label = f"Day {plot_day}"
    elif plot_month is not None:
        ms = pd.date_range("2023-01-01", periods=12, freq="MS")
        me = pd.date_range("2023-01-01", periods=12, freq="ME")
        start = (ms[plot_month - 1] - time_index[0]).days * 24
        end   = (me[plot_month - 1] - time_index[0]).days * 24 + 24
        label = ms[plot_month - 1].strftime("%B")
    elif plot_week is not None:
        start = (plot_week - 1) * 168
        end   = start + 168
        label = f"Week {plot_week}"
    else:
        start, end = 0, 8760
        label = "Full Year"
    return slice(start, end), label


period_slice, period_label = get_period(plot_day, plot_month, plot_week)

# ======================================================
# BUILD ANALYSIS DATAFRAME  +  FIT OLS MODEL
# ======================================================

df_raw = pd.DataFrame({
    "Flexibility":        flexibility[period_slice],
    "Electricity price":  price[period_slice],
    "Heat demand":        MT_demand[period_slice],
}).dropna()

scaler   = StandardScaler()
df_scaled = pd.DataFrame(scaler.fit_transform(df_raw), columns=df_raw.columns)

X = sm.add_constant(df_scaled[["Electricity price", "Heat demand"]])
y = df_scaled["Flexibility"]
model = sm.OLS(y, X).fit()

# Correlations
corr_pearson  = df_raw.corr(method="pearson")
corr_spearman = df_raw.corr(method="spearman")

# ======================================================
# FIGURE 1 — CORRELATION SUMMARY
#   Top row   : Pearson (left) & Spearman (right) heatmaps
#   Bottom row: Bar chart comparing both methods
# ======================================================

def plot_correlation_summary(corr_pearson, corr_spearman, period_label, output_folder):

    labels = list(corr_pearson.columns)
    n      = len(labels)
    cmap   = "RdBu_r"

    # ---- Fig 1a: Heatmaps ----
    fig_hm, axes_hm = plt.subplots(1, 2, figsize=(13, 5))

    def draw_heatmap(ax, corr, title):
        im = ax.imshow(corr.values, vmin=-1, vmax=1, cmap=cmap, aspect="auto")
        ax.set_xticks(range(n))
        ax.set_yticks(range(n))
        ax.set_xticklabels(labels, rotation=30, ha="right", fontsize=10)
        ax.set_yticklabels(labels, fontsize=10)
        for i in range(n):
            for j in range(n):
                val   = corr.values[i, j]
                color = "white" if abs(val) > 0.4 else "black"
                ax.text(j, i, f"{val:.2f}", ha="center", va="center",
                        fontsize=11, color=color, fontweight="bold")
        fig_hm.colorbar(im, ax=ax, shrink=0.8, label="r")

    draw_heatmap(axes_hm[0], corr_pearson,  f"Pearson")
    draw_heatmap(axes_hm[1], corr_spearman, f"Spearman")
    fig_hm.tight_layout()

    path_hm = os.path.join(output_folder, f"fig1a_heatmaps_{period_label.replace(' ', '_')}.png")
    fig_hm.savefig(path_hm)
    plt.close(fig_hm)
    print(f"Saved: {path_hm}")

    # ---- Fig 1b: Grouped bar chart — Pearson & Spearman for both variables ----
    variables = ["Electricity price", "Heat demand"]
    p_vals    = [corr_pearson.loc["Flexibility", v]  for v in variables]
    sp_vals   = [corr_spearman.loc["Flexibility", v] for v in variables]

    x_pos = np.arange(len(variables))
    bar_w = 0.35

    fig_bar, ax_bar = plt.subplots(figsize=(8, 5.5))

    bars_p  = ax_bar.bar(x_pos - bar_w / 2, p_vals,  bar_w, label="Pearson",  color=BLUE,   alpha=0.85)
    bars_sp = ax_bar.bar(x_pos + bar_w / 2, sp_vals, bar_w, label="Spearman", color=ORANGE, alpha=0.85)

    for bar, val in list(zip(bars_p, p_vals)) + list(zip(bars_sp, sp_vals)):
        sign = 1 if val >= 0 else -1
        ax_bar.text(bar.get_x() + bar.get_width() / 2, val + sign * 0.03,
                    f"{val:.3f}", ha="center",
                    va="bottom" if val >= 0 else "top",
                    fontsize=11, fontweight="bold")

    ax_bar.axhline(0, color="black", linewidth=0.8)
    ax_bar.set_xticks(x_pos)
    ax_bar.set_xticklabels([f"Flexibility vs\n{v}" for v in variables], fontsize=12)
    ax_bar.set_ylabel("Correlation coefficient")
    ax_bar.set_ylim(-1, 1)
    ax_bar.legend(fontsize=11)
    fig_bar.tight_layout()

    path_bar = os.path.join(output_folder, f"fig1b_correlation_barplot_{period_label.replace(' ', '_')}.png")
    fig_bar.savefig(path_bar)
    plt.close(fig_bar)
    print(f"Saved: {path_bar}")


# ======================================================
# FIGURE 2 — SCATTER PLOTS + REGRESSION LINES
# ======================================================

def plot_scatter_regression(df_raw, model, corr_pearson, period_label, output_folder):
    fig, axes = plt.subplots(1, 2, figsize=(14, 5.5))

    pairs = [
        ("Electricity price", BLUE,   axes[0]),
        ("Heat demand",       GREEN,  axes[1]),
    ]

    for predictor, color, ax in pairs:
        x = df_raw[predictor].values
        y = df_raw["Flexibility"].values

        # Scatter
        ax.scatter(x, y, alpha=0.35, s=12, color=color, label="Observations", rasterized=True)

        # OLS regression line (simple, for visual clarity)
        m, b = np.polyfit(x, y, 1)
        x_line = np.linspace(x.min(), x.max(), 200)
        ax.plot(x_line, m * x_line + b, color=RED, linewidth=2, label="OLS fit")

        # Annotate pearson r
        r = corr_pearson.loc["Flexibility", predictor]
        ax.text(0.05, 0.93, f"r = {r:.3f}", transform=ax.transAxes,
                fontsize=11, fontweight="bold", color=RED,
                verticalalignment="top",
                bbox=dict(boxstyle="round,pad=0.3", facecolor="white", edgecolor=RED, alpha=0.8))

        ax.set_xlabel(predictor)
        ax.set_ylabel("Flexibility (V_LoadShifting)")
        ax.legend(fontsize=10)

    plt.tight_layout()
    path = os.path.join(output_folder, f"fig2_scatter_regression_{period_label.replace(' ', '_')}.png")
    fig.savefig(path)
    plt.close(fig)
    print(f"Saved: {path}")


# ======================================================
# FIGURE 3 — OLS REGRESSION DIAGNOSTICS
#   (a) Standardised coefficients + 95 % CI
#   (b) Actual vs Predicted
#   (c) Residuals vs Fitted
#   (d) Q-Q Plot
# ======================================================

def plot_ols_diagnostics(model, period_label, output_folder):
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))

    # ---- (a) Coefficient plot ----
    ax = axes[0, 0]
    coefs  = model.params.drop("const")
    ci     = model.conf_int().drop("const")
    pvals  = model.pvalues.drop("const")

    y_pos  = np.arange(len(coefs))
    colors = [BLUE if c > 0 else RED for c in coefs.values]

    ax.barh(y_pos, coefs.values, color=colors, alpha=0.75, height=0.5)
    ax.errorbar(coefs.values, y_pos,
                xerr=[coefs.values - ci[0].values, ci[1].values - coefs.values],
                fmt="none", color="black", capsize=6, linewidth=1.5, zorder=5)
    ax.axvline(0, color="black", linewidth=0.9)

    for i, (v, p) in enumerate(zip(coefs.values, pvals.values)):
        sig = "***" if p < 0.001 else ("**" if p < 0.01 else ("*" if p < 0.05 else "n.s."))
        ax.text(v + 0.02 * np.sign(v), i, sig, va="center", ha="left" if v >= 0 else "right",
                fontsize=10, color="black")

    ax.set_yticks(y_pos)
    ax.set_yticklabels(coefs.index, fontsize=11)
    ax.set_xlabel("Standardised coefficient  (* p<0.05  ** p<0.01  *** p<0.001)")

    # ---- (b) Actual vs Predicted ----
    ax = axes[0, 1]
    y_true = model.model.endog
    y_pred = model.fittedvalues

    ax.scatter(y_true, y_pred, alpha=0.35, s=12, color=BLUE, rasterized=True)
    lims = [min(y_true.min(), y_pred.min()), max(y_true.max(), y_pred.max())]
    ax.plot(lims, lims, color=RED, linewidth=2, linestyle="--", label="Perfect fit")
    ax.set_xlabel("Actual (standardised)")
    ax.set_ylabel(f"Predicted (standardised)  [R² = {model.rsquared:.3f}]")
    ax.legend(fontsize=10)

    # ---- (c) Residuals vs Fitted ----
    ax = axes[1, 0]
    residuals = model.resid

    ax.scatter(y_pred, residuals, alpha=0.35, s=12, color=ORANGE, rasterized=True)
    ax.axhline(0, color=RED, linewidth=1.5, linestyle="--")

    # Lowess smoothing line
    lowess = sm.nonparametric.lowess(residuals, y_pred, frac=0.3)
    ax.plot(lowess[:, 0], lowess[:, 1], color=GREY, linewidth=2, label="LOWESS")

    ax.set_xlabel("Fitted values")
    ax.set_ylabel("Residuals")
    ax.legend(fontsize=10)

    # ---- (d) Q-Q Plot ----
    ax = axes[1, 1]
    (osm, osr), (slope, intercept, r) = stats.probplot(residuals, dist="norm")
    ax.scatter(osm, osr, alpha=0.5, s=12, color=BLUE, rasterized=True)
    ax.plot(osm, slope * np.array(osm) + intercept, color=RED, linewidth=2, label="Normal line")
    ax.set_xlabel("Theoretical quantiles")
    ax.set_ylabel("Sample quantiles")
    ax.legend(fontsize=10)

    plt.tight_layout()
    path = os.path.join(output_folder, f"fig3_ols_diagnostics_{period_label.replace(' ', '_')}.png")
    fig.savefig(path)
    plt.close(fig)
    print(f"Saved: {path}")


# ======================================================
# FIGURE 4 — CONTEXTUAL ANALYSES
#   (a) Lagged correlation (±24 h)
#   (b) Weekday vs Weekend correlation
#   (c) High-price vs Normal-price correlation
# ======================================================

def plot_contextual_analyses(df_raw, time_index, period_slice, period_label, output_folder):
    fig = plt.figure(figsize=(16, 5.5))
    gs  = fig.add_gridspec(1, 3, wspace=0.38)

    # ---- (a) Lagged correlation ----
    ax = fig.add_subplot(gs[0])

    lags       = range(-24, 25)
    lag_corrs  = [df_raw["Flexibility"].corr(df_raw["Electricity price"].shift(lag))
                  for lag in lags]
    lag_df     = pd.DataFrame({"lag": list(lags), "corr": lag_corrs})
    best_idx   = lag_df["corr"].abs().idxmax()
    best_lag   = lag_df.loc[best_idx, "lag"]
    best_corr  = lag_df.loc[best_idx, "corr"]

    ax.plot(lag_df["lag"], lag_df["corr"], color=BLUE, linewidth=2, zorder=2)
    ax.fill_between(lag_df["lag"], lag_df["corr"], alpha=0.2, color=BLUE)
    ax.axvline(0, color=GREY,  linewidth=1.2, linestyle="--", label="No lag")
    ax.axhline(0, color="black", linewidth=0.7, linestyle="-")
    ax.scatter([best_lag], [best_corr], color=RED, s=80, zorder=5,
               label=f"Best lag: {int(best_lag)} h  (r = {best_corr:.3f})")

    ax.set_xlabel("Lag (hours)")
    ax.set_ylabel("Pearson r")
    ax.legend(fontsize=9)

    # ---- (b) Weekday vs Weekend ----
    ax = fig.add_subplot(gs[1])

    df_wk            = df_raw.copy()
    df_wk["datetime"] = time_index[period_slice]
    df_wk["weekday"]  = df_wk["datetime"].dt.weekday
    df_wk["is_weekend"] = df_wk["weekday"] >= 5

    wkday_r_price = df_wk[~df_wk["is_weekend"]][["Flexibility","Electricity price"]].corr().iloc[0,1]
    wkend_r_price = df_wk[ df_wk["is_weekend"]][["Flexibility","Electricity price"]].corr().iloc[0,1]
    wkday_r_heat  = df_wk[~df_wk["is_weekend"]][["Flexibility","Heat demand"]].corr().iloc[0,1]
    wkend_r_heat  = df_wk[ df_wk["is_weekend"]][["Flexibility","Heat demand"]].corr().iloc[0,1]

    x_wd  = np.array([0, 1])
    bar_w = 0.35

    bars_price = ax.bar(x_wd - bar_w/2, [wkday_r_price, wkend_r_price], bar_w,
                        label="vs Electricity price", color=BLUE,   alpha=0.85)
    bars_heat  = ax.bar(x_wd + bar_w/2, [wkday_r_heat,  wkend_r_heat],  bar_w,
                        label="vs Heat demand",       color=GREEN,  alpha=0.85)

    for bar, val in list(zip(bars_price, [wkday_r_price, wkend_r_price])) + \
                    list(zip(bars_heat,  [wkday_r_heat,  wkend_r_heat])):
        sign = 1 if val >= 0 else -1
        ax.text(bar.get_x() + bar.get_width()/2, val + sign*0.04,
                f"{val:.3f}", ha="center", va="bottom" if val >= 0 else "top",
                fontsize=9, fontweight="bold")

    ax.axhline(0, color="black", linewidth=0.8)
    ax.set_xticks(x_wd)
    ax.set_xticklabels(["Weekday", "Weekend"])
    ax.set_ylabel("Pearson r (Flexibility vs …)")
    ax.set_ylim(-1, 1)
    ax.legend(fontsize=9)

    # ---- (c) High-price vs Normal-price ----
    ax = fig.add_subplot(gs[2])

    threshold = df_raw["Electricity price"].quantile(0.9)
    mask_high = df_raw["Electricity price"] > threshold

    r_price_high   = df_raw[mask_high][["Flexibility","Electricity price"]].corr().iloc[0,1]
    r_price_normal = df_raw[~mask_high][["Flexibility","Electricity price"]].corr().iloc[0,1]
    r_heat_high    = df_raw[mask_high][["Flexibility","Heat demand"]].corr().iloc[0,1]
    r_heat_normal  = df_raw[~mask_high][["Flexibility","Heat demand"]].corr().iloc[0,1]

    x_pr  = np.array([0, 1])

    bars_pr = ax.bar(x_pr - bar_w/2, [r_price_normal, r_price_high], bar_w,
                     label="vs Electricity price", color=BLUE,  alpha=0.85)
    bars_ht = ax.bar(x_pr + bar_w/2, [r_heat_normal,  r_heat_high],  bar_w,
                     label="vs Heat demand",       color=GREEN, alpha=0.85)

    for bar, val in list(zip(bars_pr, [r_price_normal, r_price_high])) + \
                    list(zip(bars_ht, [r_heat_normal,  r_heat_high])):
        sign = 1 if val >= 0 else -1
        ax.text(bar.get_x() + bar.get_width()/2, val + sign*0.04,
                f"{val:.3f}", ha="center", va="bottom" if val >= 0 else "top",
                fontsize=9, fontweight="bold")

    ax.axhline(0, color="black", linewidth=0.8)
    ax.set_xticks(x_pr)
    ax.set_xticklabels([f"Normal price\n(≤ P90)", f"High price\n(> P90)"])
    ax.set_ylabel("Pearson r (Flexibility vs …)")
    ax.set_ylim(-1, 1)
    ax.set_xticklabels([f"Normal price\n(≤ P90 = {threshold:.2f})", f"High price\n(> P90)"])
    ax.legend(fontsize=9)

    path = os.path.join(output_folder, f"fig4_contextual_{period_label.replace(' ', '_')}.png")
    fig.savefig(path)
    plt.close(fig)
    print(f"Saved: {path}")


# ======================================================
# FIGURE 5 — R² VISUALISATION
#   (a) Grouped bar: R² for price-only, heat-only, full model
#   (b) Stacked bar: explained vs unexplained variance (full model)
#   (c) Donut chart: variance decomposition
# ======================================================

def plot_r2_visualisation(df_scaled, model, period_label, output_folder):

    # Fit single-predictor models for comparison
    def r2_single(predictor):
        X_ = sm.add_constant(df_scaled[[predictor]])
        return sm.OLS(df_scaled["Flexibility"], X_).fit().rsquared

    r2_price = r2_single("Electricity price")
    r2_heat  = r2_single("Heat demand")
    r2_full  = model.rsquared

    labels_bar = ["Price only", "Heat demand only", "Full model\n(Price + Heat demand)"]
    r2_vals    = [r2_price, r2_heat, r2_full]
    colors_bar = [BLUE, GREEN, ORANGE]

    fig = plt.figure(figsize=(16, 5.5))
    gs  = fig.add_gridspec(1, 3, wspace=0.4)

    # ---- (a) R² comparison bar chart ----
    ax = fig.add_subplot(gs[0])
    bars = ax.bar(labels_bar, r2_vals, color=colors_bar, alpha=0.85, width=0.5)
    for bar, val in zip(bars, r2_vals):
        ax.text(bar.get_x() + bar.get_width() / 2, val + 0.005,
                f"{val:.3f}\n({val*100:.1f}%)",
                ha="center", va="bottom", fontsize=10, fontweight="bold")
    ax.set_ylabel("R²")
    ax.set_ylim(0, min(r2_full * 1.5, 1.0))
    ax.tick_params(axis="x", labelsize=10)

    # ---- (b) Stacked bar: explained vs unexplained ----
    ax = fig.add_subplot(gs[1])
    models_stacked = ["Price only", "Heat demand only", "Full model"]
    explained   = r2_vals
    unexplained = [1 - v for v in r2_vals]
    x = np.arange(len(models_stacked))
    bar_w = 0.5

    b1 = ax.bar(x, explained,   bar_w, label="Explained (R²)",       color=BLUE,  alpha=0.85)
    b2 = ax.bar(x, unexplained, bar_w, label="Unexplained (1 − R²)", color=GREY,  alpha=0.35,
                bottom=explained)

    for bar, val in zip(b1, explained):
        ax.text(bar.get_x() + bar.get_width() / 2, val / 2,
                f"{val*100:.1f}%", ha="center", va="center",
                fontsize=10, fontweight="bold", color="white")
    for bar, val, exp in zip(b2, unexplained, explained):
        ax.text(bar.get_x() + bar.get_width() / 2, exp + val / 2,
                f"{val*100:.1f}%", ha="center", va="center",
                fontsize=10, color=GREY)

    ax.set_xticks(x)
    ax.set_xticklabels(models_stacked, fontsize=10)
    ax.set_ylabel("Proportion of variance")
    ax.set_ylim(0, 1)
    ax.legend(fontsize=10, loc="upper right")

    # ---- (c) Donut chart: full model decomposition ----
    ax = fig.add_subplot(gs[2])

    # Approximate unique contribution of each predictor via partial R²
    # R²(price unique) = R²(full) - R²(heat only)
    # R²(heat unique)  = R²(full) - R²(price only)
    # shared           = R²(full) - unique_price - unique_heat  (can be negative; clamp to 0)
    unique_price = max(r2_full - r2_heat,  0)
    unique_heat  = max(r2_full - r2_price, 0)
    shared       = max(r2_full - unique_price - unique_heat, 0)
    unexplained_ = 1 - r2_full

    sizes  = [unique_price, unique_heat, shared, unexplained_]
    clabels = [
        f"Price unique\n{unique_price*100:.1f}%",
        f"Heat demand unique\n{unique_heat*100:.1f}%",
        f"Shared\n{shared*100:.1f}%",
        f"Unexplained\n{unexplained_*100:.1f}%",
    ]
    donut_colors = [BLUE, GREEN, ORANGE, "#cccccc"]

    wedges, texts = ax.pie(
        sizes, labels=clabels, colors=donut_colors,
        startangle=90, wedgeprops=dict(width=0.55),
        textprops=dict(fontsize=9),
    )
    # Centre annotation
    ax.text(0, 0, f"R² = {r2_full:.3f}", ha="center", va="center",
            fontsize=12, fontweight="bold")

    path = os.path.join(output_folder, f"fig5_r2_{period_label.replace(' ', '_')}.png")
    fig.savefig(path)
    plt.close(fig)
    print(f"Saved: {path}")


# ======================================================
# MAIN
# ======================================================

if __name__ == "__main__":
    print(f"\nGenerating statistical visualisations for period: {period_label}")
    print(f"Data points: {len(df_raw)}\n")
    print(f"Output folder: {os.path.abspath(output_folder)}\n")

    plot_correlation_summary(corr_pearson, corr_spearman, period_label, output_folder)
    plot_scatter_regression(df_raw, model, corr_pearson, period_label, output_folder)
    plot_ols_diagnostics(model, period_label, output_folder)
    plot_contextual_analyses(df_raw, time_index, period_slice, period_label, output_folder)
    plot_r2_visualisation(df_scaled, model, period_label, output_folder)

    print("\nAll figures saved.")
