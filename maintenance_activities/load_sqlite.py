"""Load step of the maintenance_activities pipeline: staging JSONL -> local SQLite.

Same pattern as the sibling employee_deadlines_certificates pipeline: this
is the only SQLite-specific file. To move to a cloud DB, replace this
script with an equivalent loader — the staging JSONL it reads stays the
same.

INSERT OR REPLACE keyed on activity_id: re-running extract + load after
activities change in the CRM (e.g. marked completed) is idempotent.

Usage:
    uv run python load_sqlite.py
"""

import json
import sqlite3
from pathlib import Path

PIPELINE_DIR = Path(__file__).resolve().parent
STAGING_DIR = PIPELINE_DIR / "data" / "staging"
SCHEMA_PATH = PIPELINE_DIR / "schema.sql"
DB_PATH = PIPELINE_DIR / "db" / "maintenance_activities.db"


def load_jsonl(path: Path):
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def main() -> None:
    activities = load_jsonl(STAGING_DIR / "activities.jsonl")

    if not activities:
        print(f"No staging data found in {STAGING_DIR}. Run extract_to_json.py first.")
        return

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))

        conn.executemany(
            """
            INSERT OR REPLACE INTO activities
                (activity_id, activity_type_id, activity_type_name, assigned_user_id,
                 assigned_user_name, contact_id, company_name, job_id, job_name,
                 address, city, province, postal_code, full_address, latitude, longitude,
                 planned_start, planned_end, duration_minutes, completed, confirmed, approved,
                 source_system, extracted_at)
            VALUES
                (:activity_id, :activity_type_id, :activity_type_name, :assigned_user_id,
                 :assigned_user_name, :contact_id, :company_name, :job_id, :job_name,
                 :address, :city, :province, :postal_code, :full_address, :latitude, :longitude,
                 :planned_start, :planned_end, :duration_minutes, :completed, :confirmed, :approved,
                 :source_system, :extracted_at)
            """,
            [{**a, "completed": int(a["completed"]), "confirmed": int(a["confirmed"]), "approved": int(a["approved"])}
             for a in activities],
        )

        conn.commit()
        count = conn.execute("SELECT COUNT(*) FROM activities").fetchone()[0]
    finally:
        conn.close()

    print(f"Loaded into {DB_PATH}")
    print(f"  activities: {count} rows")


if __name__ == "__main__":
    main()
