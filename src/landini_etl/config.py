"""App configuration: single source of truth for DB and Takeoff CRM
settings, used by both the ETL and Streamlit (streamlit/app/services/*).

Reads real process environment variables first; falls back to the .env
file at the repo root (pydantic-settings' env_file) for anything not set
as a real env var. This is what lets the exact same code run unchanged in
three places:
  - Docker (docker-compose injects .env as real env vars via env_file —
    the file itself is never copied into the image, so env_file here is a
    no-op there, but harmless: it just won't find the file).
  - Native Windows dev/production (no orchestrator to inject env vars —
    the .env file at the repo root is what's actually read).
Real env vars always win over the .env file (pydantic-settings default),
so Docker's behavior is unaffected by this file existing.
"""

from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# src/landini_etl/config.py -> landini_etl/ -> src/ -> repo root
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_ENV_FILE = _REPO_ROOT / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=_ENV_FILE, env_file_encoding="utf-8", extra="ignore")

    # Environment: doesn't change how anything connects, only what's shown.
    # ENABLE_SCADENZE gates the "Scadenze dipendenti" page (streamlit/app/
    # main.py) — off by default until there's a login (V2).
    dashboard_env: str = "development"
    enable_scadenze: bool = False

    # Takeoff CRM
    takeoff_base_url: str = "https://webapi.takeoffcrm.com"
    takeoff_api_key: Optional[str] = None
    takeoff_token: Optional[str] = None

    # PostgreSQL — db_host/db_port/db_name are shared; each service
    # connects with its own role (etl_writer / dashboard_reader, see
    # database/init/001_roles.sql), never as the admin user, so only the
    # two role passwords live here (not DB_USER/DB_PASSWORD, which only
    # the postgres container / deploy/windows/init_db.ps1 use).
    db_host: str = "localhost"
    db_port: int = 5435
    db_name: str = "landini_dashboard"
    etl_writer_password: Optional[str] = None
    dashboard_reader_password: Optional[str] = None

    # Runs after all fields are loaded, to check a rule that spans multiple
    # fields (a single field being Optional can't express "at least one of
    # these two must be set"). Without this, a missing key would only
    # surface later as a confusing 401 from the API instead of a clear
    # error right at startup.
    @model_validator(mode="after")
    def _require_auth(self) -> "Settings":
        if not self.takeoff_api_key and not self.takeoff_token:
            raise ValueError(
                "Missing authentication: set TAKEOFF_API_KEY or TAKEOFF_TOKEN "
                "(in .env, or as a real environment variable)."
            )
        return self


# lru_cache makes this a singleton: Settings() reads and validates the
# environment only once per process; every later call to get_settings()
# reuses that same instance.
@lru_cache
def get_settings() -> Settings:
    return Settings()
