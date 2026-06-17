from fastapi import FastAPI
from fastapi.testclient import TestClient
from structlog.testing import capture_logs

from src.api.client_log_routes import router as client_log_router
from src.api.dependencies import require_admin
from src.middleware.rate_limit import limiter

_XRW = {"X-Requested-With": "XMLHttpRequest"}


def _app():
    app = FastAPI()
    app.include_router(client_log_router)
    app.dependency_overrides[require_admin] = lambda: {"sub": "admin-1", "admin": True}
    # slowapi requires app.state.limiter; disable it so no Redis call is made in tests
    app.state.limiter = limiter
    limiter.enabled = False
    return app


def test_accepts_and_reemits():
    with capture_logs() as logs:
        r = TestClient(_app()).post(
            "/internal/client-logs",
            json={
                "events": [
                    {
                        "event": "client.login.failed",
                        "level": "warning",
                        "fields": {"reason": "bad"},
                    }
                ]
            },
            headers=_XRW,
        )
    assert r.status_code == 202
    ev = [e for e in logs if e["event"] == "client.login.failed"]
    assert ev
    assert ev[0]["category"] == "security"
    assert ev[0]["client_origin"] is True


def test_rejects_non_client_event_name():
    r = TestClient(_app()).post(
        "/internal/client-logs",
        json={
            "events": [{"event": "auth.login.failed", "level": "info", "fields": {}}]
        },
        headers=_XRW,
    )
    assert r.status_code == 422


def test_rejects_oversized_batch():
    big = {
        "events": [
            {"event": "client.x", "level": "info", "fields": {}} for _ in range(200)
        ]
    }
    r = TestClient(_app()).post("/internal/client-logs", json=big, headers=_XRW)
    assert r.status_code == 422


def test_redacts_client_supplied_pii():
    with capture_logs() as logs:
        TestClient(_app()).post(
            "/internal/client-logs",
            json={
                "events": [
                    {
                        "event": "client.error",
                        "level": "error",
                        "fields": {"email": "a@acme.com"},
                    }
                ]
            },
            headers=_XRW,
        )
    ev = [e for e in logs if e["event"] == "client.error"][0]
    assert "email" not in ev
    assert ev.get("email_domain") == "acme.com"
