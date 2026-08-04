from functools import lru_cache
from typing import Optional

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """App configuration, loaded from environment variables / .env.

    Single source of truth for secrets: no `os.getenv` scattered across the
    codebase. Fails fast, with a clear message, if auth isn't configured.
    """

    # Tells pydantic-settings to also read values from a local .env file
    # (in addition to real environment variables, which always take
    # priority). extra="ignore" means unrelated variables in .env/the
    # environment are silently ignored instead of raising an error.
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Each field is auto-populated from the matching env var name
    # (case-insensitive): takeoff_base_url <- TAKEOFF_BASE_URL, etc.
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
                "in .env (see .env.example)."
            )
        return self


# lru_cache makes this a singleton: Settings() reads and validates .env only
# once per run; every later call to get_settings() reuses that same instance
# instead of re-parsing the file.
@lru_cache
def get_settings() -> Settings:
    return Settings()
