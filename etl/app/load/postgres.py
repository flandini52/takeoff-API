"""Load step: writes records into PostgreSQL.

Kept separate from api/ and transform/ so swapping the destination (or
adding new target tables later) never touches extraction or
transformation.
"""

import logging
import os

import psycopg2

logger = logging.getLogger(__name__)


def _connection():
    return psycopg2.connect(
        host=os.environ.get("DB_HOST", "localhost"),
        port=int(os.environ.get("DB_PORT", "5432")),
        dbname=os.environ.get("DB_NAME", ""),
        user=os.environ.get("DB_USER", ""),
        password=os.environ.get("DB_PASSWORD", ""),
    )


def load_records(records: list[dict]) -> None:
    """Placeholder load: proves the ETL can reach PostgreSQL end-to-end.

    No destination table exists yet (see README, "Importante: non fare
    assunzioni sul gestionale"). Once the real schema is known, replace
    this with per-entity loaders (load_customers(), load_jobs(), ...) that
    upsert into their tables, following the same _connection() pattern.
    """
    if not records:
        logger.info("No records to load")
        return
    with _connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT version();")
        version = cur.fetchone()[0]
        logger.info(
            "Connected to PostgreSQL (%s) — %d record(s) ready to load once destination tables exist",
            version,
            len(records),
        )
