"""Load shifting submodel"""

from datetime import datetime

from pyomo.core import (
    Binary,
    Constraint,
    Model,
    NonNegativeReals,
    Reals,
    Set,
    Var,
)

from ehubx.core import common, exceptions, logging
from ehubx.data.demand_data import Demands
from ehubx.data.ec_data import EcId, Ecs
from ehubx.data.energy_system_data import EnergySystem
from ehubx.data.hub_data import HubId
from ehubx.data.load_shifting_data import DeadlineType, LoadShiftId, LoadShifting
from ehubx.data.stage_data import StageId
from ehubx.data.time_data import TimeId, Times
from ehubx.data.unit import (
    CurrencyUnit,
    FreightUnit,
    LengthUnit,
    MassUnit,
    PassengerUnit,
    PowerUnit,
    TimeUnit,
)
from ehubx.model.ec_model import SET_EC, get_ec_model_unit
from ehubx.model.hub_model import SET_HUB
from ehubx.model.stage_model import SET_STAGE
from ehubx.model.times_model import SET_TIME, SET_TIMEHORIZON


# -------- #
# Literals #
# -------- #
LOG_MODULE_STR: str = "mod/load_shift"
"""String identifying the load shifting model for logging purposes"""

MULT_SHIFT_ABOVE_DEMAND: float = 10
"""Multiplier to the demand value to set a maximal upper threshold for
above-shifts"""

MULT_SHIFT_BELOW_DEMAND: float = 1
"""Multiplier to the demand value to set a maximal upper threshold for
below-shifts"""

SET_LOADSHIFTINGIDS: str = "S_LoadShiftingIds"
"""Name of set with all load shifting indices (ls)"""

SET_LOADSHIFTINGWITHTUPLES: str = "S_LoadShiftingWithTuples"
"""Name of set with all load shifting tuples (ls, s, h, e)"""

SET_LOADSHIFTINGTUPLES: str = "S_LoadShiftingTuples"
"""Name of set with all load shifting tuples (s, h, e)"""

SET_LOADSHIFTINGWITHTUPLESFIX: str = "S_LoadShiftingWithTuplesFix"
"""Name of set with all load shifting tuples (ls, s, h, e) which have fixed costs"""

VAR_LOADSHIFTING: str = "V_LoadShifting"
"""Name of variable for load shifting amount per (ls, s, h, e)"""

VAR_LOADSHIFTINGTOTAL: str = "V_LoadShiftingTotal"
"""Name of variable for load shifting amount per (s, h, e)"""

VAR_LOADSHIFTINGCAP: str = "V_LoadShiftingCap"
"""Name of variable for load shifting capacity (contains initial capacity and installed
capacity)"""

VAR_LOADSHIFTINGCAPINSTL: str = "V_LoadShiftingCapInstl"
"""Name of variable for installed load shifting capacity"""

VAR_LOADSHIFTINGABOVE: str = "V_LoadShiftingAbove"
"""Name of variable for above-parts of load shifting"""

VAR_LOADSHIFTINGBELOW: str = "V_LoadShiftingBelow"
"""Name of variable for below-parts of load shifting"""

VAR_LOADSHIFTINGABOVEPEAK: str = "V_LoadShiftingAbovePeak"
"""Name of variable for peak value of above-parts of load shifting"""

VAR_LOADSHIFTINGBELOWPEAK: str = "V_LoadShiftingBelowPeak"
"""Name of variable for peak value of below-parts of load shifting"""

VAR_LOADSHIFTINGCOSTCAPEX: str = "V_LoadShiftingsCostCapex"
"""Name of variable for CAPEX costs of load shifting capacity"""

VAR_LOADSHIFTINGCOSTENERGY: str = "V_LoadShiftingCostEnergy"
"""Name of variable for energy-related load shifting costs"""

VAR_LOADSHIFTINGCOSTPEAK: str = "V_LoadShiftingCostPeak"
"""Name of variable for peak-related load shifting costs"""

VAR_LOADSHIFTINGCOSTFIX: str = "V_LoadShiftingCostFix"
"""Name of variable for fixed amounts in load shifting costs"""

VAR_LOADSHIFTINGCOSTTOTAL: str = "V_LoadShiftingCostTotal"
"""Name of variable for total load shifting costs"""

VAR_YLOADSHIFTING: str = "V_YLoadShifting"
"""Name of variable monitoring whether any amount of load shifting occurs"""

CON_LOADSHIFTINGTOTAL: str = "C_LoadShiftingTotal"
"""Name of constraint enforcing load shifting amount per (s, h, e) tuple
as sum over ls"""

CON_LOADHSHIFTINGNEUTRALITYONINTERVALS: str = "C_LoadShiftingNeutralityOnIntervals"
"""Name of constraint enforcing load shifting neutrality on load shift
intervals"""

CON_LOADSHIFTINGNEUTRALITYOVERALL: str = "C_LoadShiftingNeutralityOverall"
"""Name of constraint enforcing load shifting neutrality on entire time
horizon"""

CON_LOADSHIFTINGABOVEBLEOW: str = "C_LoadShiftingAboveBelow"
"""Name of constraint composing load shifting from the above and below parts"""

CON_LOADSHIFTINGMAXABOVE: str = "C_LoadShiftingMaxAbove"
"""Name of constraint setting an upper limit for above parts of load
shifting"""

CON_LOADSHIFTINGMAXBELOW: str = "C_LoadShiftingMaxBelow"
"""Name of constraint setting an upper limit for below parts of load
shifting"""

CON_LOADSHIFTINGCAP: str = "C_LoadShiftingCap"
"""Name of constraint defining load shifting capacity as the sum of initial and
 installed capacity"""

CON_LOADSHIFTINGCAPMIN: str = "C_LoadShiftingCapMin"
"""Name of constraint respecting cap_min for load shifting capacity"""

CON_LOADSHIFTINGCAPMAX: str = "C_LoadShiftingCapMax"
"""Name of constraint respecting cap_max for load shifting capacity"""

CON_LOADSHIFTINGINTERVALCAP: str = "C_LoadShiftingIntervalCap"
"""Name of constraint respecting load shifting capacity on the load shifting
intervals"""

CON_LOADSHIFTINGABOVEPEAK: str = "C_LoadShiftingAbovePeak"
"""Name of constraint setting the peak variable for above load shifts"""

CON_LOADSHIFTINGBELOWPEAK: str = "C_LoadShiftingBelowPeak"
"""Name of constraint setting the peak variable for below load shifts"""

CON_YLOADHSHIFTING: str = "C_YLoadShifting"
"""Name of constraint setting the binary monitoring variable for fix costs"""

CON_LOADSHIFTINGCOSTCAPEX: str = "C_LoadShiftingCostCapex"
"""Name of constraint setting load shifting CAPEX costs for capacity"""

CON_LOADSHIFTINGCOSTENERGY: str = "C_LoadShiftingCostEnergy"
"""Name of constraint setting the energy-related load shifting cost"""

CON_LOADSHIFTINGCOSTPEAK: str = "C_LoadShiftingCostPeak"
"""Name of constraint setting the peak-related load shifting cost"""

CON_LOADSHIFTINGCOSTFIX: str = "C_LoadShiftingCostFix"
"""Name of constraint setting the fixed load shifting costs"""

CON_LOADSHIFTINGCOSTTOTAL: str = "C_LoadShiftingCostTotal"
"""Name of constraint setting the total load shifting costs"""

# ---------------------------------------------------------------------- #
# Backlog mode (docs/semester_project/formulation/05_workload_flexibility.md)
# ---------------------------------------------------------------------- #
DT_H: float = 1.0
"""Time step length Delta t [h]. The backlog mode assumes hourly steps."""

SET_LOADSHIFTINGBACKLOG: str = "S_LoadShiftingBacklog"
"""Name of set with load shifting tuples (ls, s, h, e) in mode 'backlog'"""

VAR_LOADSHIFTINGBACKLOG: str = "V_LoadShiftingBacklog"
"""Name of variable for the backlog B_w(t) [ec_unit, e.g. kWh] at the end of
hour t (spec 05, (1)-(2))"""

VAR_LOADSHIFTINGLATE: str = "V_LoadShiftingLate"
"""Name of variable for the overdue backlog L_w(t) [ec_unit, e.g. kWh]
(spec 05, (3a)/(3b))"""

VAR_LOADSHIFTINGCOSTLATE: str = "V_LoadShiftingCostLate"
"""Name of variable for the lateness penalty sum_t pi_w L_w(t) dt [CHF]"""

VAR_LOADSHIFTINGCOSTBACKLOG: str = "V_LoadShiftingCostBacklog"
"""Name of variable for the backlog tie-break cost sum_t eps B_w(t) dt [CHF]"""

CON_LOADSHIFTINGBACKLOG: str = "C_LoadShiftingBacklog"
"""Name of constraint for the backlog balance (spec 05, (1))"""

CON_LOADSHIFTINGDEADLINE: str = "C_LoadShiftingDeadline"
"""Name of constraint for the rolling / calendar deadline (spec 05, (3a)/(3b))"""

CON_LOADSHIFTINGCOSTLATE: str = "C_LoadShiftingCostLate"
"""Name of constraint defining V_LoadShiftingCostLate (spec 05, (8))"""

CON_LOADSHIFTINGCOSTBACKLOG: str = "C_LoadShiftingCostBacklog"
"""Name of constraint defining V_LoadShiftingCostBacklog (spec 05, (8))"""


def build(model: Model, system: EnergySystem) -> None:
    """
    Builds the load shifting submodel. For a mathematical description in
    thorough detail, please refer to the section 'Load shifting model' in the
    documentation.

    :param model: Pyomo model
    :type model: Model
    :param system: Energy system data
    :type system: EnergySystem
    """
    # Extract data from modules
    ecs: Ecs = system.ecs
    demands: Demands = system.demands
    load_shifting: LoadShifting = system.load_shifting
    times: Times = system.times
    currency_unit: CurrencyUnit = system.currency_unit
    mass_unit: MassUnit = system.mass_unit
    power_unit: PowerUnit = system.power_unit
    length_unit: LengthUnit = system.length_unit
    passenger_unit: PassengerUnit = system.passenger_unit
    freight_unit: FreightUnit = system.freight_unit
    # Start measuring build time
    start = datetime.now()
    # Build
    _build_base(
        model,
        ecs,
        demands,
        load_shifting,
        times,
        currency_unit,
        mass_unit,
        power_unit,
        length_unit,
        passenger_unit,
        freight_unit,
    )
    # Backlog mode (spec 05). Must run after _build_base (needs
    # V_LoadShifting) and before _build_cost (cost total uses its variables).
    _build_backlog(
        model,
        ecs,
        load_shifting,
        times,
        currency_unit,
        mass_unit,
        power_unit,
        length_unit,
        passenger_unit,
        freight_unit,
    )
    _build_cost(
        model,
        ecs,
        load_shifting,
        times,
        currency_unit,
        mass_unit,
        power_unit,
        length_unit,
        passenger_unit,
        freight_unit,
    )
    # Logging
    elapsed = datetime.now() - start
    logging.log_file(
        f"Built load shifting module. Elapsed time: {int(elapsed.total_seconds())}s",
        module=LOG_MODULE_STR,
    )


def _build_base(
    model: Model,
    ecs: Ecs,
    demands: Demands,
    load_shifting: LoadShifting,
    times: Times,
    currency_unit: CurrencyUnit,
    mass_unit: MassUnit,
    power_unit: PowerUnit,
    length_unit: LengthUnit,
    passenger_unit: PassengerUnit,
    freight_unit: FreightUnit,
) -> None:
    # [SET] Load shifting ids
    setattr(
        model, SET_LOADSHIFTINGIDS, Set(initialize=[ls.key for ls in load_shifting.ids])
    )
    # [SET] Load shifting with tuples (ls, stage, hub, ec)
    setattr(
        model,
        SET_LOADSHIFTINGWITHTUPLES,
        Set(
            within=(
                getattr(model, SET_LOADSHIFTINGIDS)
                * getattr(model, SET_STAGE)
                * getattr(model, SET_HUB)
                * getattr(model, SET_EC)
            ),
            initialize=[
                (ls.key, s.key, h.key, load_shifting.get_ec(ls).key)
                for ls in load_shifting.ids
                for (s, h) in load_shifting.get_stage_hub_tuples(ls)
            ],
        ),
    )
    # [SET] Load shifting tuples (stage, hub, ec)
    setattr(
        model,
        SET_LOADSHIFTINGTUPLES,
        Set(
            within=(
                getattr(model, SET_STAGE)
                * getattr(model, SET_HUB)
                * getattr(model, SET_EC)
            ),
            initialize=list(
                {
                    (s.key, h.key, load_shifting.get_ec(ls).key)
                    for ls in load_shifting.ids
                    for (s, h) in load_shifting.get_stage_hub_tuples(ls)
                }
            ),
        ),
    )
    # [SET] Load shifting tuples (ls, s, h, e) in mode 'backlog' (spec 05).
    #       Built here because the interval constraints below skip them.
    setattr(
        model,
        SET_LOADSHIFTINGBACKLOG,
        Set(
            within=getattr(model, SET_LOADSHIFTINGWITHTUPLES),
            initialize=[
                (ls, s, h, e)
                for (ls, s, h, e) in getattr(model, SET_LOADSHIFTINGWITHTUPLES)
                if load_shifting.is_backlog(LoadShiftId(ls))
            ],
        ),
    )
    # [VAR] Load shifting amount per (ls, s, h, e) tuple
    setattr(
        model,
        VAR_LOADSHIFTING,
        Var(
            getattr(model, SET_LOADSHIFTINGWITHTUPLES),
            getattr(model, SET_TIME),
            domain=Reals,
        ),
    )
    # [VAR] Load shifting amount per (s, h, e) tuple
    setattr(
        model,
        VAR_LOADSHIFTINGTOTAL,
        Var(
            getattr(model, SET_LOADSHIFTINGTUPLES),
            getattr(model, SET_TIME),
            domain=Reals,
        ),
    )
    # [CON] Load shifting amount per (s, h, e) tuple as some over ls
    _con_load_shifting_total(model)
    # [CON] Enforce load shifting neutrality on shifting intervals.
    _con_load_shifting_neutrality_on_intervals(model, load_shifting, times)
    # [CON] Enforce overall load shifting neutrality, i.e., over full time
    #       horizon
    _con_load_shifting_neutrality_overall(model, times)
    # [VAR] Load shifting amount above load curve
    setattr(
        model,
        VAR_LOADSHIFTINGABOVE,
        Var(
            getattr(model, SET_LOADSHIFTINGWITHTUPLES),
            getattr(model, SET_TIME),
            domain=NonNegativeReals,
        ),
    )
    # [VAR] Load shifting amount below load curve
    setattr(
        model,
        VAR_LOADSHIFTINGBELOW,
        Var(
            getattr(model, SET_LOADSHIFTINGWITHTUPLES),
            getattr(model, SET_TIME),
            domain=NonNegativeReals,
        ),
    )
    # [CON] Force load shifting to be made of above-shifts minus below-shifts
    _con_load_shifting_abovebelow(model)
    # [CON] Respect absolute and relative maximal values for above and below
    #       shifts
    _con_load_shifting_max_abovebelow(
        model, ecs, demands, load_shifting, mass_unit, power_unit, length_unit,
        passenger_unit, freight_unit,
    )
    # [VAR] Load shifting capacity, maximal load shifting amount per interval
    setattr(
        model,
        VAR_LOADSHIFTINGCAP,
        Var(
            getattr(model, SET_LOADSHIFTINGWITHTUPLES),
            domain=NonNegativeReals,
        ),
    )
    # [VAR] Installed load shifting capacity
    setattr(
        model,
        VAR_LOADSHIFTINGCAPINSTL,
        Var(
            getattr(model, SET_LOADSHIFTINGWITHTUPLES),
            domain=NonNegativeReals,
        ),
    )
    # [CON] Define LoadShiftingCap as the sum of initial and installed capacity
    _con_load_shifting_cap(
        model, ecs, load_shifting, mass_unit, power_unit, length_unit, passenger_unit,
        freight_unit,
    )
    # [CON] Respect cap_min and cap_max for load shifting capacity
    _con_load_shifting_cap_minmax(
        model, ecs, load_shifting, mass_unit, power_unit, length_unit, passenger_unit,
        freight_unit,
    )
    # [CON] Respect interval capacity, i.e. time integral over total amount of
    #       above-shifts on each load interval
    _con_load_shifting_interval_cap(model, load_shifting, times)

    # [VAR] Peak value of all above-shifts on the full time horizon
    setattr(
        model,
        VAR_LOADSHIFTINGABOVEPEAK,
        Var(getattr(model, SET_LOADSHIFTINGWITHTUPLES), domain=NonNegativeReals),
    )
    # [VAR] Peak value of all below-shifts on the full time horizon
    setattr(
        model,
        VAR_LOADSHIFTINGBELOWPEAK,
        Var(getattr(model, SET_LOADSHIFTINGWITHTUPLES), domain=NonNegativeReals),
    )
    # [CON] Force the peak values to lie above all time-dependent values
    _con_load_shifting_peak(model)
    # [VAR] Binary variable to monitor load shifting occurences. Only defend
    #       for tuples with fix costs
    _var_y_load_shifting(
        model, ecs, load_shifting, currency_unit, mass_unit, power_unit, length_unit,
        passenger_unit, freight_unit,
    )
    # [VAR] Force YLoadShifting to 1 if LoadShifting is larger than 0
    _con_y_load_shifting(
        model, ecs, demands, load_shifting, mass_unit, power_unit, length_unit,
        passenger_unit, freight_unit,
    )


def _build_cost(
    model: Model,
    ecs: Ecs,
    load_shifting: LoadShifting,
    times: Times,
    currency_unit: CurrencyUnit,
    mass_unit: MassUnit,
    power_unit: PowerUnit,
    length_unit: LengthUnit,
    passenger_unit: PassengerUnit,
    freight_unit: FreightUnit,
) -> None:
    # [VAR] Load shifting CAPEX cost, i.e., costs for installed capacity
    setattr(
        model,
        VAR_LOADSHIFTINGCOSTCAPEX,
        Var(getattr(model, SET_LOADSHIFTINGWITHTUPLES), domain=Reals),
    )
    # [CON] Load shifting CAPEX cost
    _con_load_shifting_cost_capex(
        model, ecs, load_shifting, currency_unit, mass_unit, power_unit, length_unit,
        passenger_unit, freight_unit,
    )
    # [VAR] Load shifting energy cost, i.e. time integral over all
    #       absolute load shifting power above and below the demand curve
    setattr(
        model,
        VAR_LOADSHIFTINGCOSTENERGY,
        Var(getattr(model, SET_LOADSHIFTINGWITHTUPLES), domain=Reals),
    )
    # [CON] Load shifting energy cost
    _con_load_shifting_cost_energy(
        model, ecs, load_shifting, times, currency_unit, mass_unit, power_unit,
        length_unit, passenger_unit, freight_unit,
    )
    # [VAR] Load shifting peak cost, i.e., cost for highest shifts on time
    #       horizon
    setattr(
        model,
        VAR_LOADSHIFTINGCOSTPEAK,
        Var(getattr(model, SET_LOADSHIFTINGWITHTUPLES), domain=Reals),
    )
    # [CON] Load shifting peak cost
    _con_load_shifting_cost_peak(
        model, ecs, load_shifting, currency_unit, mass_unit, power_unit, length_unit,
        passenger_unit, freight_unit,
    )
    # [VAR] Load shifting fix cost, i.e.; costs occuring any time load shifting
    #       is used at all
    setattr(
        model,
        VAR_LOADSHIFTINGCOSTFIX,
        Var(getattr(model, SET_LOADSHIFTINGWITHTUPLESFIX), domain=Reals),
    )
    # [CON] Load shifting fix cost
    _con_load_shifting_cost_fix(
        model, ecs, load_shifting, times, currency_unit, mass_unit, power_unit,
        length_unit, passenger_unit, freight_unit,
    )
    # [VAR] Total load shifting cost
    setattr(model, VAR_LOADSHIFTINGCOSTTOTAL, Var(domain=Reals))
    # [CON] Total load shedding cost
    _con_load_shifting_cost_total(model)


def _build_backlog(
    model: Model,
    ecs: Ecs,
    load_shifting: LoadShifting,
    times: Times,
    currency_unit: CurrencyUnit,
    mass_unit: MassUnit,
    power_unit: PowerUnit,
    length_unit: LengthUnit,
    passenger_unit: PassengerUnit,
    freight_unit: FreightUnit,
) -> None:
    """
    Backlog mode of load shifting, docs/semester_project/formulation/
    05_workload_flexibility.md. Uses the shift s_w(t) = V_LoadShifting and adds
        (1)  B(t) = B(t-1) - s(t) * dt,  B(0) = 0
        (2)  B(t) >= 0                                   [variable domain]
        (3a) B(t) <= sum_{tau=max(1,t-W+1)}^{t} arrival_flex(tau) dt + L(t)
        (3b) B(t) <= L(t)  for t in deadline hours
        (8)  cost  sum_t (pi * L(t) + eps * B(t)) dt
    (4), (5), (6), (7) need no new constraint: they are the max_below_abs and
    max_above_abs profiles, the DC capacity and C_LoadShiftingNeutralityOverall.
    """
    backlog_set = getattr(model, SET_LOADSHIFTINGBACKLOG)
    time_set = getattr(model, SET_TIME)
    # [VAR] Cost variables are needed by _con_load_shifting_cost_total even if
    #       there is no backlog-mode tuple (then they are empty).
    setattr(model, VAR_LOADSHIFTINGCOSTLATE, Var(backlog_set, domain=Reals))
    setattr(model, VAR_LOADSHIFTINGCOSTBACKLOG, Var(backlog_set, domain=Reals))
    if len(backlog_set) == 0:
        return

    # Guard (spec 05 §4, item 7 and §5.1, §5.4): the backlog chain needs a
    # chronological horizon of consecutive hourly steps with weight 1.
    _assert_chronological(model, times, backlog_set)
    t_first = time_set.first()

    def _ec_unit(e):
        return get_ec_model_unit(
            ecs.get_unit(EcId(e)),
            mass_unit,
            power_unit,
            length_unit,
            passenger_unit,
            freight_unit,
        )

    # [VAR] (2) Backlog B_w(t) >= 0 [ec_unit, e.g. kWh], end of hour t
    setattr(
        model,
        VAR_LOADSHIFTINGBACKLOG,
        Var(backlog_set, time_set, domain=NonNegativeReals),
    )
    # [VAR] Overdue backlog L_w(t) >= 0 [ec_unit, e.g. kWh]
    setattr(
        model,
        VAR_LOADSHIFTINGLATE,
        Var(backlog_set, time_set, domain=NonNegativeReals),
    )

    # [CON] (1) Backlog balance B(t) = B(t-1) - s(t) * dt, with B(0) = 0.
    #       s = V_LoadShifting [ec_unit/h]; s < 0 means work is deferred.
    def __rule_backlog(model, ls, s, h, e, t):
        var_b = getattr(model, VAR_LOADSHIFTINGBACKLOG)
        var_s = getattr(model, VAR_LOADSHIFTING)
        prev = 0 if t == t_first else var_b[ls, s, h, e, t - 1]
        return var_b[ls, s, h, e, t] == prev - var_s[ls, s, h, e, t] * DT_H

    setattr(
        model,
        CON_LOADSHIFTINGBACKLOG,
        Constraint(backlog_set, time_set, rule=__rule_backlog),
    )

    # Rolling right-hand side of (3a): a constant per (ls, t). Prefix sums of
    # arrival_flex [ec_unit/h] * dt, so each rhs costs O(1) instead of O(W).
    rolling_rhs = {}
    for ls, s, h, e in backlog_set:
        lsid = LoadShiftId(ls)
        if load_shifting.get_deadline_type(lsid) != DeadlineType.ROLLING:
            continue
        window = round(load_shifting.get_window(lsid).to_float(unit=TimeUnit.H))
        arrival = load_shifting.get_arrival_flex(lsid)
        unit = _ec_unit(e) / TimeUnit.H
        cum = {t_first - 1: 0.0}
        for t in time_set:
            cum[t] = cum[t - 1] + arrival.get_value(TimeId(t)).to_float(unit=unit) * DT_H
        for t in time_set:
            start = max(t_first, t - window + 1)
            rolling_rhs[ls, s, h, e, t] = cum[t] - cum[start - 1]

    # [CON] (3a) rolling:  B(t) <= sum of arrivals in the last W hours + L(t)
    #       (3b) calendar: B(t) <= L(t) at each deadline hour of the day.
    #       Hour of day as in the spec sketch: (t - t_first) % 24, with
    #       t_first taken as 00:00 (see CHANGES.md for the open convention).
    def __rule_deadline(model, ls, s, h, e, t):
        lsid = LoadShiftId(ls)
        var_b = getattr(model, VAR_LOADSHIFTINGBACKLOG)[ls, s, h, e, t]
        var_l = getattr(model, VAR_LOADSHIFTINGLATE)[ls, s, h, e, t]
        if load_shifting.get_deadline_type(lsid) == DeadlineType.ROLLING:
            return var_b <= rolling_rhs[ls, s, h, e, t] + var_l
        hour_of_day = (t - t_first) % 24
        if hour_of_day not in load_shifting.get_deadline_hours(lsid):
            return Constraint.Skip
        return var_b <= var_l

    setattr(
        model,
        CON_LOADSHIFTINGDEADLINE,
        Constraint(backlog_set, time_set, rule=__rule_deadline),
    )

    # [CON] (8) Lateness penalty sum_t pi * L(t) * dt [CHF] and backlog
    #       tie-break sum_t eps * B(t) * dt [CHF]. Both cost parameters are in
    #       CHF/(ec_unit*h); weights are 1 (guarded above).
    def __cost_coeff(ls, e, getter):
        unit = currency_unit / (_ec_unit(e) * TimeUnit.H)
        return getter(LoadShiftId(ls)).to_float(unit=unit)

    def __rule_cost_late(model, ls, s, h, e):
        pi = __cost_coeff(ls, e, load_shifting.get_late_cost)
        var_l = getattr(model, VAR_LOADSHIFTINGLATE)
        return getattr(model, VAR_LOADSHIFTINGCOSTLATE)[ls, s, h, e] == sum(
            pi * var_l[ls, s, h, e, t] * DT_H for t in time_set
        )

    def __rule_cost_backlog(model, ls, s, h, e):
        eps = __cost_coeff(ls, e, load_shifting.get_backlog_cost)
        var_b = getattr(model, VAR_LOADSHIFTINGBACKLOG)
        return getattr(model, VAR_LOADSHIFTINGCOSTBACKLOG)[ls, s, h, e] == sum(
            eps * var_b[ls, s, h, e, t] * DT_H for t in time_set
        )

    setattr(
        model,
        CON_LOADSHIFTINGCOSTLATE,
        Constraint(backlog_set, rule=__rule_cost_late),
    )
    setattr(
        model,
        CON_LOADSHIFTINGCOSTBACKLOG,
        Constraint(backlog_set, rule=__rule_cost_backlog),
    )


def _assert_chronological(model: Model, times: Times, backlog_set) -> None:
    """
    Raise if the time horizon is not a plain chronological hourly series:
    no clustering, consecutive integer time ids, all weights equal to 1.
    The backlog chain B(t-1) -> B(t) is meaningless on clustered typical days.
    """
    time_ids = list(getattr(model, SET_TIME))
    reason = None
    if times.is_clustered:
        reason = "the time series is clustered"
    elif time_ids != list(range(time_ids[0], time_ids[-1] + 1)):
        reason = "the time ids are not consecutive integers"
    else:
        stages = {s for (_, s, _, _) in backlog_set}
        for s in stages:
            for t in time_ids:
                if abs(times.get_weight(StageId(s), TimeId(t)) - 1) > common.EPS_ZEROCHECK:
                    reason = f"time step {t} of stage {s} has a weight != 1"
                    break
            if reason:
                break
    if reason is not None:
        raise exceptions.EhubXException(
            f"Load shifting mode 'backlog' needs a chronological horizon without "
            f"clustering, but {reason}.",
            module=LOG_MODULE_STR,
        )


def _con_load_shifting_total(model: Model) -> None:
    def __rule_load_shifting_total(model, s, h, e, t):
        # Get the sum of all load shifts
        load_shifting = sum(
            getattr(model, VAR_LOADSHIFTING)[ls, s_, h_, e_, t]
            for (ls, s_, h_, e_) in getattr(model, SET_LOADSHIFTINGWITHTUPLES)
            if s_ == s and h_ == h and e_ == e
        )
        # Set constraint
        return getattr(model, VAR_LOADSHIFTINGTOTAL)[s, h, e, t] == load_shifting

    setattr(
        model,
        CON_LOADSHIFTINGTOTAL,
        Constraint(
            getattr(model, SET_LOADSHIFTINGTUPLES),
            getattr(model, SET_TIME),
            rule=__rule_load_shifting_total,
        ),
    )


def _con_load_shifting_neutrality_on_intervals(
    model: Model, load_shifting: LoadShifting, times: Times
) -> None:
    def __rule_load_shifting_neutrality_on_intervals(model, ls, s, h, e, t_hor):
        # Backlog mode (spec 05 §4, item 6): no interval blocks
        if (ls, s, h, e) in getattr(model, SET_LOADSHIFTINGBACKLOG):
            return Constraint.Skip
        # Get parameters
        interval_length = round(
            load_shifting.get_interval_length(LoadShiftId(ls)).to_float(unit=TimeUnit.H)
        )
        # Ignore edge intervals
        if t_hor + interval_length - 1 > getattr(model, SET_TIMEHORIZON).last():
            return Constraint.Skip
        # Avoid overlapping intervals by only defining the neutrality
        # constraint if t is the start id of the shift interval
        rem = (t_hor - getattr(model, SET_TIMEHORIZON).first()) % interval_length
        if rem != 0:
            return Constraint.Skip
        # Calculate load shifting balance on shift interval
        load_shifting_balance = 0
        for tau in range(t_hor, t_hor + interval_length):
            tau_clus = times.get_cluster_ts(StageId(s), TimeId(tau)).key_as_int
            load_shifting_balance += getattr(model, VAR_LOADSHIFTING)[
                ls, s, h, e, tau_clus
            ]
        # Set constraint
        return load_shifting_balance == 0

    setattr(
        model,
        CON_LOADHSHIFTINGNEUTRALITYONINTERVALS,
        Constraint(
            getattr(model, SET_LOADSHIFTINGWITHTUPLES),
            getattr(model, SET_TIMEHORIZON),
            rule=__rule_load_shifting_neutrality_on_intervals,
        ),
    )


def _con_load_shifting_neutrality_overall(model: Model, times: Times) -> None:
    def __rule_load_shifting_neutrality_overall(model, ls, s, h, e):
        # Calculate load shifting balance on entire time horizon
        load_shifting_balance = sum(
            times.get_weight(StageId(s), TimeId(t))
            * getattr(model, VAR_LOADSHIFTING)[ls, s, h, e, t]
            for t in getattr(model, SET_TIME)
        )
        # Set constraint
        return load_shifting_balance == 0

    setattr(
        model,
        CON_LOADSHIFTINGNEUTRALITYOVERALL,
        Constraint(
            getattr(model, SET_LOADSHIFTINGWITHTUPLES),
            rule=__rule_load_shifting_neutrality_overall,
        ),
    )


def _con_load_shifting_abovebelow(model: Model) -> None:
    def __rule_load_shifting_above_below(model, ls, s, h, e, t):
        # Calulate load shifting
        load_shifting = (
            getattr(model, VAR_LOADSHIFTINGABOVE)[ls, s, h, e, t]
            - getattr(model, VAR_LOADSHIFTINGBELOW)[ls, s, h, e, t]
        )
        # Set the constraint
        return getattr(model, VAR_LOADSHIFTING)[ls, s, h, e, t] == load_shifting

    setattr(
        model,
        CON_LOADSHIFTINGABOVEBLEOW,
        Constraint(
            getattr(model, SET_LOADSHIFTINGWITHTUPLES),
            getattr(model, SET_TIME),
            rule=__rule_load_shifting_above_below,
        ),
    )


def _con_load_shifting_max_abovebelow(
    model: Model,
    ecs: Ecs,
    demands: Demands,
    load_shifting: LoadShifting,
    mass_unit: MassUnit,
    power_unit: PowerUnit,
    length_unit: LengthUnit,
    passenger_unit: PassengerUnit,
    freight_unit: FreightUnit,
) -> None:
    def __rule_load_shifting_max_above(model, ls, s, h, e, t):
        # Parameters
        ec_unit = get_ec_model_unit(
            ecs.get_unit(EcId(e)),
            mass_unit,
            power_unit,
            length_unit,
            passenger_unit,
            freight_unit,
        )
        max_above_abs = (
            load_shifting.get_max_above_abs(LoadShiftId(ls))
            .get_value(TimeId(t))
            .to_float(unit=(ec_unit / TimeUnit.H))
        )
        max_above_rel = (
            load_shifting.get_max_above_rel(LoadShiftId(ls))
            .get_value(TimeId(t))
            .to_float()
        )
        demand = (
            demands.get_demand_profile(StageId(s), HubId(h), EcId(e))
            .get_value(TimeId(t))
            .to_float(unit=(ec_unit / TimeUnit.H))
        )
        # Calculate the maximal value for above-shifting
        max_above = min(max_above_abs, max_above_rel * demand)
        # Skip the constraint for infinite max
        if max_above == float("inf"):
            return Constraint.Skip
        # Set constraint
        return getattr(model, VAR_LOADSHIFTINGABOVE)[ls, s, h, e, t] <= max_above

    def __rule_load_shifting_max_below(model, ls, s, h, e, t):
        # Parameters
        ec_unit = get_ec_model_unit(
            ecs.get_unit(EcId(e)),
            mass_unit,
            power_unit,
            length_unit,
            passenger_unit,
            freight_unit,
        )
        max_below_abs = (
            load_shifting.get_max_below_abs(LoadShiftId(ls))
            .get_value(TimeId(t))
            .to_float(unit=(ec_unit / TimeUnit.H))
        )
        max_below_rel = (
            load_shifting.get_max_below_rel(LoadShiftId(ls))
            .get_value(TimeId(t))
            .to_float()
        )
        demand = (
            demands.get_demand_profile(StageId(s), HubId(h), EcId(e))
            .get_value(TimeId(t))
            .to_float(unit=(ec_unit / TimeUnit.H))
        )
        # Calculate the maximal value for below-shifting
        max_below = min(max_below_abs, max_below_rel * demand)
        # Skip the constraint for infinite max
        if max_below == float("inf"):
            return Constraint.Skip
        # Set constraint
        return getattr(model, VAR_LOADSHIFTINGBELOW)[ls, s, h, e, t] <= max_below

    setattr(
        model,
        CON_LOADSHIFTINGMAXABOVE,
        Constraint(
            getattr(model, SET_LOADSHIFTINGWITHTUPLES),
            getattr(model, SET_TIME),
            rule=__rule_load_shifting_max_above,
        ),
    )
    setattr(
        model,
        CON_LOADSHIFTINGMAXBELOW,
        Constraint(
            getattr(model, SET_LOADSHIFTINGWITHTUPLES),
            getattr(model, SET_TIME),
            rule=__rule_load_shifting_max_below,
        ),
    )


def _con_load_shifting_cap(
    model: Model,
    ecs: Ecs,
    load_shifting: LoadShifting,
    mass_unit: MassUnit,
    power_unit: PowerUnit,
    length_unit: LengthUnit,
    passenger_unit: PassengerUnit,
    freight_unit: FreightUnit,
) -> None:
    def __rule_load_shifting_cap(model, ls, s, h, e):
        var_cap = getattr(model, VAR_LOADSHIFTINGCAP)[ls, s, h, e]
        var_cap_instl = getattr(model, VAR_LOADSHIFTINGCAPINSTL)[ls, s, h, e]
        ec_unit = get_ec_model_unit(
            ecs.get_unit(EcId(e)),
            mass_unit,
            power_unit,
            length_unit,
            passenger_unit,
            freight_unit,
        )
        cap_init = load_shifting.get_cap_init(LoadShiftId(ls)).to_float(unit=ec_unit)
        return var_cap == cap_init + var_cap_instl

    setattr(
        model,
        CON_LOADSHIFTINGCAP,
        Constraint(
            getattr(model, SET_LOADSHIFTINGWITHTUPLES),
            rule=__rule_load_shifting_cap,
        ),
    )


def _con_load_shifting_cap_minmax(
    model: Model,
    ecs: Ecs,
    load_shifting: LoadShifting,
    mass_unit: MassUnit,
    power_unit: PowerUnit,
    length_unit: LengthUnit,
    passenger_unit: PassengerUnit,
    freight_unit: FreightUnit,
) -> None:
    def __rule_load_shifting_cap_min(model, ls, s, h, e):
        ec_unit = get_ec_model_unit(
            ecs.get_unit(EcId(e)),
            mass_unit,
            power_unit,
            length_unit,
            passenger_unit,
            freight_unit,
        )
        cap_min = load_shifting.get_cap_min(LoadShiftId(ls)).to_float(unit=ec_unit)
        return getattr(model, VAR_LOADSHIFTINGCAP)[ls, s, h, e] >= cap_min

    def __rule_load_shifting_cap_max(model, ls, s, h, e):
        ec_unit = get_ec_model_unit(
            ecs.get_unit(EcId(e)),
            mass_unit,
            power_unit,
            length_unit,
            passenger_unit,
            freight_unit,
        )
        cap_max = load_shifting.get_cap_max(LoadShiftId(ls)).to_float(unit=ec_unit)
        return getattr(model, VAR_LOADSHIFTINGCAP)[ls, s, h, e] <= cap_max

    setattr(
        model,
        CON_LOADSHIFTINGCAPMIN,
        Constraint(
            getattr(model, SET_LOADSHIFTINGWITHTUPLES),
            rule=__rule_load_shifting_cap_min,
        ),
    )

    setattr(
        model,
        CON_LOADSHIFTINGCAPMAX,
        Constraint(
            getattr(model, SET_LOADSHIFTINGWITHTUPLES),
            rule=__rule_load_shifting_cap_max,
        ),
    )


def _con_load_shifting_interval_cap(
    model: Model, load_shifting: LoadShifting, times: Times
) -> None:
    def __rule_load_shifting_interval_cap(model, ls, s, h, e, t_hor):
        # Backlog mode (spec 05 §4, item 6): no interval blocks
        if (ls, s, h, e) in getattr(model, SET_LOADSHIFTINGBACKLOG):
            return Constraint.Skip
        # Get parameters
        interval_length = round(
            load_shifting.get_interval_length(LoadShiftId(ls)).to_float(unit=TimeUnit.H)
        )
        var_cap = getattr(model, VAR_LOADSHIFTINGCAP)[ls, s, h, e]
        # Ignore edge intervals
        if t_hor + interval_length - 1 > getattr(model, SET_TIMEHORIZON).last():
            return Constraint.Skip
        # Avoid overlapping intervals by only defining the capacity
        # constraint if t is the start id of the shift interval
        rem = (t_hor - getattr(model, SET_TIMEHORIZON).first()) % interval_length
        if rem != 0:
            return Constraint.Skip
        # Calculate load shifting above-energy on shift interval
        load_shifting_energy = 0
        for tau in range(t_hor, t_hor + interval_length):
            tau_clus = times.get_cluster_ts(StageId(s), TimeId(tau)).key_as_int
            load_shifting_energy += getattr(model, VAR_LOADSHIFTINGABOVE)[
                ls, s, h, e, tau_clus
            ]
        # Set constraint
        return load_shifting_energy <= var_cap

    setattr(
        model,
        CON_LOADSHIFTINGINTERVALCAP,
        Constraint(
            getattr(model, SET_LOADSHIFTINGWITHTUPLES),
            getattr(model, SET_TIMEHORIZON),
            rule=__rule_load_shifting_interval_cap,
        ),
    )


def _con_load_shifting_peak(model: Model) -> None:
    def __rule_load_shifting_above_peak(model, ls, s, h, e, t):
        return (
            getattr(model, VAR_LOADSHIFTINGABOVEPEAK)[ls, s, h, e]
            >= getattr(model, VAR_LOADSHIFTINGABOVE)[ls, s, h, e, t]
        )

    def __rule_load_shifting_below_peak(model, ls, s, h, e, t):
        return (
            getattr(model, VAR_LOADSHIFTINGBELOWPEAK)[ls, s, h, e]
            >= getattr(model, VAR_LOADSHIFTINGBELOW)[ls, s, h, e, t]
        )

    setattr(
        model,
        CON_LOADSHIFTINGABOVEPEAK,
        Constraint(
            getattr(model, SET_LOADSHIFTINGWITHTUPLES),
            getattr(model, SET_TIME),
            rule=__rule_load_shifting_above_peak,
        ),
    )
    setattr(
        model,
        CON_LOADSHIFTINGBELOWPEAK,
        Constraint(
            getattr(model, SET_LOADSHIFTINGWITHTUPLES),
            getattr(model, SET_TIME),
            rule=__rule_load_shifting_below_peak,
        ),
    )


def _var_y_load_shifting(
    model: Model,
    ecs: Ecs,
    load_shifting: LoadShifting,
    currency_unit: CurrencyUnit,
    mass_unit: MassUnit,
    power_unit: PowerUnit,
    length_unit: LengthUnit,
    passenger_unit: PassengerUnit,
    freight_unit: FreightUnit,
) -> None:
    # [SET] Initialize tuple set for tuples with fix costs
    setattr(
        model,
        SET_LOADSHIFTINGWITHTUPLESFIX,
        Set(within=getattr(model, SET_LOADSHIFTINGWITHTUPLES)),
    )
    for ls, s, h, e in getattr(model, SET_LOADSHIFTINGWITHTUPLES):
        # Parameters
        fix_cost = load_shifting.get_fix_cost(LoadShiftId(ls))
        # Check if fix cost is not zero
        if not fix_cost.has_values:
            assert fix_cost.def_value is not None
            fix_cost_def = fix_cost.def_value.to_float(
                unit=(currency_unit / TimeUnit.H)
            )
            # If fix cost is zero, skip this tuple
            assert fix_cost_def is not None
            if abs(fix_cost_def) <= common.EPS_ZEROCHECK:
                continue
        # Add to fix set
        getattr(model, SET_LOADSHIFTINGWITHTUPLESFIX).add((ls, s, h, e))

    setattr(
        model,
        VAR_YLOADSHIFTING,
        Var(
            getattr(model, SET_LOADSHIFTINGWITHTUPLESFIX),
            getattr(model, SET_TIME),
            domain=Binary,
        ),
    )


def _con_y_load_shifting(
    model: Model,
    ecs: Ecs,
    demands: Demands,
    load_shifting: LoadShifting,
    mass_unit: MassUnit,
    power_unit: PowerUnit,
    length_unit: LengthUnit,
    passenger_unit: PassengerUnit,
    freight_unit: FreightUnit,
) -> None:
    def __rule_y_load_shifting(model, ls, s, h, e, t):
        # Parameters
        ec_unit = get_ec_model_unit(
            ecs.get_unit(EcId(e)),
            mass_unit,
            power_unit,
            length_unit,
            passenger_unit,
            freight_unit,
        )
        max_above_abs = (
            load_shifting.get_max_above_abs(LoadShiftId(ls))
            .get_value(TimeId(t))
            .to_float(unit=(ec_unit / TimeUnit.H))
        )
        max_above_rel = (
            load_shifting.get_max_above_rel(LoadShiftId(ls))
            .get_value(TimeId(t))
            .to_float()
        )
        max_below_abs = (
            load_shifting.get_max_below_abs(LoadShiftId(ls))
            .get_value(TimeId(t))
            .to_float(unit=(ec_unit / TimeUnit.H))
        )
        max_below_rel = (
            load_shifting.get_max_below_rel(LoadShiftId(ls))
            .get_value(TimeId(t))
            .to_float()
        )
        demand = (
            demands.get_demand_profile(StageId(s), HubId(h), EcId(e))
            .get_value(TimeId(t))
            .to_float(unit=(ec_unit / TimeUnit.H))
        )
        # Calculate upper bound for above-shifts
        max_above = min(
            max_above_abs, max_above_rel * demand, MULT_SHIFT_ABOVE_DEMAND * demand
        )
        max_below = min(
            max_below_abs, max_below_rel * demand, MULT_SHIFT_BELOW_DEMAND * demand
        )
        # Calculate the total absolute shifting
        abs_shifting = (
            getattr(model, VAR_LOADSHIFTINGABOVE)[ls, s, h, e, t]
            + getattr(model, VAR_LOADSHIFTINGBELOW)[ls, s, h, e, t]
        )
        # Calculate the upper bound for the total absolute shifting
        abs_bound = max_above + max_below
        # Set constraint
        return (
            abs_shifting
            <= abs_bound * getattr(model, VAR_YLOADSHIFTING)[ls, s, h, e, t]
        )

    setattr(
        model,
        CON_YLOADHSHIFTING,
        Constraint(
            getattr(model, SET_LOADSHIFTINGWITHTUPLESFIX),
            getattr(model, SET_TIME),
            rule=__rule_y_load_shifting,
        ),
    )


def _con_load_shifting_cost_capex(
    model: Model,
    ecs: Ecs,
    load_shifting: LoadShifting,
    currency_unit: CurrencyUnit,
    mass_unit: MassUnit,
    power_unit: PowerUnit,
    length_unit: LengthUnit,
    passenger_unit: PassengerUnit,
    freight_unit: FreightUnit,
) -> None:
    def __rule_load_shifting_cost_capex(model, ls, s, h, e):
        # Get parameters
        var_cap_instl = getattr(model, VAR_LOADSHIFTINGCAPINSTL)[ls, s, h, e]
        var_cap_cost = getattr(model, VAR_LOADSHIFTINGCOSTCAPEX)[ls, s, h, e]
        ec_unit = get_ec_model_unit(
            ecs.get_unit(EcId(e)),
            mass_unit,
            power_unit,
            length_unit,
            passenger_unit,
            freight_unit,
        )
        capex_per_cap = load_shifting.get_capex_per_cap(LoadShiftId(ls)).to_float(
            unit=(currency_unit / ec_unit)
        )
        # Set constraint
        return var_cap_cost == capex_per_cap * var_cap_instl

    setattr(
        model,
        CON_LOADSHIFTINGCOSTCAPEX,
        Constraint(
            getattr(model, SET_LOADSHIFTINGWITHTUPLES),
            rule=__rule_load_shifting_cost_capex,
        ),
    )


def _con_load_shifting_cost_energy(
    model: Model,
    ecs: Ecs,
    load_shifting: LoadShifting,
    times: Times,
    currency_unit: CurrencyUnit,
    mass_unit: MassUnit,
    power_unit: PowerUnit,
    length_unit: LengthUnit,
    passenger_unit: PassengerUnit,
    freight_unit: FreightUnit,
) -> None:
    def __rule_load_shifting_cost_energy(model, ls, s, h, e):
        # Parameters
        energy_cost_above = load_shifting.get_energy_cost_above(LoadShiftId(ls))
        energy_cost_below = load_shifting.get_energy_cost_below(LoadShiftId(ls))
        # Calculate load shifting energy cost
        ec_unit = get_ec_model_unit(
            ecs.get_unit(EcId(e)),
            mass_unit,
            power_unit,
            length_unit,
            passenger_unit,
            freight_unit,
        )
        cost = sum(
            times.get_weight(StageId(s), TimeId(t))
            * (
                energy_cost_above.get_value(TimeId(t)).to_float(
                    unit=(currency_unit / ec_unit)
                )
                * getattr(model, VAR_LOADSHIFTINGABOVE)[ls, s, h, e, t]
                + energy_cost_below.get_value(TimeId(t)).to_float(
                    unit=(currency_unit / ec_unit)
                )
                * getattr(model, VAR_LOADSHIFTINGBELOW)[ls, s, h, e, t]
            )
            for t in getattr(model, SET_TIME)
        )
        # Set constraint
        return getattr(model, VAR_LOADSHIFTINGCOSTENERGY)[ls, s, h, e] == cost

    setattr(
        model,
        CON_LOADSHIFTINGCOSTENERGY,
        Constraint(
            getattr(model, SET_LOADSHIFTINGWITHTUPLES),
            rule=__rule_load_shifting_cost_energy,
        ),
    )


def _con_load_shifting_cost_peak(
    model: Model,
    ecs: Ecs,
    load_shifting: LoadShifting,
    currency_unit: CurrencyUnit,
    mass_unit: MassUnit,
    power_unit: PowerUnit,
    length_unit: LengthUnit,
    passenger_unit: PassengerUnit,
    freight_unit: FreightUnit,
) -> None:
    def __rule_load_shifting_cost_peak(model, ls, s, h, e):
        # Parameters
        ec_unit = get_ec_model_unit(
            ecs.get_unit(EcId(e)),
            mass_unit,
            power_unit,
            length_unit,
            passenger_unit,
            freight_unit,
        )
        peak_cost_above = load_shifting.get_peak_cost_above(LoadShiftId(ls)).to_float(
            unit=(currency_unit * TimeUnit.H / ec_unit)
        )
        peak_cost_below = load_shifting.get_peak_cost_below(LoadShiftId(ls)).to_float(
            unit=(currency_unit * TimeUnit.H / ec_unit)
        )
        # Calculate load shifting peak cost
        cost = (
            peak_cost_above * getattr(model, VAR_LOADSHIFTINGABOVEPEAK)[ls, s, h, e]
            + peak_cost_below * getattr(model, VAR_LOADSHIFTINGBELOWPEAK)[ls, s, h, e]
        )
        # Set constraint
        return getattr(model, VAR_LOADSHIFTINGCOSTPEAK)[ls, s, h, e] == cost

    setattr(
        model,
        CON_LOADSHIFTINGCOSTPEAK,
        Constraint(
            getattr(model, SET_LOADSHIFTINGWITHTUPLES),
            rule=__rule_load_shifting_cost_peak,
        ),
    )


def _con_load_shifting_cost_fix(
    model: Model,
    ecs: Ecs,
    load_shifting: LoadShifting,
    times: Times,
    currency_unit: CurrencyUnit,
    mass_unit: MassUnit,
    power_unit: PowerUnit,
    length_unit: LengthUnit,
    passenger_unit: PassengerUnit,
    freight_unit: FreightUnit,
) -> None:
    def __rule_load_shifting_cost_fix(model, ls, s, h, e):
        # Parameters
        fix_cost = load_shifting.get_fix_cost(LoadShiftId(ls))
        # Calculate total fix cost
        cost = sum(
            times.get_weight(StageId(s), TimeId(t))
            * fix_cost.get_value(TimeId(t)).to_float(unit=(currency_unit / TimeUnit.H))
            * getattr(model, VAR_YLOADSHIFTING)[ls, s, h, e, t]
            for t in getattr(model, SET_TIME)
        )
        # Set constraint
        return getattr(model, VAR_LOADSHIFTINGCOSTFIX)[ls, s, h, e] == cost

    setattr(
        model,
        CON_LOADSHIFTINGCOSTFIX,
        Constraint(
            getattr(model, SET_LOADSHIFTINGWITHTUPLESFIX),
            rule=__rule_load_shifting_cost_fix,
        ),
    )


def _con_load_shifting_cost_total(model: Model) -> None:
    def __rule_load_shifting_cost_total(model):
        # Calculate total load shifting cost
        load_shifting_cost_total = sum(
            getattr(model, VAR_LOADSHIFTINGCOSTCAPEX)[ls, s, h, e]
            + getattr(model, VAR_LOADSHIFTINGCOSTENERGY)[ls, s, h, e]
            + getattr(model, VAR_LOADSHIFTINGCOSTPEAK)[ls, s, h, e]
            for (ls, s, h, e) in getattr(model, SET_LOADSHIFTINGWITHTUPLES)
        )
        # Add fix costs
        load_shifting_cost_total += sum(
            getattr(model, VAR_LOADSHIFTINGCOSTFIX)[ls, s, h, e]
            for (ls, s, h, e) in getattr(model, SET_LOADSHIFTINGWITHTUPLESFIX)
        )
        # Backlog mode (spec 05, objective (8)): lateness penalty and backlog
        # tie-break cost. They enter V_SystemCost through this total.
        load_shifting_cost_total += sum(
            getattr(model, VAR_LOADSHIFTINGCOSTLATE)[ls, s, h, e]
            + getattr(model, VAR_LOADSHIFTINGCOSTBACKLOG)[ls, s, h, e]
            for (ls, s, h, e) in getattr(model, SET_LOADSHIFTINGBACKLOG)
        )
        # Set constraint
        return getattr(model, VAR_LOADSHIFTINGCOSTTOTAL) == load_shifting_cost_total

    setattr(
        model,
        CON_LOADSHIFTINGCOSTTOTAL,
        Constraint(rule=__rule_load_shifting_cost_total),
    )
