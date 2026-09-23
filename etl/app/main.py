"""ETL entry point and CLI.

Flow: Takeoff CRM API -> extract -> (transform: empty for now) -> load -> PostgreSQL.

CLI usage (run via `python -m app.main ...`, e.g. inside the etl container
via `docker compose run --rm etl ...`):

    python -m app.main activities --month 2026-09 [--types 16602,16441]
    python -m app.main deadlines ["LANDINI SRL"] [--no-exact]
    python -m app.main all

Also exposes run(entity, **params), importable in-process by the
Streamlit "Aggiorna dati" button so a refresh never has to shell out to
this CLI.

Each run takes a Postgres advisory lock scoped to `entity` for its whole
duration (see load/postgres.py): a second concurrent run for the same
entity exits immediately instead of racing the first one.
"""

import argparse
import logging
import sys
from datetime import datetime
from typing import Any, Dict

from .api.client import TakeoffApiError, TakeoffClient
from .extract import activities as extract_activities
from .extract import deadlines as extract_deadlines
from .load import postgres as db

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("etl")

DEFAULT_DEADLINES_COMPANY = "LANDINI SRL"


class RunSkipped(Exception):
    """Raised when a run is skipped because another one for the same entity is already in progress."""


def _resolve_params(entity: str, params: Dict[str, Any]) -> Dict[str, Any]:
    if entity == "activities":
        return {
            "month": params.get("month") or datetime.now().strftime("%Y-%m"),
            "type_ids": params.get("type_ids") or list(extract_activities.DEFAULT_TYPE_IDS),
        }
    if entity == "deadlines":
        return {
            "company_name": params.get("company_name") or DEFAULT_DEADLINES_COMPANY,
            "exact": params.get("exact", True),
        }
    raise ValueError(f"Unknown entity: {entity!r} (expected 'activities' or 'deadlines')")


def _run_activities(conn, client: TakeoffClient, params: Dict[str, Any]) -> int:
    rows = extract_activities.extract(client, params["month"], params["type_ids"])
    db.upsert_activities(conn, rows)
    return len(rows)


def _run_deadlines(conn, client: TakeoffClient, params: Dict[str, Any]) -> int:
    subject_rows, deadline_rows = extract_deadlines.extract(client, params["company_name"], params["exact"])
    db.upsert_deadlines(conn, subject_rows, deadline_rows)
    return len(subject_rows) + len(deadline_rows)


RUNNERS = {
    "activities": _run_activities,
    "deadlines": _run_deadlines,
}


def run(entity: str, **params: Any) -> int:
    """Run one ETL entity end-to-end (extract -> load), logged in etl_runs
    and guarded by a per-entity advisory lock. Returns rows_loaded.

    Raises RunSkipped if another run for the same entity is already in
    progress. Any extraction/load failure is recorded in etl_runs before
    being re-raised.
    """
    if entity not in RUNNERS:
        raise ValueError(f"Unknown entity: {entity!r} (expected one of {sorted(RUNNERS)})")

    resolved_params = _resolve_params(entity, params)

    conn = db.connect()
    try:
        if not db.try_acquire_lock(conn, entity):
            logger.warning("Skipping '%s': another run is already in progress", entity)
            raise RunSkipped(f"Un'estrazione per '{entity}' è già in corso.")
        try:
            run_id = db.start_run(conn, entity, resolved_params)
            logger.info("Starting ETL run: entity=%s params=%s (run_id=%s)", entity, resolved_params, run_id)
            try:
                client = TakeoffClient.from_settings()
                rows_loaded = RUNNERS[entity](conn, client, resolved_params)
            except Exception as exc:
                db.finish_run(conn, run_id, status="error", error=str(exc))
                logger.exception("ETL run failed: entity=%s", entity)
                raise
            db.finish_run(conn, run_id, status="success", rows_loaded=rows_loaded)
            logger.info("ETL run completed: entity=%s rows_loaded=%d", entity, rows_loaded)
            return rows_loaded
        finally:
            db.release_lock(conn, entity)
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Takeoff CRM -> PostgreSQL ETL.")
    subparsers = parser.add_subparsers(dest="entity", required=True)

    p_activities = subparsers.add_parser("activities", help="Planned maintenance activities for a month")
    p_activities.add_argument("--month", default=None, help="YYYY-MM (default: current month)")
    p_activities.add_argument("--types", default=None, help="Comma-separated activity type ids (default: 16602)")

    p_deadlines = subparsers.add_parser("deadlines", help="Employee certificates/deadlines (Wiki module)")
    p_deadlines.add_argument("company_name", nargs="?", default=DEFAULT_DEADLINES_COMPANY)
    p_deadlines.add_argument(
        "--exact",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Exact companyName match (default: true; use --no-exact for a substring search)",
    )

    subparsers.add_parser("all", help="Run activities (current month) then deadlines")

    args = parser.parse_args()

    try:
        if args.entity == "activities":
            type_ids = [int(t) for t in args.types.split(",")] if args.types else None
            run("activities", month=args.month, type_ids=type_ids)
        elif args.entity == "deadlines":
            run("deadlines", company_name=args.company_name, exact=args.exact)
        elif args.entity == "all":
            run("activities")
            run("deadlines")
    except RunSkipped as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)
    except TakeoffApiError as exc:
        print(f"Takeoff API error: {exc}", file=sys.stderr)
        sys.exit(1)
    except Exception as exc:
        print(f"ETL run failed: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
