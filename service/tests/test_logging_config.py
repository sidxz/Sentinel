from src.config import Settings, settings


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
