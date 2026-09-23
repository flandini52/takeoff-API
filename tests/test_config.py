"""Parsing della configurazione da variabili d'ambiente — nessuna rete,
nessuna credenziale reale. `_env_file=None` esclude il vero .env del repo
(che ha credenziali reali) cosi' i test sono isolati e deterministici."""

import pytest

from landini_etl.config import Settings


def test_settings_parses_env_vars(monkeypatch):
    monkeypatch.setenv("TAKEOFF_API_KEY", "fake-key-for-tests")
    monkeypatch.setenv("DB_HOST", "localhost")
    monkeypatch.setenv("DB_PORT", "5435")
    monkeypatch.setenv("ENABLE_SCADENZE", "true")

    settings = Settings(_env_file=None)

    assert settings.takeoff_api_key == "fake-key-for-tests"
    assert settings.db_host == "localhost"
    assert settings.db_port == 5435
    assert settings.enable_scadenze is True


def test_settings_defaults(monkeypatch):
    monkeypatch.setenv("TAKEOFF_TOKEN", "fake-token-for-tests")
    monkeypatch.delenv("DB_HOST", raising=False)
    monkeypatch.delenv("ENABLE_SCADENZE", raising=False)

    settings = Settings(_env_file=None)

    assert settings.db_host == "localhost"
    assert settings.db_port == 5435
    assert settings.enable_scadenze is False
    assert settings.dashboard_env == "development"


def test_settings_requires_takeoff_auth(monkeypatch):
    monkeypatch.delenv("TAKEOFF_API_KEY", raising=False)
    monkeypatch.delenv("TAKEOFF_TOKEN", raising=False)

    with pytest.raises(ValueError):
        Settings(_env_file=None)
