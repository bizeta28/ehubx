# Workload flexibility: formulation v3

**Status:** v3 approved by Bea, 13 Nov 2026. Replaces v2 (approved 13 Nov 2026) in `docs/semester_project/formulation/05_workload_flexibility.md`.
**Changes from v2:** $\rho_w$ and constraint (5) dropped; hard deadlines (large $\pi_w$); calendar convention and model time base (UTC) fixed; rolling-window reading confirmed; reporting of system cost without penalties; §6 decisions settled; base case and run setup added (§6).
**Code basis:** `bizeta28/ehubx`, branch `semester-project`, backlog mode as implemented on 13 Nov (`CHANGES.md`). Base case `examples/4_WH+PV+DHN+Flex_fix1+3`.

---

## 1. Idea in one paragraph

IT work arrives as an hourly power profile per archetype $w$. A share $\theta_w$ of it can be deferred, never advanced. Deferred work waits in a backlog that must be cleared by a deadline. For **rolling** archetypes (continuous arrivals: queued batch/HPC jobs) the deadline is $W_w$ hours after arrival. For **calendar** archetypes (scheduled batch: backups, nightly ETL) it is a fixed clock time. Catch-up is limited only by the DC capacity, which all archetypes share. Deadlines are effectively hard: a large lateness penalty $\pi_w$ keeps the model always feasible, and zero lateness is checked in every run. A tiny cost on the backlog ($\varepsilon$) stops the solver from shifting work for no reason.

---

## 2. Notation

### Time base

Model time is **UTC without daylight saving**. Hour $t$ covers $[t-1, t)$ h after 1 Jan 00:00 UTC; $B_w(t)$ is the backlog at the end of hour $t$. Evidence (time-base check, 13 Nov): the solar profile peaks within ≈4 min of solar noon in UTC in every month with no DST jump; the price and building-El morning ramps step by 1 h at the 2024 DST dates, i.e. local behaviour recorded in UTC. IT, MT, LT have no clock-driven ramp and are assumed to share this base (unverified).

### Sets

| Symbol | Meaning |
|---|---|
| $t \in \mathcal{T} = \{1,\dots,8760\}$ | hours, chronological, $\Delta t = 1$ h, UTC |
| $w \in \mathcal{W} = \mathcal{W}^R \cup \mathcal{W}^C$ | workload archetypes: rolling ($R$) or calendar ($C$) deadline |
| $\mathcal{T}^D_w = \{t : t \bmod 24 = h^D_w\}$ | deadline hours of calendar archetype $w$: end of hour $t$ is $h^D_w$:00 UTC |

### Parameters

| Symbol | Unit | Meaning | Value / status |
|---|---|---|---|
| $a_w(t)$ | kW | IT power demand of archetype $w$ as it arrives; $\sum_w a_w(t) = d_{IT}(t)$ | $\alpha_w\, d_{IT}(t)$; $\alpha_w$ placeholder (§6) |
| $\theta_w$ | – | deferrable share of $a_w$ | placeholder, then literature anchors + sweep |
| $W_w$ | h | maximum delay of rolling archetype $w$ (integer, $\ge 1$) | placeholder, then literature anchors + sweep |
| $h^D_w$ | h | calendar deadline, clock hour in model time (UTC) | 5 (= 06:00 CET) |
| $\pi_w$ | CHF/(kWh·h) | lateness penalty | 10 (effectively hard, see (8)) |
| $\varepsilon$ | CHF/(kWh·h) | tie-break cost on backlog | $10^{-4}$, check by halving |
| $Cap_{DC}$ | kW | DC IT capacity | fixed at 20 kW (baseline) |

### Variables (all $\ge 0$ unless stated)

| Symbol | Unit | Meaning |
|---|---|---|
| $x_w(t)$ | kW | deferrable work executed in hour $t$ |
| $s_w(t) = x_w(t) - \theta_w a_w(t)$ | kW, free sign | shift relative to arrival (`V_LoadShifting`) |
| $B_w(t)$ | kWh | backlog at end of hour $t$ |
| $L_w(t)$ | kWh | backlog past its deadline (lateness slack) |

---

## 3. Constraints and their meaning

### (1) Backlog balance

$$B_w(t) = B_w(t-1) - s_w(t)\,\Delta t, \qquad B_w(0) = 0$$

*Meaning:* queue bookkeeping; $B_w(t) = -\sum_{\tau \le t} s_w(\tau)\,\Delta t$.

### (2) Delay-only

$$B_w(t) \ge 0 \qquad \forall w, t$$

*Meaning:* work can't run before it arrives.

### (3a) Rolling deadline ($w \in \mathcal{W}^R$)

$$B_w(t) \le \sum_{\tau = \max(1,\,t-W_w+1)}^{t} \theta_w a_w(\tau)\,\Delta t + L_w(t) \qquad \forall t$$

*Meaning:* the queue may only hold work that arrived in the last $W_w$ hours. **$W_w$ is the maximum delay in hours:** work arriving in hour $\tau$ leaves the right-hand side at $t = \tau + W_w$, so it may still run *in* hour $\tau + W_w$ (confirmed 13 Nov; pinned by the unit tests). A literature deadline "done within $D$ h of submission" maps to $W_w = D - 1$. No flexibility is represented by $\theta_w = 0$, not $W_w = 0$ (code requires $W_w \ge 1$).

### (3b) Calendar deadline ($w \in \mathcal{W}^C$)

$$B_w(t) \le L_w(t) \qquad \forall t \in \mathcal{T}^D_w$$

*Meaning:* the queue is empty at $h^D_w$:00 model time. With $h^D_w = 5$ that is 06:00 CET in winter and 07:00 CEST in summer (1 h late in summer, accepted as a limitation). Implementation: constrain hours with $t \bmod 24 = h^D_w$, i.e. $(t-1) \bmod 24 = h^D_w - 1$. **Code change needed:** v2 code constrains $(t-1) \bmod 24 = h^D_w$ (empty one hour later).

### (4) Lower bound on execution

$$x_w(t) \ge 0 \;\Longleftrightarrow\; s_w(t) \ge -\theta_w a_w(t)$$

### (5) DC capacity (shared hardware; replaces the per-archetype cap of v2)

$$P_{IT}(t) = d_{IT}(t) + \sum_w s_w(t) \le Cap_{DC}$$

*Meaning:* all archetypes run on the same servers, so the only limit on catch-up is the DC's IT capacity. Enforced by the `DC` conversion tech; **$Cap_{DC}$ fixed** (cap_min = cap_max = 20 kW) because DC capex is not costed. Assumption to state in the report: shared hardware, no dedicated per-archetype capacity.

### (6) Closure

$$B_w(T) = 0 \;\Longleftrightarrow\; \sum_t s_w(t)\,\Delta t = 0$$

### (7) Objective

$$\min \; TAC \;+\; \sum_{w,t} \pi_w\, L_w(t) \;+\; \varepsilon \sum_{w,t} B_w(t)$$

### (8) Choice of $\pi_w$ (hard deadlines)

Delaying 1 kWh of IT work by 1 h saves at most the cost of serving it in one hour rather than another: ≤ max El price × El per kWh of IT incl. cooling + avoided HT import × recoverable heat ≈ $0.49 \times 1.5 + 0.19 \times 1.4 \approx 1$ CHF/(kWh·h). $\pi_w = 10$ CHF/(kWh·h) dominates this by an order of magnitude. Since $s_w \equiv 0$ is always feasible, every run must give $\sum_{w,t} L_w(t) = 0$; a non-zero value is a bug or a too-small $\pi_w$, not a result. Tardiness vs SLA form: moot with hard deadlines; the per kWh·h form stays.

### Feasibility

$s_w \equiv 0$ gives $B = L = 0$ and satisfies (5) since $d_{IT}(t) \le Cap_{DC}$. Always feasible.

---

## 4. Mapping onto ehubX (delta to v2 code)

| Item | v2 code | v3 |
|---|---|---|
| (5) hardware cap $\rho_w$ | `max_above_abs` $= \rho_w \max a_w - a_w(t)$ | drop. If `max_above_abs` is mandatory, set it non-binding: $Cap_{DC} - d_{IT}(t)$. Claude Code: check whether the column can be omitted |
| (3b) calendar test | `(t-1) % 24 == h` | `t % 24 == h` (empty at h:00) |
| `deadline_hours` | hour of day | clock hour in model time (UTC) by which the queue is empty |
| YAML `late_cost` | sketch said `1 CHF/kWh` | `10 CHF/(kWh*h)` |
| Reporting | penalties inside `V_SystemCost` | write $TAC_{sys} = $ `V_SystemCost` − `V_LoadShiftingCostLate` − `V_LoadShiftingCostBacklog` as a result row, plus $\sum L$ and $\varepsilon\sum B$. No subtraction by hand in post-processing |

Unchanged from v2: `mode: backlog`, `arrival_flex` profile, $B$/$L$ variables, (1), (3a), interval constraints skipped, chronology guard, `fix_cost = 0`.

### Input sketch (`demands.yaml`, placeholder values)

```yaml
load_shifting:
- load_shift_id: batch_rolling
  stages: S1
  hubs: H1
  ec: IT
  mode: backlog
  deadline_type: rolling
  window: 24 h                     # max delay W_w
  late_cost: 10 CHF/(kWh*h)        # pi_w, effectively hard
  backlog_cost: 0.0001 CHF/(kWh*h) # epsilon
  profile_path: profiles/loadshifting_profiles.csv   # arrival_flex, max_below_abs (= arrival_flex)

- load_shift_id: batch_calendar
  stages: S1
  hubs: H1
  ec: IT
  mode: backlog
  deadline_type: calendar
  deadline_hours: [5]              # empty at 05:00 UTC = 06:00 CET
  late_cost: 10 CHF/(kWh*h)
  backlog_cost: 0.0001 CHF/(kWh*h)
  profile_path: profiles/loadshifting_profiles.csv
```

### Profiles and pre-processing script

- Script in the repo (`scripts/`, code only): inputs $\alpha_w$, $\theta_w$ (and $W_w$, $h^D_w$ for the YAML); outputs `arrival_flex` = `max_below_abs` = $\theta_w \alpha_w d_{IT}(t)$ per archetype. Checks $\sum_w \alpha_w = 1$.
- Generated CSVs are **not committed**; they are reproducible from `demands.csv` and the parameter file.

---

## 5. Checks (code review and runs)

1. Unit tests as in v2, with the calendar test updated: $B = 0$ at the end of every hour with $t \bmod 24 = h^D_w$.
2. New case folder (copy of `4_WH+PV+DHN+Flex_fix1+3`, reference folders untouched).
3. **θ = 0 regression:** matches `fix1+3` with load shifting removed (no-flex run, to be made). Not the 88,646.61 CHF/a of `fix1+3`: that run includes the interval-mode `ls3` shifting. The gap between the two is the value of `ls3`, a useful anchor in its own right.
4. Every flex run: $\sum L = 0$; report $TAC_{sys}$, $\varepsilon \sum B$, solve time, MIP gap.
5. Solver: MIP gap 0 % (as the 27 Oct runs); `PYTHONHASHSEED=0`.
6. $\varepsilon$ check: halve it, dispatch-relevant results unchanged.

---

## 6. Decisions (13 Nov 2026, Bea)

1. **Base case:** `4_WH+PV+DHN+Flex_fix1+3` (both fixes approved 26 Oct, checks passed 27 Oct).
2. **Archetypes:** two placeholders, one rolling and one calendar. Smoke-run values: $\alpha_R = \alpha_C = 0.5$, $\theta_w = 0.1$ (matches `ls3`), $W_R = 24$ h, $h^D_C = 5$. Placeholders only; real values come from the parameter research.
3. **Deadlines:** hard, $\pi_w = 10$ CHF/(kWh·h), $\sum L = 0$ checked.
4. **$\rho_w$:** dropped; shared DC capacity is the only catch-up limit.
5. **Calendar convention:** queue empty at 06:00 local = 05:00 UTC (fixed offset, no DST).
6. **Rolling window:** $W_w$ = maximum delay in hours, as implemented.
7. **Implementation:** `mode` of the existing `load_shifting` submodel (as built).
8. **Kept as limitations** (not fixed): free unlimited HT export, free ambient Air at DC-air COP.

### Limitations to report

- Free HT export and free ambient Air bias the value of re-timing heat (direction not established).
- Calendar deadline 1 h late in summer (no DST in model time).
- **Weekly cycles of the profiles disagree** (El weekend on row-days 6/0 of the cycle, price minimum on day 5, IT low on days 4–5, LT on days 0–1): profiles likely from different years. Minor for $W_w \le 24$ h; relevant for longer windows and weekend claims. Ask Jenny for the source year of each profile.
- Perfect foresight over 8,760 h: results are upper bounds.

---

## 7. Attribution

- Batch-class structure (total demand, release, deadline, max rate): Liu et al. (2012), SIGMETRICS, doi:10.1145/2254756.2254779, §2.3, §3.2.
- Lateness-penalty form: own choice, motivated by Liu's revenue-in-window term.
- Backlog form, rolling deadline, shared-capacity catch-up limit, $\varepsilon$ tie-break: our design (see `claude/literature_scan_it_flexibility.md`).
