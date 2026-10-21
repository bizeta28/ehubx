
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
plot_month = None       # 1-12 (e.g., 1 for Jan, 12 for Dec)
plot_week = 15     # 1-52 (e.g., 5 for week 5)

# Paths
result_file = os.path.join("examples", case_folder, "results", "opt_vars.csv")
output_folder = os.path.join("examples", case_folder, "plots and print", "plots", "other plots")
os.makedirs(output_folder, exist_ok=True)

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

# --- LOAD MT DEMAND + PRICE FIRST ---
profiles_folder = os.path.join("examples", case_folder, "inputs", "basic", "profiles")
demands_path = os.path.join(profiles_folder, "demands.csv")
imports_path = os.path.join(profiles_folder, "imports.csv")

# Read MT demand
demand_columns = ['S_Time', 'HT', 'MT', 'LT', 'IT', 'El']
demands_df = pd.read_csv(demands_path, skiprows=4, header=None, names=demand_columns)
MT_demand = demands_df['MT'].values[:8760]

# Read electricity price
imports_columns = ['S_Time', 'price', 'co2']
imports_df = pd.read_csv(imports_path, skiprows=5, header=None, names=imports_columns)
price = imports_df['price'].values[:8760]

# Time index
time_index = pd.date_range(start='2023-01-01', periods=8760, freq='h')

# --- PERIOD SELECTION ---
def get_period(plot_day=None, plot_week=None, plot_month=None):
    if plot_day is not None:
        start = (plot_day - 1) * 24
        end = start + 24
        label = f"Day_{plot_day}"
    elif plot_month is not None:
        month_starts = pd.date_range('2023-01-01', periods=12, freq='MS')
        month_ends = pd.date_range('2023-01-01', periods=12, freq='ME')
        start = (month_starts[plot_month-1] - time_index[0]).days * 24
        end = (month_ends[plot_month-1] - time_index[0]).days * 24 + 24
        label = month_starts[plot_month-1].strftime('%B')
    elif plot_week is not None:
        start = (plot_week - 1) * 168
        end = start + 168
        label = f"Week_{plot_week}"
    else:
        start, end = 0, 8760
        label = "Full_Year"

    return slice(start, end), label


# --- SELECT PERIOD (use your existing inputs) ---
period_slice, period_label = get_period(plot_day, plot_week, plot_month)

# --- PLOTTING ---
plt.rcParams.update({
    'font.size': 14,
    'axes.labelsize': 20,
    'axes.titlesize': 20,
    'xtick.labelsize': 18,
    'ytick.labelsize': 18,
    'legend.fontsize': 16,
    'legend.title_fontsize': 18
})

# Okabe-Ito colorblind-safe palette
OKABE_ITO = {
    "blue": "#0072B2",
    "orange": "#E69F00",
    "vermillion": "#D55E00",
    "bluish_green": "#009E73",
}

fig, ax1 = plt.subplots(figsize=(18, 6))

# IT load
ax1.plot(time_index[period_slice],
         IT_Profile['var_value'][period_slice],
         label='Original IT Demand Profile',
         color=OKABE_ITO["blue"])

# Flexibility fill
ax1.fill_between(time_index[period_slice],
                 IT_Profile['var_value'][period_slice],
                 Load_shifting_forplot[period_slice],
                 color=OKABE_ITO["orange"],
                 alpha=0.4,
                 label='Activated Flexibility')

# MT demand
ax1.plot(time_index[period_slice],
         MT_demand[period_slice],
         linestyle='--',
         color=OKABE_ITO["vermillion"],
         label='MT Heat Demand')

# Secondary axis for price
ax2 = ax1.twinx()
ax2.plot(time_index[period_slice],
         price[period_slice],
         linestyle=':',
         color=OKABE_ITO["bluish_green"],
         label='Electricity Price')

# --- AXIS FORMATTING ---
if plot_month is None and plot_week is None and plot_day is None:
    month_positions = pd.date_range(start='2023-01-01', periods=12, freq='MS')
    month_labels = ['Jan','Feb','Mar','Apr','May','Jun',
                    'Jul','Aug','Sep','Oct','Nov','Dec']
    ax1.set_xticks(month_positions)
    ax1.set_xticklabels(month_labels)
else:
    if plot_day is not None:
        ax1.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
    else:
        ax1.xaxis.set_major_formatter(mdates.DateFormatter('%d %b'))
    plt.xticks(rotation=45)

# Labels
ax1.set_xlabel('Time', fontsize=20, fontweight='bold')
ax1.set_ylabel('Power (kW)', fontsize=20, fontweight='bold')
ax2.set_ylabel('Electricity Price (CHF/kW)', fontsize=20, fontweight='bold')

# # Title
# plt.title(f'IT Load, Flexibility, MT Demand & Price: {period_label}', fontweight='bold')

# Combined legend
lines_1, labels_1 = ax1.get_legend_handles_labels()
lines_2, labels_2 = ax2.get_legend_handles_labels()
legend = ax1.legend(lines_1 + lines_2, labels_1 + labels_2)
for text in legend.get_texts():
    text.set_fontweight('bold')

# Final touches
ax1.grid(True)
plt.tight_layout()

output_path = os.path.join(os.path.dirname(__file__), 'plots','other plots',
                           f'ITload_and_flexibility_{period_label}.png')
plt.savefig(output_path)

print(f"Plot saved to {output_path}")


# ------------------------------------------------
# --- MT Demand and Electricity Price Plotting ---
# ------------------------------------------------

def plot_MT_demand_and_electricity_price(plot_day=None, plot_week=None, plot_month=None):
    # Paths to profiles
    profiles_folder = os.path.join("examples", case_folder, "inputs", "basic", "profiles")
    demands_path = os.path.join(profiles_folder, "demands.csv")
    imports_path = os.path.join(profiles_folder, "imports.csv")


    # Read MT demand (skip header rows, assign columns)
    demand_columns = ['S_Time', 'HT', 'MT', 'LT', 'IT', 'El']
    demands_df = pd.read_csv(demands_path, skiprows=4, header=None, names=demand_columns)
    MT_demand = demands_df['MT'].values[:8760]

    # Read electricity price (skip header rows, assign columns)
    imports_columns = ['S_Time', 'price', 'co2']
    imports_df = pd.read_csv(imports_path, skiprows=5, header=None, names=imports_columns)
    price = imports_df['price'].values[:8760]

    time_index = pd.date_range(start='2023-01-01', periods=8760, freq='h')

    # Select period
    def get_period():
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

    period_slice, period_label = get_period()

    # --- ADDITIONAL OVERLAYS ---

# Extract same period
MT_period = MT_demand[period_slice]
price_period = price[period_slice]

# Plot MT demand (heat demand) on primary axis
plt.plot(time_index[period_slice],
         MT_period,
         linestyle='--',
         color='red',
         label='MT Heat Demand')

# Secondary axis for electricity price
ax1 = plt.gca()
ax2 = ax1.twinx()

ax2.plot(time_index[period_slice],
         price_period,
         linestyle=':',
         color='green',
         label='Electricity Price')

ax2.set_ylabel('Electricity Price', fontsize=12)

# --- Combine legends from both axes ---
lines_1, labels_1 = ax1.get_legend_handles_labels()
lines_2, labels_2 = ax2.get_legend_handles_labels()
ax1.legend(lines_1 + lines_2, labels_1 + labels_2)

# Plot
fig, ax1 = plt.subplots(figsize=(12, 6))
ax1.plot(time_index[period_slice], MT_demand[period_slice], color="#F1014D", label="MT Demand")
ax1.set_ylabel("MT Demand (kW)", color="#F1014D", fontsize=12)
ax1.tick_params(axis='y', labelcolor="#F1014D")

ax2 = ax1.twinx()
ax2.plot(time_index[period_slice], price[period_slice], color="#01F18F", label="Electricity Price")
ax2.set_ylabel("Electricity Price (CHF/kWh)", color="#01F18F", fontsize=12)
ax2.tick_params(axis='y', labelcolor="#01F18F")

if plot_month is None and plot_week is None and plot_day is None:
    month_positions = pd.date_range(start='2023-01-01', periods=12, freq='MS')
    month_labels = ['Jan','Feb','Mar','Apr','May','Jun',
                            'Jul','Aug','Sep','Oct','Nov','Dec']
    ax1.set_xticks(month_positions)
    ax1.set_xticklabels(month_labels)
else:
    ax1.tick_params(axis='x', rotation=45)

    plt.title(f"MT Demand & Electricity Price: {period_label}")
    fig.tight_layout()
    out_path = os.path.join(output_folder, f"MTdemand_electricityprice_{period_label}.png")
    plt.savefig(out_path)
    print(f"MT demand & electricity price plot saved to {out_path}")



# Always create the MT Demand and Electricity Price and Flexibility plot with current period selection
# (moved below function definition)


# ------------------------------------------------
# --- MT Demand and Electricity Price and Flexibility Plotting ---
# ------------------------------------------------

def plot_MT_with_flex_overlay(plot_day=None, plot_week=None, plot_month=None):

    # -------------------------
    # PATHS
    # -------------------------
    profiles_folder = os.path.join("examples", case_folder, "inputs", "basic", "profiles")
    demands_path = os.path.join(profiles_folder, "demands.csv")
    imports_path = os.path.join(profiles_folder, "imports.csv")

    result_file = os.path.join("examples", case_folder, "results", "opt_vars.csv")

    # -------------------------
    # LOAD DATA
    # -------------------------
    data = pd.read_csv(result_file, low_memory=False)

    demand_columns = ['S_Time', 'HT', 'MT', 'LT', 'IT', 'El']
    demands_df = pd.read_csv(demands_path, skiprows=4, header=None, names=demand_columns)
    imports_df = pd.read_csv(imports_path, skiprows=5, header=None, names=['S_Time', 'price', 'co2'])

    MT_demand = demands_df['MT'].values[:8760]
    price = imports_df['price'].values[:8760]

    # -------------------------
    # FLEX DATA (same logic as your first plot)
    # -------------------------
    def expand(df, var_name):
        full_range = pd.DataFrame({'S_Time': range(1, 8761)})
        out = pd.merge(full_range, df, on='S_Time', how='left')
        out['var_value'] = out['var_value'].fillna(0)
        return out['var_value'].values

    IT_Profile = data[(data['S_Ec'] == 'IT') & (data['var_name'] == 'V_DemandSupply')]
    Load_shifting = data[(data['S_Ec'] == 'IT') & (data['var_name'] == 'V_LoadShifting')]

    IT_Profile = expand(IT_Profile, 'V_DemandSupply')
    Load_shifting = expand(Load_shifting, 'V_LoadShifting')

    flex_used = Load_shifting  # OR (IT_Profile + Load_shifting) depending on definition

    # -------------------------
    # TIME INDEX
    # -------------------------
    time_index = pd.date_range(start='2023-01-01', periods=8760, freq='h')

    # -------------------------
    # PERIOD SELECTION
    # -------------------------
    def get_period():
        if plot_day is not None:
            start = (plot_day - 1) * 24
            end = start + 24
            label = f"Day_{plot_day}"
        elif plot_week is not None:
            start = (plot_week - 1) * 168
            end = start + 168
            label = f"Week_{plot_week}"
        elif plot_month is not None:
            month_starts = pd.date_range('2023-01-01', periods=12, freq='MS')
            month_ends = pd.date_range('2023-01-01', periods=12, freq='ME')
            start = (month_starts[plot_month-1] - time_index[0]).days * 24
            end = (month_ends[plot_month-1] - time_index[0]).days * 24 + 24
            label = month_starts[plot_month-1].strftime('%B')
        else:
            start, end = 0, 8760
            label = "Full_Year"

        return slice(start, end), label

    sl, label = get_period()

    # -------------------------
    # PLOT
    # -------------------------
    fig, ax1 = plt.subplots(figsize=(12, 6))

    # MT Demand
    l1, = ax1.plot(time_index[sl], MT_demand[sl],
                  color="#F1014D", label="MT Demand")
    ax1.set_ylabel("Energy (kW)", color="#F1014D")
    ax1.tick_params(axis='y', labelcolor="#F1014D")

    # Flex overlay (same axis, visually comparable)
    l2 = ax1.fill_between(time_index[sl],
                         MT_demand[sl],
                         MT_demand[sl] - flex_used[sl],
                         color="#F18F01",
                         alpha=0.4,
                         label="Flexibility Activation")

    # Electricity price (secondary axis)
    ax2 = ax1.twinx()
    l3, = ax2.plot(time_index[sl], price[sl],
                  color="#01A3F1", label="Electricity Price")
    ax2.set_ylabel("Price (CHF/kWh)", color="#01A3F1")
    ax2.tick_params(axis='y', labelcolor="#01A3F1")

    # Add combined legend
    from matplotlib.patches import Patch
    handles = [l1, Patch(facecolor="#F18F01", edgecolor="#F18F01", alpha=0.4, label="Flexibility Activation"), l3]
    labels = ["MT Demand", "Flexibility Activation", "Electricity Price"]
    ax1.legend(handles, labels, loc="upper left")

    # -------------------------
    # FORMATTING
    # -------------------------
    ax1.set_title(f"MT Demand + Flexibility + Electricity Price ({label})")
    ax1.set_xlabel("Time")

    if plot_day is None and plot_week is None and plot_month is None:
        month_positions = pd.date_range('2023-01-01', periods=12, freq='MS')
        ax1.set_xticks(month_positions)
        ax1.set_xticklabels(['Jan','Feb','Mar','Apr','May','Jun',
                             'Jul','Aug','Sep','Oct','Nov','Dec'])
    else:
        ax1.tick_params(axis='x', rotation=45)

    ax1.grid(True)
    fig.tight_layout()

    out_path = os.path.join(output_folder,
                            f"MT_flex_price_overlay_{label}.png")
    plt.savefig(out_path, dpi=300)

    print(f"Saved: {out_path}")
    plt.show()


# --- Call the function after it is defined ---
plot_MT_with_flex_overlay(plot_day=plot_day, plot_week=plot_week, plot_month=plot_month)
