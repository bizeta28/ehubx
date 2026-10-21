import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
import os
from scipy import stats
import statsmodels.api as sm
from sklearn.preprocessing import StandardScaler


# Set the scenario folder
case_folder = "4_WH+PV+DHN+Flex"

# --- USER OPTIONS ---
plot_day = None      # 1-365 (e.g., 15 for Jan 15)
plot_month = None       # 1-12 (e.g., 1 for Jan, 12 for Dec)
plot_week = None     # 1-52 (e.g., 5 for week 5)

# Paths
result_file = os.path.join("examples", case_folder, "results", "opt_vars.csv")
profiles_folder = os.path.join("examples", case_folder, "inputs", "basic", "profiles")
output_folder = os.path.join("examples", case_folder, "plots and print", "plots", "correlation_analysis")
os.makedirs(output_folder, exist_ok=True)

# Set style
sns.set_style("whitegrid")
plt.rcParams['figure.figsize'] = (12, 7)
plt.rcParams['font.size'] = 10


def expand_and_fill_data(df, ec_value, var_name):
    """Expand time series data to full year"""
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


def load_data(case_folder, profiles_folder):
    """Load all required data"""
    # Load optimization results
    data = pd.read_csv(result_file, low_memory=False)
    Load_shifting = expand_and_fill_data(
        data[(data['S_Ec'] == 'IT') & (data['var_name'] == 'V_LoadShifting')],
        'IT', 'V_LoadShifting'
    )
    flexibility = Load_shifting['var_value'].values[:8760]

    # Load demands
    demands_path = os.path.join(profiles_folder, "demands.csv")
    demand_columns = ['S_Time', 'HT', 'MT', 'LT', 'IT', 'El']
    demands_df = pd.read_csv(demands_path, skiprows=4, header=None, names=demand_columns)
    MT_demand = demands_df['MT'].values[:8760]

    # Load electricity price
    imports_path = os.path.join(profiles_folder, "imports.csv")
    imports_columns = ['S_Time', 'price', 'co2']
    imports_df = pd.read_csv(imports_path, skiprows=5, header=None, names=imports_columns)
    price = imports_df['price'].values[:8760]

    time_index = pd.date_range(start='2023-01-01', periods=8760, freq='h')

    return flexibility, MT_demand, price, time_index


def get_period_indices(plot_day, plot_month, plot_week, time_index):
    """Get period indices and label"""
    if plot_day is not None:
        start = (plot_day - 1) * 24
        end = start + 24
        label = f"Day {plot_day}"
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
        label = f"Week {plot_week}"
        return slice(start, end), label
    else:
        return slice(0, 8760), "Full Year"


def create_correlation_heatmap(df, output_folder, period_label):
    """Create correlation matrix heatmaps (Pearson and Spearman)"""
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    # Pearson correlation
    pearson_corr = df.corr(method='pearson')
    sns.heatmap(pearson_corr, annot=True, fmt='.3f', cmap='RdBu_r', center=0,
                square=True, linewidths=1, cbar_kws={"shrink": 0.8}, ax=axes[0],
                vmin=-1, vmax=1)
    axes[0].set_title(f'Pearson Correlation - {period_label}', fontsize=12, fontweight='bold')

    # Spearman correlation
    spearman_corr = df.corr(method='spearman')
    sns.heatmap(spearman_corr, annot=True, fmt='.3f', cmap='RdBu_r', center=0,
                square=True, linewidths=1, cbar_kws={"shrink": 0.8}, ax=axes[1],
                vmin=-1, vmax=1)
    axes[1].set_title(f'Spearman Correlation - {period_label}', fontsize=12, fontweight='bold')

    plt.tight_layout()
    plt.savefig(os.path.join(output_folder, f"01_correlation_heatmap_{period_label.replace(' ', '_')}.png"), dpi=300, bbox_inches='tight')
    plt.close()
    print(f"✓ Saved: correlation heatmap")


def create_scatter_plots(df, output_folder, period_label):
    """Create scatter plots with regression lines for each variable pair"""
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    # Price vs Flexibility
    axes[0].scatter(df['price'], df['flexibility'], alpha=0.5, s=20)
    z = np.polyfit(df['price'].dropna(), df['flexibility'].dropna(), 1)
    p = np.poly1d(z)
    axes[0].plot(df['price'].sort_values(), p(df['price'].sort_values()), "r-", linewidth=2, label='Regression line')
    corr = df['price'].corr(df['flexibility'])
    axes[0].set_xlabel('Electricity Price')
    axes[0].set_ylabel('Flexibility')
    axes[0].set_title(f'Price vs Flexibility (r={corr:.3f})', fontsize=11, fontweight='bold')
    axes[0].legend()
    axes[0].grid(True, alpha=0.3)

    # Heat Demand vs Flexibility
    axes[1].scatter(df['heat_demand'], df['flexibility'], alpha=0.5, s=20, color='green')
    z = np.polyfit(df['heat_demand'].dropna(), df['flexibility'].dropna(), 1)
    p = np.poly1d(z)
    axes[1].plot(df['heat_demand'].sort_values(), p(df['heat_demand'].sort_values()), "r-", linewidth=2, label='Regression line')
    corr = df['heat_demand'].corr(df['flexibility'])
    axes[1].set_xlabel('Heat Demand (MT)')
    axes[1].set_ylabel('Flexibility')
    axes[1].set_title(f'Heat Demand vs Flexibility (r={corr:.3f})', fontsize=11, fontweight='bold')
    axes[1].legend()
    axes[1].grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(os.path.join(output_folder, f"02_scatter_plots_{period_label.replace(' ', '_')}.png"), dpi=300, bbox_inches='tight')
    plt.close()
    print(f"✓ Saved: scatter plots with regression lines")


def create_distribution_plots(df, output_folder, period_label):
    """Create distribution plots for each variable"""
    fig, axes = plt.subplots(1, 3, figsize=(15, 4))

    for idx, col in enumerate(['flexibility', 'price', 'heat_demand']):
        axes[idx].hist(df[col], bins=30, alpha=0.7, color='steelblue', edgecolor='black')
        axes[idx].axvline(df[col].mean(), color='red', linestyle='--', linewidth=2, label=f'Mean: {df[col].mean():.2f}')
        axes[idx].axvline(df[col].median(), color='green', linestyle='--', linewidth=2, label=f'Median: {df[col].median():.2f}')
        axes[idx].set_xlabel(col.replace('_', ' ').title())
        axes[idx].set_ylabel('Frequency')
        axes[idx].set_title(f'Distribution of {col.replace("_", " ").title()}', fontweight='bold')
        axes[idx].legend()
        axes[idx].grid(True, alpha=0.3, axis='y')

    plt.tight_layout()
    plt.savefig(os.path.join(output_folder, f"03_distributions_{period_label.replace(' ', '_')}.png"), dpi=300, bbox_inches='tight')
    plt.close()
    print(f"✓ Saved: distribution plots")


def create_time_series_plot(df, time_index, period_slice, output_folder, period_label):
    """Create time series plots of all three variables"""
    fig, axes = plt.subplots(3, 1, figsize=(14, 10), sharex=True)

    time_subset = time_index[period_slice]

    # Normalize for comparison
    axes[0].plot(time_subset, df['flexibility'], linewidth=1.5, color='steelblue', label='Flexibility')
    axes[0].set_ylabel('Flexibility', fontweight='bold')
    axes[0].set_title(f'Time Series - {period_label}', fontsize=12, fontweight='bold')
    axes[0].grid(True, alpha=0.3)
    axes[0].legend(loc='upper right')

    axes[1].plot(time_subset, df['price'], linewidth=1.5, color='coral', label='Price')
    axes[1].set_ylabel('Electricity Price (€/MWh)', fontweight='bold')
    axes[1].grid(True, alpha=0.3)
    axes[1].legend(loc='upper right')

    axes[2].plot(time_subset, df['heat_demand'], linewidth=1.5, color='green', label='Heat Demand')
    axes[2].set_ylabel('Heat Demand (MT)', fontweight='bold')
    axes[2].set_xlabel('Time', fontweight='bold')
    axes[2].grid(True, alpha=0.3)
    axes[2].legend(loc='upper right')

    # Format x-axis
    if len(time_subset) <= 24:
        axes[2].xaxis.set_major_locator(plt.matplotlib.dates.HourLocator(interval=4))
        axes[2].xaxis.set_major_formatter(plt.matplotlib.dates.DateFormatter('%H:%M'))
    elif len(time_subset) <= 168:
        axes[2].xaxis.set_major_locator(plt.matplotlib.dates.DayLocator())
        axes[2].xaxis.set_major_formatter(plt.matplotlib.dates.DateFormatter('%a'))
    else:
        axes[2].xaxis.set_major_locator(plt.matplotlib.dates.MonthLocator())
        axes[2].xaxis.set_major_formatter(plt.matplotlib.dates.DateFormatter('%b'))

    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig(os.path.join(output_folder, f"04_time_series_{period_label.replace(' ', '_')}.png"), dpi=300, bbox_inches='tight')
    plt.close()
    print(f"✓ Saved: time series plots")


def create_lagged_correlation_plot(df, output_folder, period_label):
    """Create lagged correlation analysis"""
    lag_range = range(-24, 25)
    lag_results = []

    for lag in lag_range:
        corr = df["flexibility"].corr(df["price"].shift(lag))
        lag_results.append((lag, corr))

    lag_df = pd.DataFrame(lag_results, columns=["lag_hours", "correlation"])
    best_lag = lag_df.iloc[lag_df["correlation"].abs().idxmax()]

    fig, ax = plt.subplots(figsize=(12, 6))
    ax.plot(lag_df["lag_hours"], lag_df["correlation"], linewidth=2, marker='o', markersize=4)
    ax.axvline(0, color='red', linestyle='--', linewidth=2, alpha=0.7, label='No lag')
    ax.axhline(0, color='black', linestyle='-', linewidth=0.8, alpha=0.3)
    ax.fill_between(lag_df["lag_hours"], lag_df["correlation"], alpha=0.3)
    ax.scatter([best_lag['lag_hours']], [best_lag['correlation']], color='red', s=100, zorder=5,
              label=f"Best lag: {int(best_lag['lag_hours'])}h (r={best_lag['correlation']:.3f})")
    ax.set_xlabel('Lag (hours)', fontweight='bold')
    ax.set_ylabel('Correlation Coefficient', fontweight='bold')
    ax.set_title(f'Lagged Correlation: Flexibility vs Price - {period_label}', fontsize=12, fontweight='bold')
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=10)
    plt.tight_layout()
    plt.savefig(os.path.join(output_folder, f"05_lagged_correlation_{period_label.replace(' ', '_')}.png"), dpi=300, bbox_inches='tight')
    plt.close()
    print(f"✓ Saved: lagged correlation plot (best lag: {int(best_lag['lag_hours'])}h)")


def create_regression_summary_plot(model, output_folder, period_label):
    """Create visualization of regression results"""
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))

    # Coefficients with confidence intervals
    coef_data = pd.DataFrame({
        'Variable': ['Price', 'Heat Demand'],
        'Coefficient': model.params[1:].values,
        'Std Error': model.bse[1:].values
    })
    coef_data['CI_lower'] = coef_data['Coefficient'] - 1.96 * coef_data['Std Error']
    coef_data['CI_upper'] = coef_data['Coefficient'] + 1.96 * coef_data['Std Error']

    axes[0, 0].barh(coef_data['Variable'], coef_data['Coefficient'],
                    xerr=[coef_data['Coefficient'] - coef_data['CI_lower'],
                          coef_data['CI_upper'] - coef_data['Coefficient']],
                    capsize=5, color=['coral', 'green'], alpha=0.7)
    axes[0, 0].axvline(0, color='black', linestyle='-', linewidth=0.8)
    axes[0, 0].set_xlabel('Coefficient Value', fontweight='bold')
    axes[0, 0].set_title('Regression Coefficients with 95% CI', fontweight='bold')
    axes[0, 0].grid(True, alpha=0.3, axis='x')

    # Actual vs Predicted
    y_pred = model.fittedvalues
    axes[0, 1].scatter(model.model.endog, y_pred, alpha=0.5, s=20)
    axes[0, 1].plot([model.model.endog.min(), model.model.endog.max()],
                    [model.model.endog.min(), model.model.endog.max()],
                    'r--', linewidth=2)
    axes[0, 1].set_xlabel('Actual Values', fontweight='bold')
    axes[0, 1].set_ylabel('Predicted Values', fontweight='bold')
    axes[0, 1].set_title(f'Actual vs Predicted (R² = {model.rsquared:.3f})', fontweight='bold')
    axes[0, 1].grid(True, alpha=0.3)

    # Residuals plot
    residuals = model.resid
    axes[1, 0].scatter(y_pred, residuals, alpha=0.5, s=20)
    axes[1, 0].axhline(0, color='red', linestyle='--', linewidth=2)
    axes[1, 0].set_xlabel('Fitted Values', fontweight='bold')
    axes[1, 0].set_ylabel('Residuals', fontweight='bold')
    axes[1, 0].set_title('Residual Plot', fontweight='bold')
    axes[1, 0].grid(True, alpha=0.3)

    # Q-Q plot
    stats.probplot(residuals, dist="norm", plot=axes[1, 1])
    axes[1, 1].set_title('Q-Q Plot', fontweight='bold')
    axes[1, 1].grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(os.path.join(output_folder, f"06_regression_diagnostics_{period_label.replace(' ', '_')}.png"), dpi=300, bbox_inches='tight')
    plt.close()
    print(f"✓ Saved: regression diagnostics plot")


def create_weekday_weekend_comparison(df, time_index, period_slice, output_folder, period_label):
    """Compare correlations between weekdays and weekends"""
    df['datetime'] = time_index[period_slice]
    df['weekday'] = df['datetime'].dt.weekday
    df['is_weekend'] = df['weekday'] >= 5

    weekend_corr = df[df['is_weekend']].corr()
    weekday_corr = df[~df['is_weekend']].corr()

    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    sns.heatmap(weekday_corr, annot=True, fmt='.3f', cmap='RdBu_r', center=0,
                square=True, linewidths=1, cbar_kws={"shrink": 0.8}, ax=axes[0],
                vmin=-1, vmax=1)
    axes[0].set_title(f'Weekday Correlation - {period_label}', fontweight='bold')

    sns.heatmap(weekend_corr, annot=True, fmt='.3f', cmap='RdBu_r', center=0,
                square=True, linewidths=1, cbar_kws={"shrink": 0.8}, ax=axes[1],
                vmin=-1, vmax=1)
    axes[1].set_title(f'Weekend Correlation - {period_label}', fontweight='bold')

    plt.tight_layout()
    plt.savefig(os.path.join(output_folder, f"07_weekday_weekend_{period_label.replace(' ', '_')}.png"), dpi=300, bbox_inches='tight')
    plt.close()
    print(f"✓ Saved: weekday vs weekend comparison")


def create_price_regime_comparison(df, output_folder, period_label):
    """Compare correlations in high-price vs normal-price regimes"""
    threshold = df["price"].quantile(0.9)
    df["high_price"] = df["price"] > threshold

    high_price_corr = df[df["high_price"]].corr()
    normal_price_corr = df[~df["high_price"]].corr()

    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    sns.heatmap(normal_price_corr, annot=True, fmt='.3f', cmap='RdBu_r', center=0,
                square=True, linewidths=1, cbar_kws={"shrink": 0.8}, ax=axes[0],
                vmin=-1, vmax=1)
    axes[0].set_title(f'Normal Price Regime (0-90th percentile) - {period_label}', fontweight='bold')

    sns.heatmap(high_price_corr, annot=True, fmt='.3f', cmap='RdBu_r', center=0,
                square=True, linewidths=1, cbar_kws={"shrink": 0.8}, ax=axes[1],
                vmin=-1, vmax=1)
    axes[1].set_title(f'High Price Regime (>90th percentile: €{threshold:.2f}/MWh) - {period_label}', fontweight='bold')

    plt.tight_layout()
    plt.savefig(os.path.join(output_folder, f"08_price_regimes_{period_label.replace(' ', '_')}.png"), dpi=300, bbox_inches='tight')
    plt.close()
    print(f"✓ Saved: price regime comparison (threshold: €{threshold:.2f}/MWh)")


def create_summary_report(df, model, period_label, output_folder):
    """Create a text summary report"""
    report_path = os.path.join(output_folder, f"00_SUMMARY_REPORT_{period_label.replace(' ', '_')}.txt")

    with open(report_path, 'w') as f:
        f.write("=" * 70 + "\n")
        f.write(f"CORRELATION AND REGRESSION ANALYSIS REPORT\n")
        f.write(f"Period: {period_label}\n")
        f.write("=" * 70 + "\n\n")

        f.write("1. DESCRIPTIVE STATISTICS\n")
        f.write("-" * 70 + "\n")
        f.write(df.describe().to_string())
        f.write("\n\n")

        f.write("2. PEARSON CORRELATION MATRIX\n")
        f.write("-" * 70 + "\n")
        f.write(df.corr(method='pearson').to_string())
        f.write("\n\n")

        f.write("3. SPEARMAN CORRELATION MATRIX\n")
        f.write("-" * 70 + "\n")
        f.write(df.corr(method='spearman').to_string())
        f.write("\n\n")

        f.write("4. MULTIPLE REGRESSION RESULTS\n")
        f.write("-" * 70 + "\n")
        f.write(model.summary().as_text())
        f.write("\n\n")

        f.write("5. MODEL INTERPRETATION\n")
        f.write("-" * 70 + "\n")
        f.write(f"R-squared: {model.rsquared:.4f} ({model.rsquared*100:.2f}% variance explained)\n")
        f.write(f"Adjusted R-squared: {model.rsquared_adj:.4f}\n")
        f.write(f"F-statistic: {model.fvalue:.2f} (p-value: {model.f_pvalue:.2e})\n")
        f.write(f"\nPrice coefficient: {model.params['price']:.4f}\n")
        f.write(f"  - Interpretation: 1 unit increase in price → {model.params['price']:.4f} change in flexibility\n")
        f.write(f"\nHeat demand coefficient: {model.params['heat_demand']:.4f}\n")
        f.write(f"  - Interpretation: 1 unit increase in heat demand → {model.params['heat_demand']:.4f} change in flexibility\n")

    print(f"✓ Saved: summary report")
    return report_path


def main():
    """Main execution function"""
    print("\n" + "=" * 70)
    print("CORRELATION AND REGRESSION VISUALIZATION TOOL")
    print("=" * 70 + "\n")

    # Load data
    print("Loading data...")
    flexibility, MT_demand, price, time_index = load_data(case_folder, profiles_folder)

    # Get period indices
    period_slice, period_label = get_period_indices(plot_day, plot_month, plot_week, time_index)

    # Create analysis dataframe
    df = pd.DataFrame({
        "flexibility": flexibility[period_slice],
        "price": price[period_slice],
        "heat_demand": MT_demand[period_slice]
    }).dropna()

    print(f"Analyzing {period_label} ({len(df)} data points)\n")

    # Standardize for regression
    scaler = StandardScaler()
    df_scaled = pd.DataFrame(
        scaler.fit_transform(df),
        columns=df.columns
    )

    # Fit regression model
    X = df_scaled[["price", "heat_demand"]]
    X = sm.add_constant(X)
    y = df_scaled["flexibility"]
    model = sm.OLS(y, X).fit()

    # Generate visualizations
    print("Generating visualizations:\n")

    create_correlation_heatmap(df, output_folder, period_label)
    create_scatter_plots(df, output_folder, period_label)
    create_distribution_plots(df, output_folder, period_label)
    create_time_series_plot(df, time_index, period_slice, output_folder, period_label)
    create_lagged_correlation_plot(df, output_folder, period_label)
    create_regression_summary_plot(model, output_folder, period_label)
    create_weekday_weekend_comparison(df, time_index, period_slice, output_folder, period_label)
    create_price_regime_comparison(df, output_folder, period_label)
    report_path = create_summary_report(df, model, period_label, output_folder)

    print("\n" + "=" * 70)
    print(f"✓ ALL VISUALIZATIONS COMPLETE")
    print(f"Output folder: {output_folder}")
    print(f"Summary report: {report_path}")
    print("=" * 70 + "\n")

    # Print correlation and regression summaries to console
    print("\n--- QUICK SUMMARY ---\n")
    print("Pearson Correlation:")
    print(df.corr())
    print("\nRegression Summary:")
    print(model.summary())


if __name__ == "__main__":
    main()
