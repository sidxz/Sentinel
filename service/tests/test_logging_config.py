import json

import structlog

from src.config import Settings, settings
from src.logging_config import configure_logging


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
