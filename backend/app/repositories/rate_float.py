from datetime import datetime, timezone


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _row(row):
    if row is None:
        return None
    d = dict(row)
    d["enabled"] = bool(d.get("enabled", 1))
    return d


def list_by_loan(conn, loan_id: int, only_enabled: bool = False) -> list[dict]:
    sql = "SELECT * FROM rate_float_events WHERE loan_id=?"
    if only_enabled:
        sql += " AND enabled=1"
    sql += " ORDER BY effective_period, id"
    return [_row(r) for r in conn.execute(sql, (loan_id,)).fetchall()]


def active_by_loan(conn, loan_id: int) -> list[dict]:
    return list_by_loan(conn, loan_id, only_enabled=True)


def get(conn, event_id: int) -> dict | None:
    return _row(conn.execute("SELECT * FROM rate_float_events WHERE id=?", (event_id,)).fetchone())


def insert(conn, loan_id: int, effective_period: int, new_annual_rate: float, note: str = "") -> int:
    now = _now()
    cur = conn.execute(
        "INSERT INTO rate_float_events(loan_id,effective_period,new_annual_rate,enabled,note,created_at,updated_at)"
        " VALUES (?,?,?,1,?,?,?)",
        (loan_id, effective_period, new_annual_rate, note, now, now))
    conn.commit()
    return int(cur.lastrowid)


def update(conn, event_id: int, effective_period: int, new_annual_rate: float, note: str) -> None:
    conn.execute(
        "UPDATE rate_float_events SET effective_period=?, new_annual_rate=?, note=?, updated_at=?"
        " WHERE id=?",
        (effective_period, new_annual_rate, note, _now(), event_id))
    conn.commit()


def set_enabled(conn, event_id: int, enabled: bool) -> None:
    conn.execute(
        "UPDATE rate_float_events SET enabled=?, updated_at=? WHERE id=?",
        (1 if enabled else 0, _now(), event_id))
    conn.commit()


def find_enabled_conflict(conn, loan_id: int, effective_period: int, exclude_id: int | None = None) -> list[dict]:
    sql = "SELECT * FROM rate_float_events WHERE loan_id=? AND enabled=1 AND effective_period=?"
    params: list = [loan_id, effective_period]
    if exclude_id is not None:
        sql += " AND id<>?"
        params.append(exclude_id)
    return [_row(r) for r in conn.execute(sql, params).fetchall()]
