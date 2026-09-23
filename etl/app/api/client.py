"""Central client for the gestionale API.

No real gestionale API is defined yet (see README, "Importante: non fare
assunzioni sul gestionale"). Once endpoints/auth/response shapes are
documented, add one method per entity here (get_customers, get_jobs,
get_activities, ...), each building on self.base_url / self._headers()
via `requests` and raising GestionaleAPIError on failure. The rest of the
ETL (and Streamlit, indirectly via PostgreSQL) never talks to the
gestionale except through this class.
"""

import os


class GestionaleAPIError(Exception):
    """Raised when a call to the gestionale API fails."""


class GestionaleClient:
    def __init__(self) -> None:
        self.base_url = os.environ.get("GESTIONALE_API_URL", "")
        self.api_key = os.environ.get("GESTIONALE_API_KEY", "")

    def _headers(self) -> dict[str, str]:
        return {"x-api-key": self.api_key} if self.api_key else {}

    def get_mock_records(self) -> list[dict]:
        """Mock data, clearly NOT from a real API — used only to exercise
        the extract -> transform -> load wiring until the real gestionale
        API is documented and a real method replaces this one."""
        return [
            {"mock_id": 1, "name": "Mock record 1"},
            {"mock_id": 2, "name": "Mock record 2"},
        ]
