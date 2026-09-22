import json
from app.modules.rate_float import floating_rate_schedule
from app.repositories import rate_float, runs


def live_schedule_for_loan(conn, loan_id, principal, annual_rate, months):
    events = rate_float.active_by_loan(conn, loan_id) if loan_id else []
    full = floating_rate_schedule(principal, annual_rate, months, events)
    out = {k: full[k] for k in ("monthly_payment", "total_interest", "total_payment")}
    out["rate_switches"] = full["rate_switches"]
    preview = full["rows"][:12]
    out["preview"] = preview
    out["row_count"] = len(full["rows"])
    return out


def rewrite_loan_runs(conn, loan_id: int) -> None:
    rows = conn.execute(
        "SELECT id, input_json FROM calc_runs WHERE loan_id=? AND kind='schedule'",
        (loan_id,),
    ).fetchall()
    for row in rows:
        payload = json.loads(row["input_json"] or "{}")
        fresh = live_schedule_for_loan(
            conn,
            loan_id,
            payload.get("principal"),
            payload.get("annual_rate"),
            payload.get("months"),
        )
        runs.replace_result(conn, int(row["id"]), fresh)
