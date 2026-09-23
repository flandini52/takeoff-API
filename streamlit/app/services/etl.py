"""Bridge to the landini_etl package, imported in-process — the "Aggiorna
dati" button never shells out to a subprocess.

landini_etl is a regular installed dependency of this project (see
pyproject.toml / uv.lock) — `uv sync` puts it on sys.path the same way in
Docker, native Windows dev, and native Windows production. No PYTHONPATH
tricks, no environment-specific import path.
"""

from typing import Any, Tuple

from landini_etl.main import RunSkipped
from landini_etl.main import run as etl_run


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
