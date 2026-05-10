"""運用エンドポイントの公開範囲（キー無しでの挙動）。"""

import os

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture()
def ops_client(monkeypatch):
    monkeypatch.delenv("METRICS_API_KEY", raising=False)
    monkeypatch.delenv("AUDIT_LOG_API_KEY", raising=False)
    return TestClient(app)


def test_metrics_public_when_key_unset(ops_client):
    res = ops_client.get("/metrics")
    assert res.status_code == 200
    body = res.json()
    assert "request_blocked" in body


def test_audit_logs_hidden_when_key_unset(ops_client):
    res = ops_client.get("/safety/audit-logs")
    assert res.status_code == 404


def test_metrics_requires_header_when_key_configured(monkeypatch):
    monkeypatch.setenv("METRICS_API_KEY", "ops-metrics-test-key")
    monkeypatch.delenv("AUDIT_LOG_API_KEY", raising=False)
    client = TestClient(app)
    assert client.get("/metrics").status_code == 401
    ok = client.get("/metrics", headers={"X-Metrics-Key": "ops-metrics-test-key"})
    assert ok.status_code == 200
