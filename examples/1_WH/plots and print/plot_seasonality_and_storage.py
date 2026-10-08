
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import os
# Colorblind-friendly color palette
colorblind_palette = [
    "#377eb8",  # blue
    "#ff7f00",  # orange
    "#4daf4a",  # green
    "#f781bf",  # pink
    "#a65628",  # brown
    "#984ea3",  # purple
    "#999999",  # grey
    "#e41a1c",  # red
    "#dede00",  # yellow
]


# Always save plots to 'plots and print' folder
plots_path = os.path.join(os.path.dirname(__file__), 'plots')
# Get the example root (parent of 'plots and print')
example_root = os.path.dirname(os.path.dirname(__file__))
results_path = os.path.join(example_root, 'results')
loads_file = os.path.join(results_path, 'loads-TS.csv')
tech_file = os.path.join(results_path, 'tech-TS.csv')

# Read loads data (first 7 rows are headers, then data)
df_loads = pd.read_csv(loads_file, skiprows=7, header=None)
# Read tech data (first 10 rows are headers, then data)
df_tech = pd.read_csv(tech_file, skiprows=10, header=None)

# Use first column as time
time = pd.to_numeric(df_loads.iloc[:, 0], errors='coerce')
# Convert relevant columns to numeric, coerce errors
for col in [2, 3, 4, 7, 8, 9]:
    df_loads.iloc[:, col] = pd.to_numeric(df_loads.iloc[:, col], errors='coerce')

# Align number of rows between df_loads and df_tech
min_len = min(len(df_loads), len(df_tech))
df_loads = df_loads.iloc[:min_len, :]
df_tech = df_tech.iloc[:min_len, :]
time = time.iloc[:min_len]


# Plot LT, MT, HT demand as stacked area plot, ensuring numeric and no NaNs
lt_demand = pd.to_numeric(-df_loads.iloc[:, 7], errors='coerce').fillna(0).astype(float)
mt_demand = pd.to_numeric(-df_loads.iloc[:, 8], errors='coerce').fillna(0).astype(float)
ht_demand = pd.to_numeric(-df_loads.iloc[:, 9], errors='coerce').fillna(0).astype(float)

plt.figure(figsize=(15, 5))
plt.stackplot(time, lt_demand, mt_demand, ht_demand, labels=['LT Demand', 'MT Demand', 'HT Demand'], colors=[colorblind_palette[0], colorblind_palette[1], colorblind_palette[5]])
plt.title('Seasonality of Energy System: Heating Demands (Stacked)')
plt.xlabel('Time Step')
plt.ylabel('Load (kW)')
plt.legend(loc='upper right')
plt.tight_layout()
plt.savefig(os.path.join(plots_path, 'seasonality_heating_demands.png'))
plt.close()

# --- Supply by Technology for LT, MT, HT ---
# Get supply columns for LT, MT, HT (columns 3, 4, 5 in 0-index: 2, 3, 4)
lt_supply = df_loads.iloc[:, 2]
mt_supply = df_loads.iloc[:, 3]
ht_supply = df_loads.iloc[:, 4]
total_supply = lt_supply + mt_supply + ht_supply

# For supply by technology, use tech-TS.csv headers

# Read header, Ec, and Tech rows, handling possible NaNs

# Read header rows: 0-based index
header = pd.read_csv(tech_file, nrows=1, header=None).iloc[0]
ec_names = pd.read_csv(tech_file, skiprows=4, nrows=1, header=None).iloc[0]  # Ec row is line 5 (0-based index 4)
tech_names = pd.read_csv(tech_file, skiprows=5, nrows=1, header=None).iloc[0]  # Tech row is line 6 (0-based index 5)

# Only use columns where tech_names is not NaN
valid_cols = [i for i, t in enumerate(tech_names) if pd.notna(t)]

# Find all columns that are conversion tech outputs to LT, MT, HT


lt_cols = [i for i in valid_cols if str(ec_names[i]).strip() == 'LT' and 'Out' in str(header[i])]
mt_cols = [i for i in valid_cols if str(ec_names[i]).strip() == 'MT' and 'Out' in str(header[i])]
ht_cols = [i for i in valid_cols if str(ec_names[i]).strip() == 'HT' and 'Out' in str(header[i])]

# Get unique techs for legend
lt_techs = [tech_names[i] for i in lt_cols]
mt_techs = [tech_names[i] for i in mt_cols]
ht_techs = [tech_names[i] for i in ht_cols]

# Prepare supply shares for each tech
def get_supply_shares(df, cols, total):
    shares = []
    for i in cols:
        val = pd.to_numeric(df.iloc[:, i], errors='coerce').fillna(0).astype(float)
        shares.append(val)
    shares = np.array(shares, dtype=float)
    # Normalize by total supply (avoid division by zero)
    total = np.where(total == 0, 1, total)
    result = shares / total
    # Replace any NaN or inf with 0
    result = np.nan_to_num(result, nan=0.0, posinf=0.0, neginf=0.0)
    return result

df_tech = df_tech.reset_index(drop=True)
lt_shares = get_supply_shares(df_tech, lt_cols, lt_supply.values)
mt_shares = get_supply_shares(df_tech, mt_cols, mt_supply.values)
ht_shares = get_supply_shares(df_tech, ht_cols, ht_supply.values)

# Plot stacked area for each demand type
def plot_supply_shares(time, shares, techs, demand_type):
    plt.figure(figsize=(15, 5))
    # Ensure shares is a 2D float array and each row is 1D float
    shares = np.array(shares, dtype=float)
    shares = [np.array(s, dtype=float).flatten() for s in shares]
    plt.stackplot(time, *shares, labels=techs)
    plt.title(f'Supply Shares by Technology for {demand_type}')
    plt.xlabel('Time Step')
    plt.ylabel('Share of Total Supply')
    plt.legend(loc='upper right', bbox_to_anchor=(1.15, 1))
    plt.tight_layout()
    plt.savefig(os.path.join(plots_path, f'supply_shares_{demand_type}.png'))
    plt.close()

plot_supply_shares(time, lt_shares, lt_techs, 'LT')
plot_supply_shares(time, mt_shares, mt_techs, 'MT')
plot_supply_shares(time, ht_shares, ht_techs, 'HT')

# --- Storage System Usage Timeline ---
# Label storages as TES LT, TES MT, TES HT
tes_labels = ['TES HT', 'TES LT', 'TES MT']
# Find storage columns in order: HT, LT, MT (based on tech-TS.csv header and tech row)
storage_col_indices = []
for label in ['TESHT', 'TESLT', 'TESMT']:
    for i, tech in enumerate(tech_names):
        if tech == label and 'Storage energy' in str(header[i]):
            storage_col_indices.append(i)

plt.figure(figsize=(15, 5))
for idx, label in zip(storage_col_indices, tes_labels):
    plt.plot(df_tech.iloc[:, 0], df_tech.iloc[:, idx], label=label)
plt.title('Storage System Usage Over Time')
plt.xlabel('Time Step')
plt.ylabel('Storage Energy (h*kW)')
plt.legend()
plt.tight_layout()
plt.savefig(os.path.join(plots_path, 'storage_usage_timeline.png'))
plt.close()


print('Graphs created: seasonality_heating_demands.png, supply_shares_LT.png, supply_shares_MT.png, supply_shares_HT.png, storage_usage_timeline.png')


# --- Combined Supply and Demand Plots for LT, MT, HT ---
def plot_combined_supply_demand(time, supply_by_tech, techs, demand, total_supply, demand_label, demand_color, demand_type):
    plt.figure(figsize=(15, 5))
    # Normalize supply by tech so sum matches total_supply at each timestep
    supply = np.array(supply_by_tech, dtype=float)
    # Remove technologies that are never used (all zeros)
    used_mask = np.any(supply != 0, axis=1)
    supply = supply[used_mask]
    techs_used = [t for t, used in zip(techs, used_mask) if used]
    # Recalculate sum after masking
    supply_sum = np.sum(supply, axis=0)
    # Avoid division by zero
    norm_factors = np.ones_like(total_supply)
    nonzero = supply_sum != 0
    norm_factors[nonzero] = total_supply[nonzero] / supply_sum[nonzero]
    norm_factors[~nonzero] = 0
    supply_norm = supply * norm_factors
    # Ensure perfect balancing by recalculating the sum after normalization
    supply_norm_sum = np.sum(supply_norm, axis=0)
    # If any small floating point drift, correct the last tech to absorb the difference
    if supply_norm.shape[0] > 0:
        diff = total_supply - supply_norm_sum
        supply_norm[-1, :] += diff
    supply_norm = [supply_norm[i, :] for i in range(supply.shape[0])]
    labels = techs_used + [demand_label]
    colors = plt.cm.tab20.colors[:len(techs_used)] + (demand_color,)
    plt.stackplot(time, *supply_norm, labels=techs_used, alpha=0.7, colors=colors[:-1])
    plt.stackplot(time, demand, labels=[demand_label], alpha=0.7, colors=[demand_color])
    plt.title(f'Supply by Technology and Demand for {demand_type}')
    plt.xlabel('Time Step')
    plt.ylabel('Load (kW)')
    plt.legend(loc='upper right', bbox_to_anchor=(1.15, 1))
    plt.tight_layout()
    plt.savefig(os.path.join(plots_path, f'combined_supply_demand_{demand_type}.png'))
    plt.close()

# Plot for LT (normalized supply, only Chiller with Input/Result 'result', Tech 'Chiller', Ec 'LT')
input_result = pd.read_csv(tech_file, skiprows=8, nrows=1, header=None).iloc[0]
lt_cols_filtered = [i for i in lt_cols if (tech_names[i] != 'Chiller') or (str(input_result[i]).strip().lower() == 'result' and str(ec_names[i]).strip() == 'LT')]
lt_techs_filtered = [tech_names[i] for i in lt_cols_filtered]
lt_supply_by_tech = [pd.to_numeric(df_tech.iloc[:, i], errors='coerce').fillna(0).astype(float) for i in lt_cols_filtered]
lt_total_supply = pd.to_numeric(df_loads.iloc[:, 2], errors='coerce').fillna(0).astype(float)
plot_combined_supply_demand(
    time,
    lt_supply_by_tech,
    lt_techs_filtered,
    lt_demand,
    lt_total_supply,
    'LT Demand',
    'red',
    'LT'
)
# Plot for MT (normalized supply)
mt_supply_by_tech = [pd.to_numeric(df_tech.iloc[:, i], errors='coerce').fillna(0).astype(float) for i in mt_cols]
mt_total_supply = pd.to_numeric(df_loads.iloc[:, 3], errors='coerce').fillna(0).astype(float)
plot_combined_supply_demand(
    time,
    mt_supply_by_tech,
    mt_techs,
    mt_demand,
    mt_total_supply,
    'MT Demand',
    'orange',
    'MT'
)
# Plot for HT (normalized supply)
ht_supply_by_tech = [pd.to_numeric(df_tech.iloc[:, i], errors='coerce').fillna(0).astype(float) for i in ht_cols]
ht_total_supply = pd.to_numeric(df_loads.iloc[:, 4], errors='coerce').fillna(0).astype(float)
plot_combined_supply_demand(
    time,
    ht_supply_by_tech,
    ht_techs,
    ht_demand,
    ht_total_supply,
    'HT Demand',
    'purple',
    'HT'
)
