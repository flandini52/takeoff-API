"""PostgreSQL connection layer for the Streamlit app.

Streamlit only ever reads from PostgreSQL (see README: gestionale -> ETL ->
PostgreSQL -> Streamlit) — pages/components must go through this module
instead of opening their own connection or calling the gestionale API.

Business queries (get_customers, get_jobs, get_activities,
get_job_economics, ...) will be added here once the corresponding tables
exist, each following the same get_connection() pattern below.
"""

import os
from contextlib import contextmanager
from dataclasses import dataclass

import psycopg2


def _db_config() -> dict:
    return {
        "host": os.environ.get("DB_HOST", "localhost"),
        "port": int(os.environ.get("DB_PORT", "5432")),
        "dbname": os.environ.get("DB_NAME", ""),
        "user": os.environ.get("DB_USER", ""),
        "password": os.environ.get("DB_PASSWORD", ""),
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
    version: str | None = None
    table_count: int | None = None
    error: str | None = None


def get_connection_status() -> ConnectionStatus:
    """Round-trips to PostgreSQL to prove the infrastructure is wired up.

    table_count reflects the current (empty, at this stage) public schema —
    it's an infra check, not a business metric.
    """
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
