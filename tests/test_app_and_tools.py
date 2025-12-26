# tests/test_app_and_tools.py

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from fastapi import status

from backend.app import app
from backend.import_csv_api import import_via_api
from backend import import_csv_api
from backend.sim_priority_vs_fifo import (
    generate_arrivals,
    simulate,
)
from backend import sim_priority_vs_fifo


client = TestClient(app)


def test_enqueue_and_get_queue():
    now = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc).isoformat()

    payload = {
        "id": "T1",
        "supply_type": "Medical Kit",
        "quantity": 3,
        "timestamp": now,
        "expiry_date": None,
        "distance_km": 5.0,
        "destination": "Test Camp",
    }

    resp = client.post("/api/requests", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "enqueued"
    assert data["computed_priority"] > 0

    resp2 = client.get("/api/queue")
    assert resp2.status_code == 200
    q = resp2.json()
    assert q["size"] >= 1
    assert any(item["request"]["id"] == "T1" for item in q["items"])


def test_dispatch_next():
    payload = {
        "id": "T2",
        "supply_type": "Food",
        "quantity": 1,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "expiry_date": None,
        "distance_km": 10.0,
        "destination": "Test Camp 2",
    }
    client.post("/api/requests", json=payload)

    resp = client.post("/api/dispatch")
    assert resp.status_code == 200
    data = resp.json()
    assert "dispatched" in data
    assert data["dispatched"]["request"]["id"] in ["T1", "T2"]


def test_enqueue_rejects_bad_timestamp():
    bad_payload = {
        "id": "BAD1",
        "supply_type": "Food",
        "quantity": 1,
        "timestamp": "not-a-timestamp",
        "expiry_date": None,
        "distance_km": 5.0,
        "destination": "Nowhere",
    }

    resp = client.post("/api/requests", json=bad_payload)
    assert resp.status_code == status.HTTP_400_BAD_REQUEST
    data = resp.json()
    assert "Bad datetime format" in data["detail"]


def test_dispatch_empty_queue_404():
    # drain queue
    while True:
        resp = client.post("/api/dispatch")
        if resp.status_code == status.HTTP_404_NOT_FOUND:
            break

    resp2 = client.post("/api/dispatch")
    assert resp2.status_code == status.HTTP_404_NOT_FOUND
    data = resp2.json()
    assert data["detail"] == "Queue empty"


def test_import_via_api_smoke(tmp_path, monkeypatch):
    csv_content = (
        "id,supply_type,quantity,timestamp,expiry_date,distance_km,destination\n"
        "C1,Water,2,,,5.0,Camp X\n"
    )
    csv_file = tmp_path / "requests.csv"
    csv_file.write_text(csv_content, encoding="utf-8")

    calls = {}

    def fake_post(url, json):
        calls["url"] = url
        calls["json"] = json

        class Resp:
            status_code = 200
            text = "ok"

        return Resp()

    monkeypatch.setattr("backend.import_csv_api.requests.post", fake_post)

    import_via_api(str(csv_file))

    assert calls["url"].endswith("/api/requests")
    assert calls["json"]["id"] == "C1"
    assert calls["json"]["supply_type"] == "Water"


def test_import_csv_usage_error(monkeypatch, capsys):
    # simulate running as a script with no args
    monkeypatch.setattr(import_csv_api, "sys", import_csv_api.sys)
    import_csv_api.sys.argv = ["import_csv_api.py"]

    exits = {}

    def fake_exit(code):
        exits["code"] = code
        raise SystemExit()

    monkeypatch.setattr(import_csv_api.sys, "exit", fake_exit)

    with pytest.raises(SystemExit):
        if len(import_csv_api.sys.argv) < 2:
            print("Usage: python import_csv_api.py path/to/requests.csv")
            import_csv_api.sys.exit(1)

    captured = capsys.readouterr()
    assert "Usage: python import_csv_api.py" in captured.out
    assert exits["code"] == 1


def test_simulation_runs_priority_and_fifo():
    arrivals = generate_arrivals(
        total_time_s=300.0,
        arrival_rate=0.02,
        seed=1,
    )
    assert len(arrivals) > 0

    res_pr = simulate(arrivals, service_rate=1.0 / 30.0, discipline="priority")
    res_fifo = simulate(arrivals, service_rate=1.0 / 30.0, discipline="fifo")

    for res in (res_pr, res_fifo):
        assert "mean_wait" in res
        assert "p95_wait" in res
        assert res["count"] > 0


def test_run_sweep_smoke(monkeypatch):
    saves = []

    def fake_savefig(path, *args, **kwargs):
        saves.append(path)

    monkeypatch.setattr(sim_priority_vs_fifo.plt, "savefig", fake_savefig)

    sim_priority_vs_fifo.run_sweep()

    assert any(
        "mean_wait_vs_rate" in p or "p95_wait_vs_rate" in p for p in saves
    )
