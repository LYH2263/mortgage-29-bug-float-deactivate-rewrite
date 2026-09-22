"""利率浮动重算模块。

在等额本息路径上按浮动事件分段：生效期之前各期沿用原年利率，
自生效期起以剩余本金（余额）与新年利率按剩余期数重算年金月供。
"""
from __future__ import annotations

from typing import Mapping, Sequence


class RateFloatError(ValueError):
    """浮动事件参数不合法。"""


class DuplicateEffectivePeriodError(RateFloatError):
    """同一贷款上存在两条生效期相同的启用事件。"""

    def __init__(self, period: int, event_ids: Sequence[int]):
        self.period = period
        self.event_ids = list(event_ids)
        ids = " 与 ".join(f"#{i}" for i in self.event_ids)
        super().__init__(f"启用浮动事件 {ids} 生效期相同（第 {period} 期）")


def _monthly_rate(annual_rate: float) -> float:
    return float(annual_rate) / 12.0 / 100.0


def _annuity_payment(balance: float, monthly_rate: float, remaining: int) -> float:
    if remaining <= 0:
        return 0.0
    if monthly_rate == 0:
        return balance / remaining
    return balance * monthly_rate * (1 + monthly_rate) ** remaining / ((1 + monthly_rate) ** remaining - 1)


def validate_events(events: Sequence[Mapping], months: int) -> list[dict]:
    """规整并校验浮动事件，返回按生效期升序的启用事件列表。

    停用事件不参与测算；生效期须大于 1 且不超过总期数，利率不得为负；
    同一贷款两条启用事件生效期相同则拒绝并点名两条标识。
    """
    active = []
    for e in events:
        if not bool(e.get("enabled", True)):
            continue
        period = int(e["effective_period"])
        rate = float(e["new_annual_rate"])
        if not (1 < period <= int(months)):
            raise RateFloatError(f"生效期须大于 1 且不超过贷款总期数（{months}），收到 {period}")
        if rate < 0:
            raise RateFloatError("新年利率不得为负")
        active.append({"id": e.get("id"), "effective_period": period, "new_annual_rate": rate})
    active.sort(key=lambda x: x["effective_period"])
    seen: dict[int, object] = {}
    for e in active:
        p = e["effective_period"]
        if p in seen:
            raise DuplicateEffectivePeriodError(p, [seen[p], e["id"]])
        seen[p] = e["id"]
    return active


def floating_rate_schedule(
    principal: float,
    annual_rate: float,
    months: int,
    events: Sequence[Mapping] | None = None,
) -> dict:
    """等额本息 + 浮动事件分段重算。

    每个启用事件在其生效期开启一个新段：以切换时点的剩余本金、
    新年利率与剩余期数重算年金月供。events 为 None 或不含启用事件时，
    数值结果与 equal_payment_schedule 完全一致（仅多出空的 rate_switches）。
    """
    P = float(principal)
    n = int(months)
    if n <= 0:
        raise ValueError("months")

    active = validate_events(events or [], n)
    boundaries = {e["effective_period"]: e for e in active}

    rows: list[dict] = []
    switches: list[dict] = []
    bal = P
    seg_annual = float(annual_rate)
    seg_rate = _monthly_rate(seg_annual)
    seg_pay = _annuity_payment(bal, seg_rate, n)
    initial_payment = seg_pay
    seg_interest = 0.0  # 当前段已累计利息（未取整）
    total_interest_raw = 0.0

    for i in range(1, n + 1):
        if i in boundaries:
            event = boundaries[i]
            # 旧段在 i-1 期结束：seg_interest 即“切换前（旧段）利息合计”
            switches.append({
                "event_id": event["id"],
                "switch_period": i,
                "rate_before": round(seg_annual, 6),
                "rate_after": round(float(event["new_annual_rate"]), 6),
                "payment_before": round(seg_pay, 2),
                "payment_after": None,
                "interest_before": round(seg_interest, 2),
                "interest_after": None,
            })
            seg_annual = float(event["new_annual_rate"])
            seg_rate = _monthly_rate(seg_annual)
            seg_pay = _annuity_payment(bal, seg_rate, n - i + 1)
            seg_interest = 0.0
            switches[-1]["payment_after"] = round(seg_pay, 2)

        interest = bal * seg_rate
        principal_part = seg_pay - interest
        if i == n:
            principal_part = bal
            pay_i = principal_part + interest
        else:
            pay_i = seg_pay
        bal = max(0.0, bal - principal_part)
        seg_interest += interest
        total_interest_raw += interest
        rows.append({
            "period": i,
            "payment": round(pay_i, 2),
            "principal": round(principal_part, 2),
            "interest": round(interest, 2),
            "balance": round(bal, 2),
        })

    # 末段利息属于最后一次切换的“切换后利息合计”；
    # 其余切换的“切换后”即下一次切换时闭合的旧段利息。
    for k in range(len(switches) - 1):
        switches[k]["interest_after"] = switches[k + 1]["interest_before"]
    if switches:
        switches[-1]["interest_after"] = round(seg_interest, 2)

    return {
        "monthly_payment": round(initial_payment, 2),
        "total_interest": round(total_interest_raw, 2),
        "total_payment": round(sum(r["payment"] for r in rows), 2),
        "rows": rows,
        "rate_switches": switches,
    }
