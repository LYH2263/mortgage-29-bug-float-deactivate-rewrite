import json

import pytest

from app import db, seed
from app.modules.rate_float import DuplicateEffectivePeriodError, RateFloatError
from app.services.mortgage_service import MortgageService, RateFloatConflict


@pytest.fixture()
def svc(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    seed.init_db()
    with MortgageService() as s:
        yield s


def test_crud_flow(svc):
    created = svc.create_rate_event(1, 13, 4.2, "次年浮动")
    assert created["enabled"] is True and created["note"] == "次年浮动"
    items = svc.list_rate_events(1)
    assert [e["id"] for e in items] == [created["id"]]

    updated = svc.update_rate_event(created["id"], 25, 4.6, "改期")
    assert updated["effective_period"] == 25 and updated["new_annual_rate"] == 4.6

    disabled = svc.disable_rate_event(created["id"])
    assert disabled["enabled"] is False


def test_create_conflict_names_existing_id(svc):
    e = svc.create_rate_event(1, 13, 4.2)
    with pytest.raises(RateFloatConflict) as ei:
        svc.create_rate_event(1, 13, 5.0)
    assert f"#{e['id']}" in str(ei.value)


def test_update_conflict_names_both_ids(svc):
    e1 = svc.create_rate_event(1, 13, 4.2)
    e2 = svc.create_rate_event(1, 25, 4.8)
    with pytest.raises(DuplicateEffectivePeriodError) as ei:
        svc.update_rate_event(e2["id"], 13, 4.8)
    assert ei.value.event_ids == [e2["id"], e1["id"]]


def test_update_disabled_event_allows_same_period(svc):
    e1 = svc.create_rate_event(1, 13, 4.2)
    e2 = svc.create_rate_event(1, 25, 4.8)
    svc.disable_rate_event(e2["id"])
    out = svc.update_rate_event(e2["id"], 13, 4.8)
    assert out["effective_period"] == 13  # 停用事件不参与冲突


@pytest.mark.parametrize("period,rate", [(1, 3.0), (361, 3.0), (13, -0.1)])
def test_field_validation(svc, period, rate):
    with pytest.raises(RateFloatError):
        svc.create_rate_event(1, period, rate)


def test_schedule_without_active_events_is_plain(svc):
    out = svc.schedule(1_000_000, 3.5, 360, 1, False)
    assert out["run_id"] is None
    assert out["rate_switches"] == []
    assert out["monthly_payment"] == 4490.45


def test_schedule_switch_and_persist(svc):
    svc.create_rate_event(1, 13, 4.2)
    out = svc.schedule(1_000_000, 3.5, 360, 1, True)
    assert out["run_id"] is not None
    sw = out["rate_switches"][0]
    assert sw["switch_period"] == 13
    assert sw["rate_before"] == 3.5 and sw["rate_after"] == 4.2
    assert sw["payment_before"] == 4490.45 and sw["payment_after"] == 4879.31

    stored = svc.history_run(out["run_id"])
    assert stored["result"]["rate_switches"] == [sw]
    assert stored["input"]["rate_event_ids"]


def test_persist_false_writes_nothing(svc):
    svc.create_rate_event(1, 13, 4.2)
    before = len(svc.history(500))
    out = svc.schedule(1_000_000, 3.5, 360, 1, False)
    after = len(svc.history(500))
    assert out["run_id"] is None and after == before


def test_disable_clears_switch_but_keeps_old_run(svc):
    e = svc.create_rate_event(1, 13, 4.2)
    persisted = svc.schedule(1_000_000, 3.5, 360, 1, True)
    old_switch = persisted["rate_switches"][0]

    svc.disable_rate_event(e["id"])
    again = svc.schedule(1_000_000, 3.5, 360, 1, False)
    assert again["rate_switches"] == []
    assert again["monthly_payment"] == 4490.45

    stored = svc.history_run(persisted["run_id"])
    assert stored["result"]["rate_switches"] == [old_switch]
    # 旧条目没有被改写成单利率表
    assert stored["result"]["rate_switches"][0]["switch_period"] == 13


def test_adhoc_schedule_ignores_events(svc):
    svc.create_rate_event(1, 13, 4.2)
    out = svc.schedule(500_000, 3.0, 120, None, False)
    assert out["rate_switches"] == [] and out["run_id"] is None


def test_missing_loan_and_event_404(svc):
    with pytest.raises(LookupError):
        svc.list_rate_events(999)
    with pytest.raises(LookupError):
        svc.disable_rate_event(9999)


fastapi = pytest.importorskip("fastapi")
httpx = pytest.importorskip("httpx")


@pytest.fixture()
def client(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "api.db")
    seed.init_db()
    from fastapi.testclient import TestClient
    from app.main import app
    with TestClient(app) as c:
        yield c


def test_api_conflict_returns_409_with_both_ids(client):
    r1 = client.post("/api/loans/1/rate-events", json={"effective_period": 13, "new_annual_rate": 4.2})
    assert r1.status_code == 201
    rid = r1.json()["id"]
    r2 = client.post("/api/loans/1/rate-events", json={"effective_period": 13, "new_annual_rate": 5.0})
    assert r2.status_code == 409
    detail = r2.json()["detail"]
    assert f"#{rid}" in detail and "第 13 期" in detail


def test_api_disable_then_switch_disappears(client):
    e = client.post("/api/loans/1/rate-events", json={"effective_period": 13, "new_annual_rate": 4.2}).json()
    on = client.post("/api/schedule", json={
        "principal": 1_000_000, "annual_rate": 3.5, "months": 360, "loan_id": 1, "persist": True})
    assert on.json()["rate_switches"][0]["switch_period"] == 13

    assert client.post(f"/api/rate-events/{e['id']}/disable").status_code == 200
    off = client.post("/api/schedule", json={
        "principal": 1_000_000, "annual_rate": 3.5, "months": 360, "loan_id": 1, "persist": False})
    assert off.json()["rate_switches"] == []


def test_api_history_detail_keeps_switch(client):
    e = client.post("/api/loans/1/rate-events", json={"effective_period": 13, "new_annual_rate": 4.2}).json()
    run = client.post("/api/schedule", json={
        "principal": 1_000_000, "annual_rate": 3.5, "months": 360, "loan_id": 1, "persist": True}).json()
    client.post(f"/api/rate-events/{e['id']}/disable")
    detail = client.get(f"/api/history/{run['run_id']}").json()
    assert detail["result"]["rate_switches"][0]["switch_period"] == 13
    assert detail["result"]["rate_switches"][0]["payment_after"] == 4879.31
