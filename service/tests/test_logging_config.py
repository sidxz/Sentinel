import json
import logging

import pytest
import structlog

from src.config import Settings, settings
from src.logging_config import configure_logging


@pytest.fixture(autouse=True)
def _restore_logging():
    """configure_logging() mutates process-wide logging (root handlers, structlog
    config, uvicorn/sqlalchemy loggers). Snapshot and restore so these tests can't
    leak state into the rest of the suite (order-dependent coupling)."""
    root = logging.getLogger()
    saved_handlers = root.handlers[:]
    saved_level = root.level
    saved_structlog = structlog.get_config()
    uvicorn_access = logging.getLogger("uvicorn.access")
    saved_uvicorn_handlers = uvicorn_access.handlers[:]
    saved_uvicorn_propagate = uvicorn_access.propagate
    saved_sqla_level = logging.getLogger("sqlalchemy.engine").level
    try:
        yield
    finally:
        root.handlers[:] = saved_handlers
        root.setLevel(saved_level)
        structlog.configure(**saved_structlog)
        uvicorn_access.handlers[:] = saved_uvicorn_handlers
        uvicorn_access.propagate = saved_uvicorn_propagate
        logging.getLogger("sqlalchemy.engine").setLevel(saved_sqla_level)


def test_logging_defaults():
    s = Settings()
    assert s.log_level == "INFO"
    assert s.log_format == "json"
    assert s.log_pii_redaction is True


def test_environment_property(monkeypatch):
    monkeypatch.setattr(settings, "debug", True)
    assert settings.environment == "dev"
    monkeypatch.setattr(settings, "debug", False)
    assert settings.environment == "prod"


def test_configure_emits_json_envelope(capsys, monkeypatch):
    monkeypatch.setattr(settings, "log_format", "json")
    monkeypatch.setattr(settings, "log_level", "INFO")
    configure_logging()
    structlog.get_logger().info("test.event", foo="bar")
    line = capsys.readouterr().out.strip().splitlines()[-1]
    rec = json.loads(line)
    assert rec["event"] == "test.event"
    assert rec["level"] == "info"
    assert rec["service"] == "sentinel"
    assert rec["version"]
    assert rec["ts"]
    assert rec["foo"] == "bar"


def test_configure_redacts_email_end_to_end(capsys, monkeypatch):
    monkeypatch.setattr(settings, "log_format", "json")
    monkeypatch.setattr(settings, "log_pii_redaction", True)
    configure_logging()
    structlog.get_logger().warning("authz.token.denied", email="a@acme.com")
    rec = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert "email" not in rec
    assert rec["email_domain"] == "acme.com"
