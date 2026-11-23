"""
Sanity plots for the backlog mode of load shifting (spec 05 v3).

Run after a case in backlog mode has been solved. Place this file in the case's
'plots and print' folder (same layout as examples/1_WH/plots and print).

Plots (saved to 'plots and print/plots'):
  1. backlog_deadline_<ls>.png   backlog B(t), overdue L(t) and the deadline (one week)
  2. shift_drivers_<season>.png  shift s(t) next to El price, PV and heat demand (one week)
  3. delay_histogram.png         IT energy by hours of delay (FIFO reconstruction)

All time steps are model hours (UTC, t = 1 is 1 Jan 00:00-01:00).
"""

import os
from collections import deque

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import yaml

# Colorblind-friendly color palette (same as plot_seasonality_and_storage.py)
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

# --- Settings -------------------------------------------------------------
# First time step of the sample weeks (1-based model hours, UTC)
WEEKS = {
    "winter": 24 * 14 + 1,   # 15 Jan
    "summer": 24 * 196 + 1,  # 15 Jul
}
WEEK_FOR_BACKLOG = "winter"
WEEK_LENGTH = 7 * 24
TOL = 1e-6  # kWh, below this a value counts as zero

# --- Paths (same convention as the existing scripts) ----------------------
script_dir = os.path.dirname(os.path.abspath(__file__))
plots_path = os.path.join(script_dir, "plots")
example_root = os.path.dirname(script_dir)
results_path = os.path.join(example_root, "results")
demands_yaml = os.path.join(example_root, "inputs", "basic", "demands.yaml")
os.makedirs(plots_path, exist_ok=True)


# --- Reading ehubX result files -------------------------------------------
def read_ts(path):
    """Return (header, data) of an ehubX *-TS.csv file.

    header: DataFrame indexed by the header row names (Entry, Unit, Ec, ...),
            one column per data column.
    data:   DataFrame of floats, index = time step.
    The number of header rows differs between files, so it is detected:
    header rows end at the first row whose first field is a number.
    """
    raw = pd.read_csv(path, header=None, dtype=str, keep_default_na=False)
    first = pd.to_numeric(raw.iloc[:, 0], errors="coerce")
    n_head = int(first.notna().idxmax())
    header = raw.iloc[:n_head, 1:]
    header.index = raw.iloc[:n_head, 0].str.strip()
    data = raw.iloc[n_head:, 1:].apply(pd.to_numeric, errors="coerce").fillna(0.0)
    data.index = first.iloc[n_head:].astype(int).values
    return header, data


def find_col(header, entry, **rows):
    """Return the single column whose 'Entry' contains `entry` and whose other
    header rows equal the given values (e.g. Ec='IT', **{'Load shift': 'ls1'})."""
    mask = header.loc["Entry"].str.contains(entry, regex=False)
    for row, val in rows.items():
        mask &= header.loc[row].str.strip() == val
    cols = header.columns[mask.values]
    if len(cols) != 1:
        raise KeyError(f"Expected 1 column for {entry} {rows}, found {len(cols)}")
    return cols[0]


def backlog_settings():
    """Read window / deadline_hours of every backlog-mode entry in demands.yaml."""
    with open(demands_yaml, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    out = {}
    for ls in cfg.get("load_shifting", []):
        if ls.get("mode") != "backlog":
            continue
        entry = {"type": ls["deadline_type"]}
        if entry["type"] == "rolling":
            entry["W"] = int(round(float(str(ls["window"]).split()[0])))
        else:
            entry["hours"] = [int(h) for h in ls["deadline_hours"]]
        out[str(ls["load_shift_id"])] = entry
    if not out:
        raise ValueError("No load_shifting entry with mode: backlog in demands.yaml")
    return out


settings = backlog_settings()
hdr_l, df_l = read_ts(os.path.join(results_path, "loads-TS.csv"))
hdr_i, df_i = read_ts(os.path.join(results_path, "import_export-TS.csv"))
hdr_t, df_t = read_ts(os.path.join(results_path, "tech-TS.csv"))
time = df_l.index.values

series = {}
for ls in settings:
    series[ls] = {
        "B": df_l[find_col(hdr_l, "(V_LoadShiftingBacklog)", **{"Load shift": ls})].values,
        "L": df_l[find_col(hdr_l, "(V_LoadShiftingLate)", **{"Load shift": ls})].values,
        "s": df_l[find_col(hdr_l, "(V_LoadShifting)", **{"Load shift": ls})].values,
        # arrival of deferrable work theta_w * a_w(t); equals arrival_flex by spec (4)
        "q": df_l[find_col(hdr_l, "(max_below_abs)", **{"Load shift": ls})].values,
    }

price = df_i[find_col(hdr_i, "Import price", Ec="El")].values
pv = df_t[find_col(hdr_t, "output", Tech="PV", Ec="El")].values
heat = sum(df_l[find_col(hdr_l, "Demand-profile", Ec=ec)].values for ec in ("MT", "HT"))

# --- Console check: lateness must be zero (spec 05 v3, (8)) ---------------
for ls, d in series.items():
    print(f"{ls}: sum L = {d['L'].sum():.3e} kWh*h, max B = {d['B'].max():.2f} kWh, "
          f"shifted = {np.clip(-d['s'], 0, None).sum() / 1000:.2f} MWh/a")
    if d["L"].sum() > TOL:
        print(f"  WARNING {ls}: overdue backlog is not zero -> check pi_w or the model")


def week_slice(start):
    return slice(start - 1, start - 1 + WEEK_LENGTH)


# --- Plot 1: backlog vs deadline ------------------------------------------
sl = week_slice(WEEKS[WEEK_FOR_BACKLOG])
for ls, d in series.items():
    st = settings[ls]
    plt.figure(figsize=(15, 5))
    plt.plot(time[sl], d["B"][sl], label="Backlog B(t)", color=colorblind_palette[0])
    if st["type"] == "rolling":
        W = st["W"]
        limit = pd.Series(d["q"]).rolling(W, min_periods=1).sum().values
        plt.plot(time[sl], limit[sl], label=f"Rolling limit (arrivals of last {W} h)",
                 color=colorblind_palette[1], linestyle="--")
    else:
        # deadline at the end of hour t with t mod 24 == h (spec 05 v3, (3b))
        dl = [t for t in time[sl] if t % 24 in st["hours"]]
        for k, t in enumerate(dl):
            plt.axvline(t, color=colorblind_palette[1], linestyle="--",
                        label="Deadline (queue empty)" if k == 0 else None)
    plt.plot(time[sl], d["L"][sl], label="Overdue L(t)", color=colorblind_palette[7])
    plt.title(f"Backlog and Deadline for {ls} ({st['type']}, {WEEK_FOR_BACKLOG} week)")
    plt.xlabel("Time Step")
    plt.ylabel("Energy (kWh)")
    plt.legend(loc="upper right", bbox_to_anchor=(1.15, 1))
    plt.tight_layout()
    plt.savefig(os.path.join(plots_path, f"backlog_deadline_{ls}.png"))
    plt.close()


# --- Plot 2: shift vs drivers ---------------------------------------------
for season, start in WEEKS.items():
    sl = week_slice(start)
    fig, axes = plt.subplots(3, 1, figsize=(15, 9), sharex=True)
    for k, (ls, d) in enumerate(series.items()):
        axes[0].step(time[sl], d["s"][sl], where="mid", label=ls,
                     color=colorblind_palette[k % len(colorblind_palette)])
    axes[0].axhline(0, color="black", linewidth=0.5)
    axes[0].set_ylabel("Shift s(t) (kW)")
    axes[0].set_title(f"Load Shifting and its Drivers ({season} week)")
    axes[1].step(time[sl], price[sl], where="mid", color=colorblind_palette[6], label="El import price")
    axes[1].set_ylabel("Price (CHF/kWh)")
    axes[2].plot(time[sl], pv[sl], color=colorblind_palette[8], label="PV El output")
    axes[2].plot(time[sl], heat[sl], color=colorblind_palette[5], label="MT + HT demand")
    axes[2].set_ylabel("Load (kW)")
    axes[2].set_xlabel("Time Step")
    for ax in axes:
        ax.legend(loc="upper right", bbox_to_anchor=(1.15, 1))
    plt.tight_layout()
    plt.savefig(os.path.join(plots_path, f"shift_drivers_{season}.png"))
    plt.close()


# --- Plot 3: delay histogram (FIFO) ---------------------------------------
def fifo_delays(q, s):
    """Energy executed per delay (h), first-come-first-served.

    Arrivals q(t) = theta*a(t) [kWh in hour t]; executed x(t) = q(t) + s(t).
    Work arriving in hour tau and run in hour t has delay t - tau.
    """
    queue = deque()  # [arrival hour, remaining kWh]
    delays = {}
    for t, (qt, st) in enumerate(zip(q, s)):
        if qt > TOL:
            queue.append([t, qt])
        x = max(qt + st, 0.0)
        while x > TOL and queue:
            tau, rem = queue[0]
            take = min(rem, x)
            delays[t - tau] = delays.get(t - tau, 0.0) + take
            x -= take
            if rem - take > TOL:
                queue[0][1] = rem - take
            else:
                queue.popleft()
    return delays


plt.figure(figsize=(15, 5))
n = len(series)
width = 0.8 / n
max_delay = 0
for k, (ls, d) in enumerate(series.items()):
    dl = fifo_delays(d["q"], d["s"])
    h = np.array(sorted(dl))
    e = np.array([dl[i] for i in h]) / 1000  # MWh
    max_delay = max(max_delay, h.max())
    plt.bar(h + (k - (n - 1) / 2) * width, e, width=width, label=ls,
            color=colorblind_palette[k % len(colorblind_palette)])
    if settings[ls]["type"] == "rolling":
        plt.axvline(settings[ls]["W"] + 0.5, linestyle="--",
                    color=colorblind_palette[k % len(colorblind_palette)],
                    label=f"{ls}: W = {settings[ls]['W']} h")
plt.title("Delay of Deferrable IT Work (FIFO)")
plt.xlabel("Delay (h)")
plt.ylabel("Energy (MWh/a)")
plt.yscale("log")
plt.xlim(-0.5, max_delay + 1)
plt.legend(loc="upper right", bbox_to_anchor=(1.15, 1))
plt.tight_layout()
plt.savefig(os.path.join(plots_path, "delay_histogram.png"))
plt.close()

print("Graphs created: backlog_deadline_<ls>.png, shift_drivers_winter.png, "
      "shift_drivers_summer.png, delay_histogram.png")
