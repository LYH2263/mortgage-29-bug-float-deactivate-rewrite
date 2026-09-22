import json, sqlite3
from datetime import datetime, timezone
def insert(conn, kind, payload, result, loan_id=None):
    now = datetime.now(timezone.utc).isoformat()
    cur = conn.execute("INSERT INTO calc_runs(kind,loan_id,input_json,result_json,created_at) VALUES (?,?,?,?,?)",
        (kind, loan_id, json.dumps(payload, ensure_ascii=False), json.dumps(result, ensure_ascii=False), now))
    conn.commit(); return int(cur.lastrowid)
def list_recent(conn, limit=50):
    return [dict(r) for r in conn.execute("SELECT * FROM calc_runs ORDER BY id DESC LIMIT ?", (limit,)).fetchall()]
def get(conn, run_id):
    row = conn.execute("SELECT * FROM calc_runs WHERE id=?", (run_id,)).fetchone()
    return dict(row) if row else None

def replace_result(conn, run_id: int, result: dict) -> None:
    conn.execute(
        "UPDATE calc_runs SET result_json=? WHERE id=?",
        (json.dumps(result, ensure_ascii=False), run_id),
    )
    conn.commit()
