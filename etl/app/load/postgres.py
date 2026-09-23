"""PostgreSQL access for the ETL: connection, per-entity advisory locks,
etl_runs logging, and per-table upserts.

Connects as `etl_writer` (read/write role — see
database/init/001_roles.sql), never as the Postgres admin user. Kept
separate from api/ and extract/ so swapping/extending the destination
never touches extraction.
"""

import os
from typing import Any, Dict, List, Optional, Tuple

import psycopg2
from psycopg2.extras import Json, execute_values


def connect():
    return psycopg2.connect(
        host=os.environ.get("DB_HOST", "localhost"),
        port=int(os.environ.get("DB_PORT", "5432")),
        dbname=os.environ.get("DB_NAME", ""),
        user="etl_writer",
        password=os.environ.get("ETL_WRITER_PASSWORD", ""),
    )


# --- per-entity advisory lock -------------------------------------------
#
# A session-level advisory lock keyed on hashtext(entity): held on the same
# connection for the whole run, released explicitly (or automatically if
# the connection/process dies) so a second concurrent run for the same
# entity never races the first one.


def try_acquire_lock(conn, entity: str) -> bool:
    with conn.cursor() as cur:
        cur.execute("SELECT pg_try_advisory_lock(hashtext(%s));", (entity,))
        return cur.fetchone()[0]


def release_lock(conn, entity: str) -> None:
    with conn.cursor() as cur:
        cur.execute("SELECT pg_advisory_unlock(hashtext(%s));", (entity,))
    conn.commit()


# --- etl_runs (replaces the old _manifest.json) -------------------------


def start_run(conn, entity: str, params: Dict[str, Any]) -> int:
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO etl_runs (entity, params, status) VALUES (%s, %s, 'running') RETURNING id",
            (entity, Json(params)),
        )
        run_id = cur.fetchone()[0]
    conn.commit()
    return run_id


def finish_run(conn, run_id: int, status: str, rows_loaded: int = 0, error: Optional[str] = None) -> None:
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE etl_runs SET finished_at = now(), status = %s, rows_loaded = %s, error = %s WHERE id = %s",
            (status, rows_loaded, error, run_id),
        )
    conn.commit()


# --- upserts --------------------------------------------------------------
#
# INSERT ... ON CONFLICT DO UPDATE on the same natural keys the old
# SQLite pipelines used for INSERT OR REPLACE (activity_id / subject_id /
# element_id) — re-running an extraction after data changes in the CRM is
# idempotent: it updates existing rows and adds new ones, no duplicates.

ACTIVITIES_COLUMNS = [
    "activity_id", "activity_type_id", "activity_type_name", "assigned_user_id",
    "assigned_user_name", "contact_id", "company_name", "job_id", "job_name",
    "address", "city", "province", "postal_code", "full_address", "latitude", "longitude",
    "planned_start", "planned_end", "duration_minutes", "completed", "confirmed", "approved",
    "source_system", "extracted_at",
]

SUBJECTS_COLUMNS = [
    "subject_id", "contact_id", "company_name", "subject_name", "subject_category",
    "is_employee", "source_system", "extracted_at",
]

DEADLINES_COLUMNS = [
    "element_id", "subject_id", "element_name", "element_category", "expiry_date",
    "document_filename", "raw_properties", "source_system", "extracted_at",
]


def _upsert(conn, table: str, columns: List[str], key: str, rows: List[Dict[str, Any]], json_columns: Tuple[str, ...] = ()) -> None:
    if not rows:
        return
    values = [[Json(r[c]) if c in json_columns else r[c] for c in columns] for r in rows]
    update_cols = [c for c in columns if c != key]
    set_clause = ", ".join(f"{c} = EXCLUDED.{c}" for c in update_cols)
    query = f"""
        INSERT INTO {table} ({", ".join(columns)})
        VALUES %s
        ON CONFLICT ({key}) DO UPDATE SET {set_clause}
    """
    with conn.cursor() as cur:
        execute_values(cur, query, values)


def upsert_activities(conn, rows: List[Dict[str, Any]]) -> None:
    _upsert(conn, "activities", ACTIVITIES_COLUMNS, "activity_id", rows)
    conn.commit()


def upsert_deadlines(conn, subject_rows: List[Dict[str, Any]], deadline_rows: List[Dict[str, Any]]) -> None:
    # subjects first: deadlines_certificates.subject_id references it.
    _upsert(conn, "subjects", SUBJECTS_COLUMNS, "subject_id", subject_rows)
    _upsert(conn, "deadlines_certificates", DEADLINES_COLUMNS, "element_id", deadline_rows, json_columns=("raw_properties",))
    conn.commit()
