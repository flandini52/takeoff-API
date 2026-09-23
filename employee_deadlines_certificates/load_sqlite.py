"""Load step of the employee_deadlines_certificates pipeline: staging JSONL -> local SQLite.

This is the *only* part that's SQLite-specific. It exists so you have a
queryable local DB today; when you're ready to move to a cloud DB, this file
is the one to swap (e.g. for a script that runs `COPY INTO` on Snowflake, a
`bq load` call, or `psycopg2` inserts against managed Postgres) -- the
staging JSONL files it reads are already in the right shape for any of
those, unchanged.

Uses INSERT OR REPLACE keyed on the Takeoff ids (subject_id / element_id),
so re-running extract + load after data changes in the CRM is idempotent:
it updates existing rows and adds new ones, no duplicates.

Usage:
    uv run python load_sqlite.py
"""

import json
import sqlite3
from pathlib import Path

PIPELINE_DIR = Path(__file__).resolve().parent
STAGING_DIR = PIPELINE_DIR / "data" / "staging"
SCHEMA_PATH = PIPELINE_DIR / "schema.sql"
DB_PATH = PIPELINE_DIR / "db" / "employee_deadlines_certificates.db"


def load_jsonl(path: Path):
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def main() -> None:
    subjects = load_jsonl(STAGING_DIR / "subjects.jsonl")
    deadlines = load_jsonl(STAGING_DIR / "deadlines_certificates.jsonl")

    if not subjects and not deadlines:
        print(f"No staging data found in {STAGING_DIR}. Run extract_to_json.py first.")
        return

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))

        conn.executemany(
            """
            INSERT OR REPLACE INTO subjects
                (subject_id, contact_id, company_name, subject_name, subject_category,
                 is_employee, source_system, extracted_at)
            VALUES (:subject_id, :contact_id, :company_name, :subject_name, :subject_category,
                    :is_employee, :source_system, :extracted_at)
            """,
            [{**s, "is_employee": int(s["is_employee"])} for s in subjects],
        )

        conn.executemany(
            """
            INSERT OR REPLACE INTO deadlines_certificates
                (element_id, subject_id, element_name, element_category, expiry_date,
                 document_filename, raw_properties, source_system, extracted_at)
            VALUES (:element_id, :subject_id, :element_name, :element_category, :expiry_date,
                    :document_filename, :raw_properties, :source_system, :extracted_at)
            """,
            deadlines,
        )

        conn.commit()

        subject_count = conn.execute("SELECT COUNT(*) FROM subjects").fetchone()[0]
        deadline_count = conn.execute("SELECT COUNT(*) FROM deadlines_certificates").fetchone()[0]
    finally:
        conn.close()

    print(f"Loaded into {DB_PATH}")
    print(f"  subjects: {subject_count} rows")
    print(f"  deadlines_certificates: {deadline_count} rows")


if __name__ == "__main__":
    main()
