import json

from app.db import connect
from app.engines.amortization import equal_payment_schedule
from app.modules.rate_float import (
    DuplicateEffectivePeriodError,
    RateFloatError,
    floating_rate_schedule,
)
from app.repositories import loans, rate_float, runs, settings


class RateFloatConflict(RateFloatError):
    """新建/更新事件与已有启用事件生效期冲突。"""


class MortgageService:
    def __init__(self): self._c = connect()
    def close(self): self._c.close()
    def __enter__(self): return self
    def __exit__(self, *a): self.close()
    def list_loans(self): return loans.list_all(self._c)
    def loan(self, lid): return loans.get(self._c, lid)
    def settings(self): return settings.get_map(self._c)
    def history(self, limit=50): return runs.list_recent(self._c, limit)
    def history_run(self, rid):
        row = runs.get(self._c, rid)
        if not row:
            return None
        return {
            "id": row["id"], "kind": row["kind"], "loan_id": row["loan_id"],
            "created_at": row["created_at"],
            "input": json.loads(row["input_json"] or "{}"),
            "result": json.loads(row["result_json"] or "{}"),
        }

    # ---- 利率浮动事件 -------------------------------------------------
    def _require_loan(self, loan_id) -> dict:
        loan = loans.get(self._c, loan_id)
        if not loan:
            raise LookupError(f"贷款 #{loan_id} 不存在")
        return loan

    def list_rate_events(self, loan_id):
        self._require_loan(loan_id)
        return rate_float.list_by_loan(self._c, loan_id)

    def create_rate_event(self, loan_id, effective_period, new_annual_rate, note=""):
        loan = self._require_loan(loan_id)
        self._validate_fields(loan, effective_period, new_annual_rate)
        conflicts = rate_float.find_enabled_conflict(self._c, loan_id, effective_period)
        if conflicts:
            labels = [f"#{c['id']}" for c in conflicts] + ["新建事件"]
            raise RateFloatConflict(
                f"启用浮动事件 {' 与 '.join(labels)} 生效期相同（第 {effective_period} 期）")
        eid = rate_float.insert(self._c, loan_id, effective_period, new_annual_rate, note or "")
        return rate_float.get(self._c, eid)

    def update_rate_event(self, event_id, effective_period, new_annual_rate, note=""):
        event = rate_float.get(self._c, event_id)
        if not event:
            raise LookupError(f"浮动事件 #{event_id} 不存在")
        loan = self._require_loan(event["loan_id"])
        self._validate_fields(loan, effective_period, new_annual_rate)
        if event["enabled"]:
            conflicts = rate_float.find_enabled_conflict(
                self._c, event["loan_id"], effective_period, exclude_id=event_id)
            if conflicts:
                ids = [event_id] + [c["id"] for c in conflicts]
                raise DuplicateEffectivePeriodError(effective_period, ids)
        rate_float.update(self._c, event_id, effective_period, new_annual_rate, note or "")
        return rate_float.get(self._c, event_id)

    def disable_rate_event(self, event_id):
        event = rate_float.get(self._c, event_id)
        if not event:
            raise LookupError(f"浮动事件 #{event_id} 不存在")
        # 仅翻转启用标志：停用只影响之后的新测算，不得改写已落库的历史结果
        rate_float.set_enabled(self._c, event_id, False)
        return rate_float.get(self._c, event_id)

    @staticmethod
    def _validate_fields(loan, effective_period, new_annual_rate):
        months = int(loan["months"])
        if not (1 < int(effective_period) <= months):
            raise RateFloatError(f"生效期须大于 1 且不超过贷款总期数（{months}），收到 {effective_period}")
        if float(new_annual_rate) < 0:
            raise RateFloatError("新年利率不得为负")

    # ---- 测算 ---------------------------------------------------------
    def schedule(self, principal, annual_rate, months, loan_id, persist, preview_rows=12):
        events = []
        if loan_id is not None:
            self._require_loan(loan_id)
            events = rate_float.active_by_loan(self._c, loan_id)
        full = floating_rate_schedule(principal, annual_rate, months, events)
        out = {k: full[k] for k in ("monthly_payment", "total_interest", "total_payment")}
        out["preview"] = full["rows"][:preview_rows]
        out["row_count"] = len(full["rows"])
        out["rate_switches"] = full["rate_switches"]
        rid = None
        if persist:
            payload = {
                "principal": principal, "annual_rate": annual_rate, "months": months,
                "rate_event_ids": [e["id"] for e in events],
            }
            rid = runs.insert(self._c, "schedule", payload, out, loan_id)
        return {"run_id": rid, **out}

    def dashboard(self):
        items = loans.list_all(self._c)
        return {"loan_count": len(items), "clean": len([x for x in items if "种子" not in x["name"]]), "dirty": len([x for x in items if "种子" in x["name"]])}
