"""App configuration, loaded from environment variables.

Single source of truth for Takeoff CRM credentials used by the ETL. Reads
real process environment variables only (docker-compose injects them via
`env_file: .env` — no .env file is ever copied into the image). Fails
fast, with a clear message, if authentication isn't configured.
"""

from functools import lru_cache
from typing import Optional

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    takeoff_base_url: str = "https://webapi.takeoffcrm.com"
    takeoff_api_key: Optional[str] = None
    takeoff_token: Optional[str] = None

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
                "(in .env, injected into the container by docker-compose)."
            )
        return self


# lru_cache makes this a singleton: Settings() reads and validates the
# environment only once per process; every later call to get_settings()
# reuses that same instance.
@lru_cache
def get_settings() -> Settings:
    return Settings()
