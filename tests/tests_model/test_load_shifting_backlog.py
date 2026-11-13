"""
Tests for the backlog mode of load shifting
(docs/semester_project/formulation/05_workload_flexibility.md, §5.6).

Tiny chronological cases: one hub, one carrier IT (kWh), IT bought by import
at an hourly price, one load shift id in backlog mode. All parameter values are
placeholders chosen to make the expected optimum obvious; they are not data.
Solved with Gurobi (skipped if it is not available).
"""

import os
import textwrap

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

pytestmark = pytest.mark.skipif(
    not SolverFactory("gurobi").available(exception_flag=False),
    reason="Gurobi not available",
)

KEY = ("w1", "S1", "H1", "IT")  # (ls, stage, hub, ec)
TOL = 1e-6


# ------- #
# Helpers #
# ------- #
def _write_case(root, n, demand, price, ls_yaml="", ls_profile=None):
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
    w(
        "imports.yaml",
        "- stages: S1\n  hubs: H1\n  ec: IT\n  profile_path: profiles/imports.csv\n",
    )
    w("demands.yaml", "demand_profiles:\n- profiles/demands.csv\n" + ls_yaml)
    with open(os.path.join(prof, "imports.csv"), "w") as f:
        f.write("stage_id,S1\nhub_id,H1\nec_id,IT\nprofile_key,price\nunit,CHF/kWh\n")
        f.writelines(f"{t},{v}\n" for t, v in enumerate(price, 1))
    with open(os.path.join(prof, "demands.csv"), "w") as f:
        f.write("ec_id,IT\nstage_id,S1\nhub_id,H1\nunit,kW\n")
        f.writelines(f"{t},{v}\n" for t, v in enumerate(demand, 1))
    if ls_profile is not None:
        keys = list(ls_profile)
        with open(os.path.join(prof, "ls.csv"), "w") as f:
            f.write("loadshift_id," + ",".join("w1" for _ in keys) + "\n")
            f.write("profile_key," + ",".join(keys) + "\n")
            f.write("unit," + ",".join("kW" for _ in keys) + "\n")
            for t in range(n):
                f.write(f"{t + 1}," + ",".join(str(ls_profile[k][t]) for k in keys))
                f.write("\n")


def _backlog_yaml(extra: str, late="100 CHF/kWh/h", eps="0.0001 CHF/kWh/h") -> str:
    return (
        "load_shifting:\n"
        "- load_shift_id: w1\n"
        "  stages: S1\n"
        "  hubs: H1\n"
        "  ec: IT\n"
        "  mode: backlog\n"
        f"  late_cost: {late}\n"
        f"  backlog_cost: {eps}\n"
        "  profile_path: profiles/ls.csv\n" + textwrap.indent(extra, "  ")
    )


def _profiles(arrival, above):
    """arrival_flex = max_below_abs = theta*a(t); max_above_abs = rho*max a - a."""
    return {
        "arrival_flex": arrival,
        "max_below_abs": arrival,
        "max_above_abs": above,
    }


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


def _series(model, var_name, n):
    var = getattr(model, var_name)
    return [value(var[(*KEY, t)]) for t in range(1, n + 1)]


# ----- #
# Tests #
# ----- #
def test_zero_flex_share_equals_baseline(tmp_path):
    """§5.6: all flex shares 0 -> identical to the baseline without shifting."""
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
        ls_profile=_profiles([0.0] * n, [1.0] * n),
    )
    flex = _solve(_parse(tmp_path / "flex"))
    assert value(flex.V_SystemCost) == pytest.approx(value(base.V_SystemCost))
    assert max(abs(x) for x in _series(flex, lsm.VAR_LOADSHIFTING, n)) < TOL


def test_flat_price_no_shift(tmp_path):
    """§5.6: flat price, no heat value, eps > 0 -> s == 0 and B == 0."""
    n = 24
    _write_case(
        tmp_path,
        n,
        [2.0] * n,
        [0.2] * n,
        ls_yaml=_backlog_yaml("deadline_type: rolling\nwindow: 6 h\n"),
        ls_profile=_profiles([1.0] * n, [1.0] * n),
    )
    model = _solve(_parse(tmp_path))
    assert max(abs(x) for x in _series(model, lsm.VAR_LOADSHIFTING, n)) < TOL
    assert max(_series(model, lsm.VAR_LOADSHIFTINGBACKLOG, n)) < TOL
    assert value(model.V_SystemCost) == pytest.approx(n * 2.0 * 0.2)


def test_dip_inside_window(tmp_path):
    """
    §5.6: a price dip inside W -> work moves there and no further.
    W = 6 h, dip in hour 13: work arriving in hours 7..12 can wait until 13
    (it leaves the rhs of (3a) only at t = tau + W). Hardware cap is not
    binding (max_above_abs = 10 kW), so exactly 6 kWh move into hour 13.
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
        ls_profile=_profiles([1.0] * n, [10.0] * n),
    )
    model = _solve(_parse(tmp_path))
    s = _series(model, lsm.VAR_LOADSHIFTING, n)
    late = _series(model, lsm.VAR_LOADSHIFTINGLATE, n)
    for t in range(1, n + 1):
        expected = 6.0 if t == 13 else (-1.0 if 7 <= t <= 12 else 0.0)
        assert s[t - 1] == pytest.approx(expected, abs=TOL), f"s({t})"
    assert max(late) < TOL
    # Delay-only: backlog never negative, and zero at the end (closure (7))
    backlog = _series(model, lsm.VAR_LOADSHIFTINGBACKLOG, n)
    assert min(backlog) > -TOL and backlog[-1] == pytest.approx(0, abs=TOL)
    # opt_vars.csv: B is written with its full index (ls, s, h, e, t)
    import pandas as pd

    df = pd.read_csv(tmp_path / "results" / "opt_vars.csv")
    rows = df[df["var_name"] == lsm.VAR_LOADSHIFTINGBACKLOG]
    assert set(rows["S_Time"].astype(int)) == {7, 8, 9, 10, 11, 12}
    assert set(rows["S_LoadShiftingIds"]) == {"w1"}
    assert set(rows["S_Ec"]) == {"IT"}


def test_hardware_cap_limits_catch_up(tmp_path):
    """(5): with max_above_abs = 1 kW only 1 kWh can catch up in the dip hour."""
    n = 24
    price = [0.3] * n
    price[12] = 0.1
    _write_case(
        tmp_path,
        n,
        [2.0] * n,
        price,
        ls_yaml=_backlog_yaml("deadline_type: rolling\nwindow: 6 h\n"),
        ls_profile=_profiles([1.0] * n, [1.0] * n),
    )
    model = _solve(_parse(tmp_path))
    s = _series(model, lsm.VAR_LOADSHIFTING, n)
    assert s[12] == pytest.approx(1.0, abs=TOL)
    assert sum(abs(x) for x in s) == pytest.approx(2.0, abs=TOL)


def test_dip_beyond_window_large_penalty(tmp_path):
    """
    §5.6: a dip beyond W with large pi -> no work moves past the deadline.
    Deferrable work arrives only in hour 5, W = 6 h, dip in hour 20.
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
        ls_profile=_profiles(arrival, [10.0] * n),
    )
    model = _solve(_parse(tmp_path))
    assert max(abs(x) for x in _series(model, lsm.VAR_LOADSHIFTING, n)) < TOL
    assert max(_series(model, lsm.VAR_LOADSHIFTINGLATE, n)) < TOL


def test_dip_beyond_window_small_penalty_is_soft(tmp_path):
    """
    Soft deadline: same case with a tiny pi. Moving 1 kWh from hour 5 to 20
    saves 0.2 CHF and is late for hours 11..19 (9 h) at 0.001 CHF/(kWh h),
    so it moves and L > 0. Checks that pi is charged per kWh and hour.
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
        ls_profile=_profiles(arrival, [10.0] * n),
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


def test_calendar_backlog_zero_at_deadline(tmp_path):
    """
    §5.6: calendar deadline -> backlog is 0 at every deadline hour.
    deadline_hours [6] -> constraint at hour-of-day (t - 1) % 24 == 6.
    Work arrives in the evening of day 1; a cheap hour before the deadline
    (hod 3) and a cheaper one after it (hod 10). Work must take the first.
    """
    n = 48
    price = [0.3] * n
    price[27] = 0.15  # t = 28, hod 3 of day 2
    price[34] = 0.05  # t = 35, hod 10 of day 2 (after the deadline)
    arrival = [1.0 if 20 <= (t % 24) <= 23 else 0.0 for t in range(n)]
    _write_case(
        tmp_path,
        n,
        [2.0] * n,
        price,
        ls_yaml=_backlog_yaml("deadline_type: calendar\ndeadline_hours: [6]\n"),
        ls_profile=_profiles(arrival, [10.0] * n),
    )
    model = _solve(_parse(tmp_path))
    backlog = _series(model, lsm.VAR_LOADSHIFTINGBACKLOG, n)
    s = _series(model, lsm.VAR_LOADSHIFTING, n)
    for t in range(1, n + 1):
        if (t - 1) % 24 == 6:
            assert backlog[t - 1] == pytest.approx(0, abs=TOL), f"B({t})"
    assert s[27] == pytest.approx(4.0, abs=TOL)  # day-1 evening work, 4 kWh
    assert abs(s[34]) < TOL
    assert max(_series(model, lsm.VAR_LOADSHIFTINGLATE, n)) < TOL


def test_guard_rejects_non_unit_weights(tmp_path):
    """§4 item 7 / §5.4: backlog mode needs weights == 1 (no clustering)."""
    n = 24
    _write_case(
        tmp_path,
        n,
        [2.0] * n,
        [0.2] * n,
        ls_yaml=_backlog_yaml("deadline_type: rolling\nwindow: 6 h\n"),
        ls_profile=_profiles([1.0] * n, [1.0] * n),
    )
    ehubx = _parse(tmp_path)
    ehubx.energy_system.times.set_weight(StageId("S1"), TimeId(5), 2.0)
    with pytest.raises(core_exceptions.EhubXException):
        ehubx.build()


def test_interval_mode_unchanged(tmp_path):
    """Interval mode (default) still builds without any backlog components."""
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
        ls_profile=_profiles([1.0] * n, [1.0] * n),
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
        ls_profile={"max_below_abs": [1.0] * n, "max_above_abs": [1.0] * n},
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
        ls_profile=_profiles([1.0] * n, [1.0] * n),
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
