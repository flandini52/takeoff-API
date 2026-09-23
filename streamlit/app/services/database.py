"""PostgreSQL connection layer for the Streamlit app.

Streamlit only ever reads from PostgreSQL (see README: gestionale -> ETL ->
PostgreSQL -> Streamlit) — pages/components must go through this module
instead of opening their own connection or calling the gestionale API.
Connects as `dashboard_reader` (read-only role — see
database/init/001_roles.sql); writes only ever happen via the ETL
(services/etl.py), never here.

One function per query, cached for 5 minutes (@st.cache_data(ttl=300)) —
cleared explicitly by components/sidebar.py after a successful "Aggiorna
dati" run so the dashboard doesn't wait out the TTL to show fresh data.
"""

import os
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Optional

import pandas as pd
import psycopg2
import streamlit as st


def _db_config() -> dict:
    return {
        "host": os.environ.get("DB_HOST", "localhost"),
        "port": int(os.environ.get("DB_PORT", "5432")),
        "dbname": os.environ.get("DB_NAME", ""),
        "user": "dashboard_reader",
        "password": os.environ.get("DASHBOARD_READER_PASSWORD", ""),
    }


@contextmanager
def get_connection():
    conn = psycopg2.connect(**_db_config())
    try:
        yield conn
    finally:
        conn.close()


@dataclass
class ConnectionStatus:
    ok: bool
    host: str
    port: int
    database: str
    version: Optional[str] = None
    table_count: Optional[int] = None
    error: Optional[str] = None


def get_connection_status() -> ConnectionStatus:
    config = _db_config()
    try:
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute("SELECT version();")
            version = cur.fetchone()[0]
            cur.execute("SELECT count(*) FROM information_schema.tables WHERE table_schema = 'public';")
            table_count = cur.fetchone()[0]
        return ConnectionStatus(
            ok=True,
            host=config["host"],
            port=config["port"],
            database=config["dbname"],
            version=version,
            table_count=table_count,
        )
    except Exception as exc:
        return ConnectionStatus(
            ok=False,
            host=config["host"],
            port=config["port"],
            database=config["dbname"],
            error=str(exc),
        )


@st.cache_data(ttl=300)
def get_activities() -> pd.DataFrame:
    with get_connection() as conn:
        return pd.read_sql_query("SELECT * FROM activities", conn)


@st.cache_data(ttl=300)
def get_deadlines() -> pd.DataFrame:
    with get_connection() as conn:
        return pd.read_sql_query(
            """
            SELECT s.subject_id, s.subject_name, s.subject_category, s.is_employee,
                   s.company_name, d.element_id, d.element_name, d.element_category,
                   d.expiry_date, d.document_filename
            FROM subjects s
            JOIN deadlines_certificates d ON d.subject_id = s.subject_id
            """,
            conn,
        )


@st.cache_data(ttl=300)
def get_recent_etl_runs(limit: int = 20) -> pd.DataFrame:
    with get_connection() as conn:
        return pd.read_sql_query(
            """
            SELECT id, entity, params, started_at, finished_at, status, rows_loaded, error
            FROM etl_runs
            ORDER BY started_at DESC
            LIMIT %(limit)s
            """,
            conn,
            params={"limit": limit},
        )


def get_last_successful_run(entity: str):
    """Most recent successful etl_runs row for `entity`, or None."""
    runs = get_recent_etl_runs(limit=50)
    matches = runs[(runs["entity"] == entity) & (runs["status"] == "success")]
    return matches.iloc[0] if not matches.empty else None


# Future business queries (get_customers, get_jobs, get_job_economics, ...)
# go here once the corresponding tables exist, following the same
# get_connection() + @st.cache_data(ttl=300) pattern.
