"""Bridge to the ETL package, imported in-process — the "Aggiorna dati"
button never shells out to a subprocess.

Requires the ETL package to be present in the image alongside this app/
(see streamlit/Dockerfile: build context is the repo root so it can COPY
etl/app/ in too, at /app/etl, with PYTHONPATH=/app making it importable
as `etl`).
"""

from typing import Any, Tuple

from etl.main import RunSkipped
from etl.main import run as etl_run


def trigger_refresh(entity: str, **params: Any) -> Tuple[bool, str]:
    """Runs one ETL entity synchronously (extract -> load), guarded by the
    same per-entity Postgres lock the CLI uses. Returns (ok, message)."""
    try:
        rows_loaded = etl_run(entity, **params)
    except RunSkipped:
        return False, "Aggiornamento già in corso."
    except Exception as exc:
        return False, f"Aggiornamento fallito: {exc}"
    return True, f"Aggiornati {rows_loaded} record."
