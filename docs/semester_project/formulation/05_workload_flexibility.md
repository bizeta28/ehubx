# Workload flexibility: formulation v2

**Status:** formulation approved by Bea, 13 Nov 2026. The open decisions in §6 are still pending and get settled through the parameter research. Target file in the repo: `docs/semester_project/formulation/05_workload_flexibility.md`.
**Replaces:** the earlier draft with $\kappa_w$ (catch-up cap) and hard deadlines.
**Code basis:** read against `bizeta28/ehubx`, branch `semester-project` (`src/ehubx/model/load_shifting_model.py`, `energy_system_model.py`, example `4_WH+PV+DHN+Flex`).

---

## 1. Idea in one paragraph

IT work arrives as an hourly power profile per archetype $w$. A share $\theta_w$ of it can be deferred, never advanced. Deferred work waits in a backlog that has to be cleared by a deadline. For **rolling** archetypes (continuous arrivals: queued HPC jobs, inference backlogs) the deadline is $W_w$ hours after arrival. For **calendar** archetypes (scheduled batch: backups, nightly ETL) it is a fixed clock time, e.g. 06:00. Each archetype can only run as fast as its hardware allows ($\rho_w$). Missing a deadline is allowed but penalised ($\pi_w$), so the model is always feasible. A tiny cost on the backlog ($\varepsilon$) stops the solver from shifting work for no reason.

---

## 2. Notation

### Sets

| Symbol | Meaning |
|---|---|
| $t \in \mathcal{T} = \{1,\dots,8760\}$ | hours, chronological, $\Delta t = 1$ h |
| $w \in \mathcal{W} = \mathcal{W}^R \cup \mathcal{W}^C$ | workload archetypes: rolling ($R$) or calendar ($C$) deadline |
| $\mathcal{T}^D_w \subseteq \mathcal{T}$ | deadline hours of calendar archetype $w$ (e.g. every 06:00) |

### Parameters

| Symbol | Unit | Meaning | Source / status |
|---|---|---|---|
| $a_w(t)$ | kW | IT power demand of archetype $w$ as it arrives; $\sum_w a_w(t) = d_{IT}(t)$ | scenario ($\alpha_w$ × profile) |
| $\theta_w$ | – | deferrable share of $a_w$ | literature anchors, sweep |
| $W_w$ | h | rolling window ($w \in \mathcal{W}^R$) | literature anchors, sweep |
| $\rho_w$ | – | hardware headroom: installed IT power of $w$ / $\max_t a_w(t)$, $\rho_w \ge 1$ | **no source yet** (utilisation data) |
| $\pi_w$ | CHF/(kWh·h) | lateness penalty | **no empirical anchor**: large value or sweep |
| $\varepsilon$ | CHF/(kWh·h) | tie-break cost on backlog | ≈ $10^{-4}$, check by halving |
| $Cap_{DC}$ | kW | DC IT capacity | fixed at baseline value in flex runs |

### Variables (all $\ge 0$ unless stated)

| Symbol | Unit | Meaning |
|---|---|---|
| $x_w(t)$ | kW | deferrable work actually executed in hour $t$ |
| $s_w(t) = x_w(t) - \theta_w a_w(t)$ | kW, free sign | shift relative to the arrival profile (this is ehubX's `V_LoadShifting`) |
| $B_w(t)$ | kWh | backlog: deferrable work that has arrived but not yet run |
| $L_w(t)$ | kWh | backlog that is past its deadline (lateness slack) |

---

## 3. Constraints and their meaning

### (1) Backlog balance

$$B_w(t) = B_w(t-1) + \big(\theta_w a_w(t) - x_w(t)\big)\,\Delta t = B_w(t-1) - s_w(t)\,\Delta t, \qquad B_w(0) = 0$$

*Meaning:* bookkeeping for a queue. The backlog grows with what arrives and shrinks with what runs. Written with the shift $s_w$, the backlog is just minus the cumulative shift: $B_w(t) = -\sum_{\tau \le t} s_w(\tau)\,\Delta t$.

### (2) Delay-only

$$B_w(t) \ge 0 \qquad \forall w, t$$

*Meaning:* the backlog can never be negative, so work can't run before it has arrived. This single sign condition is what makes the model **delay-only**. The current ehubX load shifting is bidirectional and lets load move *earlier* within an interval, which is non-causal for IT work.

### (3a) Rolling deadline ($w \in \mathcal{W}^R$)

$$B_w(t) \le \sum_{\tau = \max(1,\,t-W_w+1)}^{t} \theta_w a_w(\tau)\,\Delta t + L_w(t) \qquad \forall t$$

*Meaning:* at any hour, the queue can only hold work that arrived in the last $W_w$ hours. Anything older is overdue and has to be counted in $L_w(t)$. For a first-come-first-served fluid queue this is exactly "every kWh runs within $W_w$ hours of its arrival" (backlog reading, 3 Nov; derivation still to be checked independently).

### (3b) Calendar deadline ($w \in \mathcal{W}^C$)

$$B_w(t) \le L_w(t) \qquad \forall t \in \mathcal{T}^D_w$$

*Meaning:* at each deadline hour (e.g. 06:00) the queue must be empty; whatever is left is late. Between deadlines the backlog is unconstrained (except for (2)). This is Liu et al.'s fixed window, but delay-only. Work that arrives just before the deadline has almost no slack. That is intended and realistic for scheduled jobs, provided the arrival profile places the work sensibly (e.g. released after business hours).

### (4) Lower bound on execution

$$x_w(t) \ge 0 \;\Longleftrightarrow\; s_w(t) \ge -\theta_w a_w(t)$$

*Meaning:* in any hour you can at most postpone all of the deferrable work that arrives then. You can't "un-run" the inflexible part $(1-\theta_w)a_w$.

### (5) Hardware cap per archetype (replaces $\kappa_w$)

$$(1-\theta_w)\,a_w(t) + x_w(t) \le \rho_w \max_\tau a_w(\tau) \;\Longleftrightarrow\; s_w(t) \le \rho_w \max_\tau a_w(\tau) - a_w(t)$$

*Meaning:* an archetype can't draw more power than the hardware it runs on. With $\rho_w = 1$, catch-up only happens in hours where the archetype runs below its own peak, so flexibility is bounded by underutilisation. That's physically right, and it puts all the weight on getting $\rho_w$ from data.

### (6) DC capacity

$$P_{IT}(t) = \sum_w \big[a_w(t) + s_w(t)\big] = d_{IT}(t) + \sum_w s_w(t) \le Cap_{DC}$$

*Meaning:* total IT load after shifting is what the DC must supply. In ehubX this isn't a new constraint: the shifted IT demand is met by the `DC` conversion tech, whose capacity bounds it. **$Cap_{DC}$ must be fixed** (cap_min = cap_max = baseline) in flex runs. Otherwise the model could build a bigger DC to absorb catch-up peaks, and DC capex is currently commented out in `techs.yaml`, so it would cost nothing.

### (7) Closure

$$B_w(T) = 0 \;\Longleftrightarrow\; \sum_t s_w(t)\,\Delta t = 0$$

*Meaning:* all work is done within the year, so annual IT energy (and therefore recoverable heat) is conserved. Shifting only re-times heat. In ehubX this is already enforced by `C_LoadShiftingNeutralityOverall`.

### (8) Objective

$$\min \; TAC \;+\; \sum_{w,t} \pi_w\, L_w(t) \;+\; \varepsilon \sum_{w,t} B_w(t)$$

*Meaning:* the usual system cost, plus a penalty for each kWh·h of overdue work, plus a negligible cost on waiting. Without $\varepsilon$, every reshuffle that leaves TAC unchanged is equally optimal, and the reported shifting becomes a solver artefact. With $\pi_w \to \infty$ you recover hard deadlines. Note: penalising per kWh·**h** makes a 10 h delay cost ten times a 1 h delay (tardiness logic). A flat cost per kWh that misses its deadline (SLA logic) is the alternative. Decide which one.

### Feasibility

Running everything on arrival, $s_w \equiv 0$ ($x_w = \theta_w a_w$), gives $B = L = 0$. It satisfies (5) when $\rho_w \ge 1$ and (6) when $d_{IT}(t) \le Cap_{DC}$. So the model is **always feasible**. The earlier $\kappa_w < \theta_w$ trap is gone.

---

## 4. Mapping onto ehubX

### What already exists and is reused

| Formulation | ehubX object | Note |
|---|---|---|
| $s_w(t)$ | `V_LoadShifting[ls, s, h, e, t]`, one `ls` per archetype, `ec: IT` | several `ls` on the same `(s, h, IT)` are already summed in `C_LoadShiftingTotal` |
| (6) $P_{IT} = d_{IT} + \sum_w s_w$ | `C_SystemDemandSupplyProfile` adds `V_LoadShiftingTotal` to the IT demand | no change |
| (4) lower bound | `max_below_abs` profile $= \theta_w a_w(t)$ | must be **abs**, not rel: `max_below_rel` multiplies the *total* IT demand, not $a_w$ |
| (5) hardware cap | `max_above_abs` profile $= \rho_w \max a_w - a_w(t)$ | time-varying profile, already supported |
| (7) closure | `C_LoadShiftingNeutralityOverall` | holds if all weights = 1 (no clustering) |
| objective | `V_LoadShiftingCostTotal` → `V_SystemCost` | extend the sum, no new link needed |

### What is new

1. **YAML key `mode`** on a load-shift entry: `interval` (default, current behaviour) or `backlog` (this formulation).
2. **Parameters:** `deadline_type` (`rolling` | `calendar`), `window` (h), `deadline_hours` (list of hour-of-day), `late_cost` ($\pi_w$), `backlog_cost` ($\varepsilon$).
3. **Profile column** `arrival_flex` $= \theta_w a_w(t)$ (kW), needed on the right-hand side of (3a).
4. **Variables** `V_LoadShiftingBacklog`, `V_LoadShiftingLate` (`NonNegativeReals`: the domain itself enforces (2)).
5. **Constraints** (1), (3a), (3b).
6. **Skip** `C_LoadShiftingNeutralityOnIntervals` and `C_LoadShiftingIntervalCap` for backlog-mode `ls`. They implement the non-overlapping 24 h blocks we're replacing.
7. **Guard:** backlog mode requires a chronological horizon (no time clustering, all weights 1). Raise an error otherwise: the backlog chain across hours is meaningless on clustered typical days.

### Input sketch (`demands.yaml`)

```yaml
load_shifting:
- load_shift_id: hpc_batch
  stages: S1
  hubs: H1
  ec: IT
  mode: backlog                 # new
  deadline_type: rolling        # new: rolling | calendar
  window: 24 h                  # new, rolling only
  late_cost: 1 CHF/kWh          # new, pi_w (interpreted per hour of lateness; unit handling to check)
  backlog_cost: 0.0001 CHF/kWh  # new, epsilon
  profile_path: profiles/loadshifting_profiles.csv   # arrival_flex, max_above_abs, max_below_abs

- load_shift_id: backup
  stages: S1
  hubs: H1
  ec: IT
  mode: backlog
  deadline_type: calendar
  deadline_hours: [6]           # new, calendar only
  late_cost: 1 CHF/kWh
  backlog_cost: 0.0001 CHF/kWh
  profile_path: profiles/loadshifting_profiles.csv
```

The profiles ($\theta_w a_w$, $\rho_w \max a_w - a_w$) come from a pre-processing script outside the repo (archetype mix $\alpha_w$, $\theta_w$, $\rho_w$ → CSV). **No data committed.** The script also checks $\sum_w a_w(t) = d_{IT}(t)$ against `demands.csv`.

### Pyomo sketch (`load_shifting_model.py`, same `getattr/setattr` style)

```python
SET_LOADSHIFTINGBACKLOG = "S_LoadShiftingBacklog"     # (ls, s, h, e) with mode == backlog
VAR_LOADSHIFTINGBACKLOG = "V_LoadShiftingBacklog"     # B_w(t)  [kWh]
VAR_LOADSHIFTINGLATE    = "V_LoadShiftingLate"        # L_w(t)  [kWh]
CON_LOADSHIFTINGBACKLOG = "C_LoadShiftingBacklog"     # (1)
CON_LOADSHIFTINGDEADLINE = "C_LoadShiftingDeadline"   # (3a)/(3b)

def _build_backlog(model, load_shifting, times):
    _assert_chronological(times)   # no clustering, weights == 1 -> else raise
    tuples = [(ls, s, h, e) for (ls, s, h, e) in getattr(model, SET_LOADSHIFTINGWITHTUPLES)
              if load_shifting.get_mode(LoadShiftId(ls)) == "backlog"]
    setattr(model, SET_LOADSHIFTINGBACKLOG,
            Set(within=getattr(model, SET_LOADSHIFTINGWITHTUPLES), initialize=tuples))
    T = getattr(model, SET_TIME)
    setattr(model, VAR_LOADSHIFTINGBACKLOG,
            Var(getattr(model, SET_LOADSHIFTINGBACKLOG), T, domain=NonNegativeReals))  # (2)
    setattr(model, VAR_LOADSHIFTINGLATE,
            Var(getattr(model, SET_LOADSHIFTINGBACKLOG), T, domain=NonNegativeReals))

    # (1) B(t) = B(t-1) - s(t) * dt, B(0) = 0
    def _rule_backlog(m, ls, s, h, e, t):
        B, S = getattr(m, VAR_LOADSHIFTINGBACKLOG), getattr(m, VAR_LOADSHIFTING)
        prev = 0 if t == T.first() else B[ls, s, h, e, t - 1]   # assumes consecutive int keys
        return B[ls, s, h, e, t] == prev - S[ls, s, h, e, t]    # dt = 1 h
    setattr(model, CON_LOADSHIFTINGBACKLOG,
            Constraint(getattr(model, SET_LOADSHIFTINGBACKLOG), T, rule=_rule_backlog))

    # (3a) rolling / (3b) calendar
    def _rule_deadline(m, ls, s, h, e, t):
        lsid = LoadShiftId(ls)
        B, L = getattr(m, VAR_LOADSHIFTINGBACKLOG), getattr(m, VAR_LOADSHIFTINGLATE)
        if load_shifting.get_deadline_type(lsid) == "rolling":
            W = round(load_shifting.get_window(lsid).to_float(unit=TimeUnit.H))
            arr = load_shifting.get_arrival_flex(lsid)          # profile theta_w * a_w(t)
            rhs = sum(arr.get_value(TimeId(tau)).to_float(unit=PowerUnit.KW)  # unit: as in other kW profiles
                      for tau in range(max(T.first(), t - W + 1), t + 1))
            return B[ls, s, h, e, t] <= rhs + L[ls, s, h, e, t]
        # calendar: only at deadline hours
        hour_of_day = (t - T.first()) % 24                       # assumes t = first is 00:00
        if hour_of_day not in load_shifting.get_deadline_hours(lsid):
            return Constraint.Skip
        return B[ls, s, h, e, t] <= L[ls, s, h, e, t]
    setattr(model, CON_LOADSHIFTINGDEADLINE,
            Constraint(getattr(model, SET_LOADSHIFTINGBACKLOG), T, rule=_rule_deadline))
```

Changes to existing functions:

```python
# in _con_load_shifting_neutrality_on_intervals and _con_load_shifting_interval_cap:
if (ls, s, h, e) in getattr(model, SET_LOADSHIFTINGBACKLOG):
    return Constraint.Skip

# in _con_load_shifting_cost_total, add:
load_shifting_cost_total += sum(
    pi[ls] * L[ls, s, h, e, t] + eps[ls] * B[ls, s, h, e, t]
    for (ls, s, h, e) in getattr(model, SET_LOADSHIFTINGBACKLOG)
    for t in getattr(model, SET_TIME)
)
```

Order matters: `_build_backlog` has to run before `_build_cost` (it needs the sets and variables).

Also keep **`fix_cost = 0`** for backlog-mode entries. A non-zero fix cost creates the binary `V_YLoadShifting` and turns the LP into a MILP.

### Size

Per archetype: 3 × 8,760 variables ($s$ plus the existing above/below split, $B$, $L$) and about 2 × 8,760 constraints. That's $O(T)$, the same order as the current submodel. The rolling right-hand side is a constant (a parameter sum), so it adds no density.

---

## 5. Things to check in code review (not just in the maths)

1. **Time keys:** are `S_Time` ids consecutive integers, and does the first one correspond to 1 Jan 00:00? Both (1) and the calendar hour-of-day logic rely on it.
2. **Units:** `V_LoadShifting` is in `ec_unit / h` (kW for IT). With $\Delta t = 1$ h, kW·h = kWh, fine. Check that the unit parser accepts the cost units, or document that `late_cost` / `backlog_cost` are per kWh per time step.
3. **above/below split:** with zero energy costs, `above` and `below` can both be positive in the same hour. Harmless for the bounds ($s \ge -\text{below} \ge -\theta a$), but report $s$, not above/below.
4. **Overall neutrality uses weights:** fine for 8,760 h (weights = 1). The guard in §4 makes sure.
5. **DC capacity fixed** in flex runs (see (6)).
6. **Unit tests (tiny cases):**
   - all flex shares 0 → identical to baseline;
   - flat price, no heat value, $\varepsilon > 0$ → $s \equiv 0$;
   - a single price dip inside $W_w$ → work moves there and no further;
   - a price dip beyond $W_w$ with large $\pi_w$ → no work moves past the deadline;
   - calendar: backlog is 0 at every 06:00.

---

## 6. Open decisions (for Bea)

1. Which archetypes are rolling and which are calendar?
2. Soft ($\pi_w$ finite, swept) or effectively hard deadlines?
3. Lateness cost per kWh·h (tardiness) or per kWh (SLA breach)?
4. $\rho_w$ replacing $\kappa_w$: accepted? Where do the utilisation data come from?
5. Implement as a `mode` of the existing `load_shifting` submodel (proposed, in line with "extend existing submodels") or as a separate submodel?

## 7. Attribution

- Batch-class structure (total demand, release, deadline, max rate): Liu et al. (2012), SIGMETRICS, doi:10.1145/2254756.2254779, §2.3, §3.2.
- Soft deadlines: motivated by Liu's revenue-in-window term; the specific lateness-penalty form is our own choice.
- Backlog form, rolling deadline, $\rho_w$ cap, $\varepsilon$ tie-break: our design (see `claude/literature_scan_it_flexibility.md` for precedents of cumulative constraints).
