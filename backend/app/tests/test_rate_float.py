import pytest

from app.engines.amortization import equal_payment_schedule
from app.modules.rate_float import (
    DuplicateEffectivePeriodError,
    RateFloatError,
    floating_rate_schedule,
)


def test_no_events_matches_plain_equal_payment():
    base = equal_payment_schedule(1_000_000, 3.5, 360)
    out = floating_rate_schedule(1_000_000, 3.5, 360, [])
    assert out["monthly_payment"] == base["monthly_payment"]
    assert out["total_interest"] == base["total_interest"]
    assert out["total_payment"] == base["total_payment"]
    assert out["rows"] == base["rows"]
    assert out["rate_switches"] == []


def test_none_events_matches_plain_equal_payment():
    base = equal_payment_schedule(800_000, 6.8, 240)
    out = floating_rate_schedule(800_000, 6.8, 240, None)
    assert out["rows"] == base["rows"]
    assert out["rate_switches"] == []


def test_switch_annotation_values():
    base = equal_payment_schedule(1_000_000, 3.5, 360)
    events = [{"id": 7, "effective_period": 13, "new_annual_rate": 4.2, "enabled": True}]
    out = floating_rate_schedule(1_000_000, 3.5, 360, events)
    sw = out["rate_switches"]
    assert len(sw) == 1
    s = sw[0]
    assert s["switch_period"] == 13
    assert s["rate_before"] == 3.5
    assert s["rate_after"] == 4.2
    assert s["payment_before"] == base["monthly_payment"]
    assert s["payment_after"] > s["payment_before"]
    # 切换前最后一期仍是旧月供，生效期起是新月供
    assert out["rows"][11]["payment"] == s["payment_before"]
    assert out["rows"][12]["payment"] == s["payment_after"]
    assert abs(s["interest_before"] - sum(r["interest"] for r in out["rows"][:12])) < 0.05
    assert abs(s["interest_after"] - sum(r["interest"] for r in out["rows"][12:])) < 0.05
    assert out["rows"][-1]["balance"] == 0.0
    assert abs(out["total_interest"] - (s["interest_before"] + s["interest_after"])) < 0.05


def test_balance_at_switch_feeds_recompute():
    """新月供须基于切换时点余额，而非原始本金。"""
    events = [{"id": 1, "effective_period": 121, "new_annual_rate": 3.0, "enabled": True}]
    out = floating_rate_schedule(1_000_000, 3.5, 360, events)
    bal_before = out["rows"][119]["balance"]
    s = out["rate_switches"][0]
    # 手算第121期起的年金月供
    r = 3.0 / 12 / 100
    n = 240
    expect = bal_before * r * (1 + r) ** n / ((1 + r) ** n - 1)
    assert s["payment_after"] == round(expect, 2)


def test_multiple_switches_segment_interest():
    events = [
        {"id": 1, "effective_period": 13, "new_annual_rate": 4.2, "enabled": True},
        {"id": 2, "effective_period": 60, "new_annual_rate": 3.0, "enabled": True},
    ]
    out = floating_rate_schedule(1_000_000, 3.5, 360, events)
    a, b = out["rate_switches"]
    assert a["switch_period"] == 13 and b["switch_period"] == 60
    assert a["payment_after"] == b["payment_before"]
    assert a["interest_after"] == b["interest_before"]
    assert abs(
        out["total_interest"] - (a["interest_before"] + a["interest_after"] + b["interest_after"])
    ) < 0.05
    assert out["rows"][-1]["balance"] == 0.0


def test_disabled_events_ignored():
    base = equal_payment_schedule(1_000_000, 3.5, 360)
    out = floating_rate_schedule(
        1_000_000, 3.5, 360,
        [{"id": 3, "effective_period": 13, "new_annual_rate": 9.0, "enabled": False}],
    )
    assert out["rows"] == base["rows"]
    assert out["rate_switches"] == []


@pytest.mark.parametrize("period", [1, 0, -3, 361])
def test_period_out_of_range_rejected(period):
    with pytest.raises(RateFloatError):
        floating_rate_schedule(
            1_000_000, 3.5, 360,
            [{"id": 1, "effective_period": period, "new_annual_rate": 3.0, "enabled": True}],
        )


def test_negative_rate_rejected():
    with pytest.raises(RateFloatError):
        floating_rate_schedule(
            1_000_000, 3.5, 360,
            [{"id": 1, "effective_period": 13, "new_annual_rate": -0.01, "enabled": True}],
        )


def test_duplicate_period_names_both_ids():
    with pytest.raises(DuplicateEffectivePeriodError) as ei:
        floating_rate_schedule(
            1_000_000, 3.5, 360,
            [
                {"id": 11, "effective_period": 13, "new_annual_rate": 3.0, "enabled": True},
                {"id": 12, "effective_period": 13, "new_annual_rate": 4.0, "enabled": True},
            ],
        )
    assert ei.value.event_ids == [11, 12]
    assert "#11" in str(ei.value) and "#12" in str(ei.value)


def test_zero_new_rate_supported():
    events = [{"id": 1, "effective_period": 13, "new_annual_rate": 0, "enabled": True}]
    out = floating_rate_schedule(1_000_000, 3.5, 360, events)
    assert out["rate_switches"][0]["rate_after"] == 0
    assert out["rows"][-1]["balance"] == 0.0
