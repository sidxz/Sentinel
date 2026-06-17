from fastapi import FastAPI
from fastapi.testclient import TestClient
from structlog.testing import capture_logs

from src.middleware.access_log import AccessLogMiddleware


def _app():
    app = FastAPI()
    app.add_middleware(AccessLogMiddleware)

    @app.get("/echo/{name}")
    def echo(name: str):
        return {"name": name}

    return app


def test_emits_single_access_event_with_route_template():
    with capture_logs() as logs:
        TestClient(_app()).get("/echo/alice")
    access = [e for e in logs if e["event"] == "http.access"]
    assert len(access) == 1
    e = access[0]
    assert e["category"] == "access"
    assert e["http.route"] == "/echo/{name}"  # template, not /echo/alice
    assert e["http.method"] == "GET"
    assert e["http.status"] == 200
    assert "duration_ms" in e
    assert e["log_level"] == "info"


def test_4xx_logged_as_warning():
    with capture_logs() as logs:
        TestClient(_app()).get("/nope")
    e = [x for x in logs if x["event"] == "http.access"][0]
    assert e["http.status"] == 404
    assert e["log_level"] == "warning"


def test_skips_health():
    app = FastAPI()
    app.add_middleware(AccessLogMiddleware)

    @app.get("/health")
    def health():
        return {"ok": True}

    with capture_logs() as logs:
        TestClient(app).get("/health")
    assert not [e for e in logs if e.get("event") == "http.access"]
