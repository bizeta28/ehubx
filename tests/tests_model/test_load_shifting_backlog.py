"""
Tests for the backlog mode of load shifting
(docs/semester_project/formulation/05_workload_flexibility.md, v3, §5.1).

Tiny chronological cases: one hub, one carrier IT (kWh), IT bought by import
at an hourly price, one or two load shift ids in backlog mode. All parameter
values are placeholders chosen to make the expected optimum obvious; they are
not data. Solved with Gurobi (skipped if it is not available).

v3 (13 Nov 2026): no max_above_abs column (the per-archetype cap rho_w was
dropped; (5) is the shared capacity), calendar deadline at t mod 24 = h^D,
result rows TAC_sys, sum L and eps * sum B.
"""

import os
import textwrap

import pandas as pd
import pytest
from pyomo.core import value
from pyomo.environ import SolverFactory

from ehubx import EhubX, Gurobi, ObjectiveType
from ehubx.core import exceptions as core_exceptions
from ehubx.data import exceptions as data_exceptions
from ehubx.data.stage_data import StageId
from ehubx.data.time_data import TimeId
from ehubx.model import load_shifting_model as lsm
from ehubx.parser import exceptions as parser_exceptions
from ehubx.writer import energy_system_writer as esw
from ehubx.writer import load_shifting_writer as lsw

pytestmark = pytest.mark.skipif(
    not SolverFactory("gurobi").available(exception_flag=False),
    reason="Gurobi not available",
)

KEY = ("w1", "S1", "H1", "IT")  # (ls, stage, hub, ec)
KEY2 = ("w2", "S1", "H1", "IT")
TOL = 1e-6


# ------- #
# Helpers #
# ------- #
def _write_case(
    root, n, demand, price, ls_yaml="", ls_profile=None, ls_profiles=None, import_max=None
):
    """
    ls_profile:  {profile_key: values} for load shift id w1 (convenience).
    ls_profiles: {ls_id: {profile_key: values}} for several ids in one CSV.
    import_max:  hourly cap on the IT import [kW] (shared capacity, spec (5)).
    """
    basic = os.path.join(root, "inputs", "basic")
    prof = os.path.join(basic, "profiles")
    os.makedirs(prof, exist_ok=True)

    def w(name, txt):
        with open(os.path.join(basic, name), "w") as f:
            f.write(textwrap.dedent(txt))

    w(
        "stages.yaml",
        f"""\
        system_params:
          interest_rate_def: 0.1
          num_times_horizon: {n}
          currency_unit: CHF
          power_unit: kW
        stages:
        - stage_id: S1
          start_year: 2025
        """,
    )
    w("hubs.yaml", "hubs:\n- hub_id: H1\n")
    w("ecs.yaml", "ecs:\n- ec_id: IT\n  unit: kWh\n")
    imp = "- stages: S1\n  hubs: H1\n  ec: IT\n  profile_path: profiles/imports.csv\n"
    if import_max is not None:
        imp += f"  max: {import_max} kW\n"
    w("imports.yaml", imp)
    w("demands.yaml", "demand_profiles:\n- profiles/demands.csv\n" + ls_yaml)
    with open(os.path.join(prof, "imports.csv"), "w") as f:
        f.write("stage_id,S1\nhub_id,H1\nec_id,IT\nprofile_key,price\nunit,CHF/kWh\n")
        f.writelines(f"{t},{v}\n" for t, v in enumerate(price, 1))
    with open(os.path.join(prof, "demands.csv"), "w") as f:
        f.write("ec_id,IT\nstage_id,S1\nhub_id,H1\nunit,kW\n")
        f.writelines(f"{t},{v}\n" for t, v in enumerate(demand, 1))
    if ls_profile is not None:
        ls_profiles = {"w1": ls_profile}
    if ls_profiles is not None:
        cols = [(ls, k) for ls, keys in ls_profiles.items() for k in keys]
        with open(os.path.join(prof, "ls.csv"), "w") as f:
            f.write("loadshift_id," + ",".join(ls for ls, _ in cols) + "\n")
            f.write("profile_key," + ",".join(k for _, k in cols) + "\n")
            f.write("unit," + ",".join("kW" for _ in cols) + "\n")
            for t in range(n):
                f.write(f"{t + 1},")
                f.write(",".join(str(ls_profiles[ls][k][t]) for ls, k in cols))
                f.write("\n")


def _backlog_yaml(
    extra: str, late="100 CHF/kWh/h", eps="0.0001 CHF/kWh/h", ids=("w1",)
) -> str:
    out = "load_shifting:\n"
    for ls in ids:
        out += (
            f"- load_shift_id: {ls}\n"
            "  stages: S1\n"
            "  hubs: H1\n"
            "  ec: IT\n"
            "  mode: backlog\n"
            f"  late_cost: {late}\n"
            f"  backlog_cost: {eps}\n"
            "  profile_path: profiles/ls.csv\n" + textwrap.indent(extra, "  ")
        )
    return out


def _profiles(arrival):
    """arrival_flex = max_below_abs = theta_w * a_w(t) (spec (3a), (4)).
    No max_above_abs: v3 has no per-archetype catch-up cap."""
    return {"arrival_flex": arrival, "max_below_abs": arrival}


def _parse(root):
    ehubx = EhubX()
    ehubx.model_dir_path = str(root)
    ehubx.parse()
    return ehubx


def _solve(ehubx):
    ehubx.build()
    ehubx.set_solver(Gurobi())
    ehubx.solve_single_obj(obj_type=ObjectiveType.COST, write_model=False)
    return ehubx._model


def _series(model, var_name, n, key=KEY):
    var = getattr(model, var_name)
    return [value(var[(*key, t)]) for t in range(1, n + 1)]


def _row_values(csv_path, entry, **filters):
    """Values of the result rows with a given Entry (and optional column filters)."""
    df = pd.read_csv(csv_path, keep_default_na=False)
    df = df[df["Entry"] == entry]
    for col, val in filters.items():
        df = df[df[col] == val]
    return [float(v) for v in df["Value"]]


# ----- #
# Tests #
# ----- #
def test_zero_flex_share_equals_baseline(tmp_path):
    """§5.3: theta = 0 (arrival_flex = max_below_abs = 0) -> identical to the
    baseline without load shifting."""
    n = 24
    demand = [2.0] * n
    price = [0.3] * n
    price[12] = 0.05  # a dip that would attract shifted work
    _write_case(tmp_path / "base", n, demand, price)
    base = _solve(_parse(tmp_path / "base"))
    _write_case(
        tmp_path / "flex",
        n,
        demand,
        price,
        ls_yaml=_backlog_yaml("deadline_type: rolling\nwindow: 6 h\n"),
        ls_profile=_profiles([0.0] * n),
    )
    flex = _solve(_parse(tmp_path / "flex"))
    assert value(flex.V_SystemCost) == pytest.approx(value(base.V_SystemCost))
    assert max(abs(x) for x in _series(flex, lsm.VAR_LOADSHIFTING, n)) < TOL
    # TAC_sys row equals V_SystemCost (no penalties incurred)
    tac_sys = _row_values(tmp_path / "flex" / "results" / "system.csv", esw.ENTRY_SYSTEMCOSTNOPENALTY)
    assert tac_sys == [pytest.approx(value(base.V_SystemCost))]


def test_flat_price_no_shift(tmp_path):
    """Flat price, no heat value, eps > 0 -> s == 0 and B == 0."""
    n = 24
    _write_case(
        tmp_path,
        n,
        [2.0] * n,
        [0.2] * n,
        ls_yaml=_backlog_yaml("deadline_type: rolling\nwindow: 6 h\n"),
        ls_profile=_profiles([1.0] * n),
    )
    model = _solve(_parse(tmp_path))
    assert max(abs(x) for x in _series(model, lsm.VAR_LOADSHIFTING, n)) < TOL
    assert max(_series(model, lsm.VAR_LOADSHIFTINGBACKLOG, n)) < TOL
    assert value(model.V_SystemCost) == pytest.approx(n * 2.0 * 0.2)


def test_dip_inside_window(tmp_path):
    """
    A price dip inside W -> work moves there and no further.
    W = 6 h, dip in hour 13: work arriving in hours 7..12 can wait until 13
    (it leaves the rhs of (3a) only at t = tau + W, §3 (3a) and §6.6).
    Without max_above_abs nothing in the load shifting module limits the
    catch-up, so exactly 6 kWh move into hour 13. Also checks the v3 result
    rows (§4 reporting): TAC_sys, sum L and eps * sum B.
    """
    n = 24
    price = [0.3] * n
    price[12] = 0.1  # hour t = 13
    _write_case(
        tmp_path,
        n,
        [2.0] * n,
        price,
        ls_yaml=_backlog_yaml("deadline_type: rolling\nwindow: 6 h\n"),
        ls_profile=_profiles([1.0] * n),
    )
    model = _solve(_parse(tmp_path))
    s = _series(model, lsm.VAR_LOADSHIFTING, n)
    late = _series(model, lsm.VAR_LOADSHIFTINGLATE, n)
    for t in range(1, n + 1):
        expected = 6.0 if t == 13 else (-1.0 if 7 <= t <= 12 else 0.0)
        assert s[t - 1] == pytest.approx(expected, abs=TOL), f"s({t})"
    assert max(late) < TOL
    # Delay-only: backlog never negative, and zero at the end (closure (6))
    backlog = _series(model, lsm.VAR_LOADSHIFTINGBACKLOG, n)
    assert min(backlog) > -TOL and backlog[-1] == pytest.approx(0, abs=TOL)
    # (5) is not enforced by the load shifting module: max_above_abs omitted
    # -> default infinity -> C_LoadShiftingMaxAbove has no member.
    assert len(getattr(model, lsm.CON_LOADSHIFTINGMAXABOVE)) == 0
    # opt_vars.csv: B is written with its full index (ls, s, h, e, t)
    df = pd.read_csv(tmp_path / "results" / "opt_vars.csv")
    rows = df[df["var_name"] == lsm.VAR_LOADSHIFTINGBACKLOG]
    assert set(rows["S_Time"].astype(int)) == {7, 8, 9, 10, 11, 12}
    assert set(rows["S_LoadShiftingIds"]) == {"w1"}
    assert set(rows["S_Ec"]) == {"IT"}
    # Result rows (§4 reporting). sum B = 1+2+3+4+5+6 = 21 kWh h -> eps*21.
    cost_backlog = value(getattr(model, lsm.VAR_LOADSHIFTINGCOSTBACKLOG)[KEY])
    assert cost_backlog == pytest.approx(21 * 0.0001, abs=1e-9)
    system_csv = tmp_path / "results" / "system.csv"
    tac_sys = _row_values(system_csv, esw.ENTRY_SYSTEMCOSTNOPENALTY)
    assert tac_sys == [pytest.approx(value(model.V_SystemCost) - cost_backlog)]
    assert _row_values(system_csv, esw.ENTRY_LOADSHIFTINGCOSTLATETOTAL) == [0.0]
    assert _row_values(system_csv, esw.ENTRY_LOADSHIFTINGCOSTBACKLOGTOTAL) == [
        pytest.approx(cost_backlog)
    ]
    assert _row_values(system_csv, esw.ENTRY_LOADSHIFTINGLATETOTAL, Ec="IT") == [0.0]
    loads_csv = tmp_path / "results" / "loads_S1_H1_IT.csv"  # tuple rows (default granularity)
    assert _row_values(
        loads_csv, lsw.ENTRY_LOADSHIFTINGLATESUM, **{"Load shift": "w1"}
    ) == [0.0]
    assert _row_values(
        loads_csv, lsw.ENTRY_LOADSHIFTINGCOSTBACKLOG, **{"Load shift": "w1"}
    ) == [pytest.approx(cost_backlog)]


def test_shared_capacity_limits_catch_up(tmp_path):
    """
    (5): all archetypes share the hardware. Two rolling archetypes w1, w2,
    both with 1 kW deferrable arrivals, and an import cap of 3 kW on IT
    (stand-in for Cap_DC with d_IT = 2 kW): together they can catch up at
    most 1 kWh in the dip hour, whatever the split between them.
    """
    n = 24
    price = [0.3] * n
    price[12] = 0.1
    _write_case(
        tmp_path,
        n,
        [2.0] * n,
        price,
        ls_yaml=_backlog_yaml(
            "deadline_type: rolling\nwindow: 6 h\n", ids=("w1", "w2")
        ),
        ls_profiles={"w1": _profiles([1.0] * n), "w2": _profiles([1.0] * n)},
        import_max=3.0,
    )
    model = _solve(_parse(tmp_path))
    s1 = _series(model, lsm.VAR_LOADSHIFTING, n, KEY)
    s2 = _series(model, lsm.VAR_LOADSHIFTING, n, KEY2)
    assert s1[12] + s2[12] == pytest.approx(1.0, abs=TOL)
    assert sum(abs(x) for x in s1 + s2) == pytest.approx(2.0, abs=TOL)
    assert max(_series(model, lsm.VAR_LOADSHIFTINGLATE, n, KEY)) < TOL
    assert max(_series(model, lsm.VAR_LOADSHIFTINGLATE, n, KEY2)) < TOL


def test_explicit_max_above_abs_still_applies(tmp_path):
    """max_above_abs is not part of v3, but if an input still gives it, the
    value is applied as given (and a warning is logged)."""
    n = 24
    price = [0.3] * n
    price[12] = 0.1
    _write_case(
        tmp_path,
        n,
        [2.0] * n,
        price,
        ls_yaml=_backlog_yaml("deadline_type: rolling\nwindow: 6 h\n"),
        ls_profile={**_profiles([1.0] * n), "max_above_abs": [1.0] * n},
    )
    model = _solve(_parse(tmp_path))
    s = _series(model, lsm.VAR_LOADSHIFTING, n)
    assert s[12] == pytest.approx(1.0, abs=TOL)
    assert sum(abs(x) for x in s) == pytest.approx(2.0, abs=TOL)


def test_dip_beyond_window_large_penalty(tmp_path):
    """
    A dip beyond W with large pi -> no work moves past the deadline, L == 0
    (§3 (8): hard deadline). Deferrable work arrives only in hour 5, W = 6 h,
    dip in hour 20.
    """
    n = 24
    price = [0.3] * n
    price[19] = 0.1  # hour 20
    arrival = [0.0] * n
    arrival[4] = 1.0  # hour 5
    _write_case(
        tmp_path,
        n,
        [2.0] * n,
        price,
        ls_yaml=_backlog_yaml("deadline_type: rolling\nwindow: 6 h\n"),
        ls_profile=_profiles(arrival),
    )
    model = _solve(_parse(tmp_path))
    assert max(abs(x) for x in _series(model, lsm.VAR_LOADSHIFTING, n)) < TOL
    assert max(_series(model, lsm.VAR_LOADSHIFTINGLATE, n)) < TOL


def test_dip_beyond_window_small_penalty_is_soft(tmp_path):
    """
    Soft deadline: same case with a tiny pi. Moving 1 kWh from hour 5 to 20
    saves 0.2 CHF and is late for hours 11..19 (9 h) at 0.001 CHF/(kWh h),
    so it moves and L > 0. Checks that pi is charged per kWh and hour, and
    that the result rows report sum L = 9 kWh h and TAC_sys net of pi sum L.
    """
    n = 24
    price = [0.3] * n
    price[19] = 0.1
    arrival = [0.0] * n
    arrival[4] = 1.0
    _write_case(
        tmp_path,
        n,
        [2.0] * n,
        price,
        ls_yaml=_backlog_yaml(
            "deadline_type: rolling\nwindow: 6 h\n", late="0.001 CHF/kWh/h"
        ),
        ls_profile=_profiles(arrival),
    )
    model = _solve(_parse(tmp_path))
    s = _series(model, lsm.VAR_LOADSHIFTING, n)
    late = _series(model, lsm.VAR_LOADSHIFTINGLATE, n)
    assert s[4] == pytest.approx(-1.0, abs=TOL)
    assert s[19] == pytest.approx(1.0, abs=TOL)
    # late in hours 11..19 (rhs of (3a) is 0 there), 1 kWh each
    assert sum(late) == pytest.approx(9.0, abs=TOL)
    cost_late = value(getattr(model, lsm.VAR_LOADSHIFTINGCOSTLATE)[KEY])
    assert cost_late == pytest.approx(9 * 0.001, abs=1e-9)
    cost_backlog = value(getattr(model, lsm.VAR_LOADSHIFTINGCOSTBACKLOG)[KEY])
    system_csv = tmp_path / "results" / "system.csv"
    assert _row_values(system_csv, esw.ENTRY_LOADSHIFTINGLATETOTAL, Ec="IT") == [
        pytest.approx(9.0, abs=TOL)
    ]
    assert _row_values(system_csv, esw.ENTRY_SYSTEMCOSTNOPENALTY) == [
        pytest.approx(value(model.V_SystemCost) - cost_late - cost_backlog)
    ]
    assert _row_values(
        tmp_path / "results" / "loads_S1_H1_IT.csv",
        lsw.ENTRY_LOADSHIFTINGLATESUM,
        **{"Load shift": "w1"},
    ) == [pytest.approx(9.0, abs=TOL)]


def test_calendar_backlog_zero_at_deadline(tmp_path):
    """
    §5.1: calendar deadline -> B(t) = 0 at the end of every hour with
    t mod 24 = h^D (queue empty at h^D:00 model time). deadline_hours [6]
    -> t = 6, 30. Work arrives in hours 21..24 of day 1. A cheap hour at
    t = 30 (the deadline hour itself, work may still run in it) and a cheaper
    one at t = 31 (right after the deadline). Work must take t = 30.
    The v2 convention ((t-1) mod 24 = h, i.e. t = 31) would take t = 31.
    """
    n = 48
    price = [0.3] * n
    price[29] = 0.15  # t = 30: ends at 06:00 -> last hour before the deadline
    price[30] = 0.05  # t = 31: after the deadline
    arrival = [1.0 if 21 <= t <= 24 else 0.0 for t in range(1, n + 1)]
    _write_case(
        tmp_path,
        n,
        [2.0] * n,
        price,
        ls_yaml=_backlog_yaml("deadline_type: calendar\ndeadline_hours: [6]\n"),
        ls_profile=_profiles(arrival),
    )
    model = _solve(_parse(tmp_path))
    backlog = _series(model, lsm.VAR_LOADSHIFTINGBACKLOG, n)
    s = _series(model, lsm.VAR_LOADSHIFTING, n)
    for t in range(1, n + 1):
        if t % 24 == 6:
            assert backlog[t - 1] == pytest.approx(0, abs=TOL), f"B({t})"
    assert s[29] == pytest.approx(4.0, abs=TOL)  # day-1 evening work, 4 kWh
    assert abs(s[30]) < TOL
    assert backlog[28] == pytest.approx(4.0, abs=TOL)  # B(29): still queued
    assert max(_series(model, lsm.VAR_LOADSHIFTINGLATE, n)) < TOL
    # The constraint exists exactly at the deadline hours
    con = getattr(model, lsm.CON_LOADSHIFTINGDEADLINE)
    assert sorted(t for (*_, t) in con.keys()) == [6, 30]


def test_calendar_hour_zero_is_end_of_hour_24(tmp_path):
    """deadline_hours [0]: t mod 24 = 0 -> t = 24, 48 (queue empty at
    00:00). Work from hours 21..23 may still run in hour 24, not in 25."""
    n = 48
    price = [0.3] * n
    price[23] = 0.15  # t = 24
    price[24] = 0.05  # t = 25
    arrival = [1.0 if 21 <= t <= 23 else 0.0 for t in range(1, n + 1)]
    _write_case(
        tmp_path,
        n,
        [2.0] * n,
        price,
        ls_yaml=_backlog_yaml("deadline_type: calendar\ndeadline_hours: [0]\n"),
        ls_profile=_profiles(arrival),
    )
    model = _solve(_parse(tmp_path))
    s = _series(model, lsm.VAR_LOADSHIFTING, n)
    assert s[23] == pytest.approx(3.0, abs=TOL)
    assert abs(s[24]) < TOL
    con = getattr(model, lsm.CON_LOADSHIFTINGDEADLINE)
    assert sorted(t for (*_, t) in con.keys()) == [24, 48]


def test_guard_rejects_non_unit_weights(tmp_path):
    """§5.4 / chronology guard: backlog mode needs weights == 1 (no clustering)."""
    n = 24
    _write_case(
        tmp_path,
        n,
        [2.0] * n,
        [0.2] * n,
        ls_yaml=_backlog_yaml("deadline_type: rolling\nwindow: 6 h\n"),
        ls_profile=_profiles([1.0] * n),
    )
    ehubx = _parse(tmp_path)
    ehubx.energy_system.times.set_weight(StageId("S1"), TimeId(5), 2.0)
    with pytest.raises(core_exceptions.EhubXException):
        ehubx.build()


def test_interval_mode_unchanged(tmp_path):
    """Interval mode (default) still builds without any backlog components,
    and without the v3 result rows."""
    n = 24
    price = [0.3] * n
    price[12] = 0.1
    _write_case(
        tmp_path,
        n,
        [2.0] * n,
        price,
        ls_yaml=(
            "load_shifting:\n- load_shift_id: w1\n  stages: S1\n  hubs: H1\n"
            "  ec: IT\n  interval_length: 24 h\n  max_above_abs: 1 kW\n"
            "  max_below_abs: 1 kW\n"
        ),
    )
    model = _solve(_parse(tmp_path))
    assert len(getattr(model, lsm.SET_LOADSHIFTINGBACKLOG)) == 0
    assert not hasattr(model, lsm.CON_LOADSHIFTINGBACKLOG)
    # bidirectional: the dip hour gains exactly max_above_abs
    s = _series(model, lsm.VAR_LOADSHIFTING, n)
    assert s[12] == pytest.approx(1.0, abs=TOL)
    assert _row_values(tmp_path / "results" / "system.csv", esw.ENTRY_SYSTEMCOSTNOPENALTY) == []


# ---------------------------- #
# Input validation (no solve)  #
# ---------------------------- #
@pytest.mark.parametrize(
    "extra, late",
    [
        ("deadline_type: rolling\n", "1 CHF/kWh/h"),  # window missing
        ("window: 6 h\n", "1 CHF/kWh/h"),  # deadline_type missing
        ("deadline_type: calendar\n", "1 CHF/kWh/h"),  # deadline_hours missing
        ("deadline_type: calendar\ndeadline_hours: [24]\n", "1 CHF/kWh/h"),
        ("deadline_type: rolling\nwindow: 6 h\nfix_cost: 1 CHF/h\n", "1 CHF/kWh/h"),
        ("deadline_type: rolling\nwindow: 6 h\n", "-1 CHF/kWh/h"),
    ],
)
def test_validation_errors(tmp_path, extra, late):
    n = 24
    _write_case(
        tmp_path,
        n,
        [2.0] * n,
        [0.2] * n,
        ls_yaml=_backlog_yaml(extra, late=late),
        ls_profile=_profiles([1.0] * n),
    )
    with pytest.raises(data_exceptions.DataException):
        _parse(tmp_path).build()


def test_rolling_requires_arrival_flex(tmp_path):
    n = 24
    _write_case(
        tmp_path,
        n,
        [2.0] * n,
        [0.2] * n,
        ls_yaml=_backlog_yaml("deadline_type: rolling\nwindow: 6 h\n"),
        ls_profile={"max_below_abs": [1.0] * n},
    )
    with pytest.raises(data_exceptions.DataException):
        _parse(tmp_path).build()


def test_late_cost_unit_per_kwh_rejected(tmp_path):
    """late_cost is per kWh and hour (spec §2); 'CHF/kWh' is rejected."""
    n = 24
    _write_case(
        tmp_path,
        n,
        [2.0] * n,
        [0.2] * n,
        ls_yaml=_backlog_yaml("deadline_type: rolling\nwindow: 6 h\n", late="1 CHF/kWh"),
        ls_profile=_profiles([1.0] * n),
    )
    with pytest.raises(parser_exceptions.InvalidValueException):
        _parse(tmp_path)


def test_backlog_keys_rejected_in_interval_mode(tmp_path):
    n = 24
    _write_case(
        tmp_path,
        n,
        [2.0] * n,
        [0.2] * n,
        ls_yaml=(
            "load_shifting:\n- load_shift_id: w1\n  stages: S1\n  hubs: H1\n"
            "  ec: IT\n  interval_length: 24 h\n  window: 6 h\n"
        ),
    )
    with pytest.raises(data_exceptions.DataException):
        _parse(tmp_path).build()
