"""Extract-to-JSON step of the maintenance_activities pipeline.

Pulls planned maintenance Activities from Takeoff CRM for a given month and
a set of activity types (default: "Manutenzione ordinaria programmata",
id 16602 — confirmed against /api/activitytypes on the live API), and
writes them as JSON in the same raw/staging split as the sibling
employee_deadlines_certificates pipeline:

  data/raw/<month>_activities.json
      Untouched API response for the month (paginated, concatenated).
      Kept for lineage/debugging.

  data/staging/activities.jsonl
      Normalized, flat, one JSON object per line (NDJSON) — the format
      every cloud warehouse/DB loader speaks natively. The only thing a
      future cloud-loading step should need to read.

  data/staging/_manifest.json
      Metadata about the run (when, month, types, row counts).

Usage:
    uv run python extract_to_json.py --month 2026-09
    uv run python extract_to_json.py --month 2026-09 --types 16602,16441
"""

import argparse
import calendar
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterator, List

# Reuse the shared API client from the repo root instead of duplicating it.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from takeoff_client import TakeoffApiError, TakeoffClient  # noqa: E402

PIPELINE_DIR = Path(__file__).resolve().parent
RAW_DIR = PIPELINE_DIR / "data" / "raw"
STAGING_DIR = PIPELINE_DIR / "data" / "staging"

SOURCE_SYSTEM = "takeoff_crm"

# "Manutenzione ordinaria programmata" — confirmed via GET /api/activitytypes.
DEFAULT_TYPE_IDS = [16602]


def month_bounds(month: str) -> tuple[str, str]:
    """'2026-09' -> ('2026-09-01T00:00:00', '2026-09-30T23:59:59')."""
    year, mon = (int(x) for x in month.split("-"))
    last_day = calendar.monthrange(year, mon)[1]
    start = f"{year:04d}-{mon:02d}-01T00:00:00"
    end = f"{year:04d}-{mon:02d}-{last_day:02d}T23:59:59"
    return start, end


def fetch_activities(client: TakeoffClient, type_ids: List[int], start: str, end: str, take: int = 200) -> List[Dict[str, Any]]:
    skip = 0
    all_activities: List[Dict[str, Any]] = []
    while True:
        page = client.get_json(
            "/api/activities",
            params={
                "skip": skip,
                "take": take,
                "types": type_ids,
                "startDate": start,
                "endDate": end,
            },
        )
        if not page:
            break
        all_activities.extend(page)
        if len(page) < take:
            break
        skip += take
    return all_activities


def build_row(activity: Dict[str, Any], extracted_at: str) -> Dict[str, Any]:
    activity_type = activity.get("activityType") or {}
    assigned_user = activity.get("assignedUser") or {}
    contact = activity.get("contact") or {}
    job = activity.get("job") or {}
    address = activity.get("contactAddress") or {}

    return {
        "activity_id": activity["id"],
        "activity_type_id": activity_type.get("id"),
        "activity_type_name": activity_type.get("name"),
        "assigned_user_id": assigned_user.get("id"),
        "assigned_user_name": assigned_user.get("displayName"),
        "contact_id": contact.get("id"),
        "company_name": (contact.get("companyName") or "").strip() or None,
        "job_id": job.get("id"),
        "job_name": job.get("name"),
        "address": address.get("address"),
        "city": address.get("city"),
        "province": address.get("province"),
        "postal_code": address.get("postalCode"),
        "full_address": address.get("fullAddress"),
        "latitude": address.get("latitude"),
        "longitude": address.get("longitude"),
        "planned_start": activity.get("start"),
        "planned_end": activity.get("end"),
        "duration_minutes": activity.get("duration"),
        "completed": bool(activity.get("completed")),
        "confirmed": bool(activity.get("confirmed")),
        "approved": bool(activity.get("approved")),
        "source_system": SOURCE_SYSTEM,
        "extracted_at": extracted_at,
    }


def write_jsonl(rows: List[Dict[str, Any]], path: Path) -> None:
    with open(path, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract Takeoff CRM maintenance Activities for a month to JSON.")
    parser.add_argument("--month", default=None, help="Month as YYYY-MM (default: current month)")
    parser.add_argument("--types", default=None, help="Comma-separated activity type ids (default: 16602, 'Manutenzione ordinaria programmata')")
    args = parser.parse_args()

    month = args.month or datetime.now().strftime("%Y-%m")
    type_ids = [int(t) for t in args.types.split(",")] if args.types else DEFAULT_TYPE_IDS

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    STAGING_DIR.mkdir(parents=True, exist_ok=True)

    try:
        client = TakeoffClient.from_settings()
    except Exception as exc:  # pydantic ValidationError or missing .env
        print(f"Configuration error: {exc}", file=sys.stderr)
        sys.exit(1)

    start, end = month_bounds(month)

    try:
        activities = fetch_activities(client, type_ids, start, end)
    except TakeoffApiError as exc:
        print(f"Takeoff API error: {exc}", file=sys.stderr)
        sys.exit(1)

    with open(RAW_DIR / f"{month}_activities.json", "w", encoding="utf-8") as f:
        json.dump(activities, f, ensure_ascii=False, indent=2)

    extracted_at = datetime.now(timezone.utc).isoformat()
    rows = [build_row(a, extracted_at) for a in activities]
    write_jsonl(rows, STAGING_DIR / "activities.jsonl")

    manifest = {
        "extracted_at": extracted_at,
        "source_system": SOURCE_SYSTEM,
        "month": month,
        "type_ids": type_ids,
        "row_counts": {"activities": len(rows)},
    }
    with open(STAGING_DIR / "_manifest.json", "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    print(f"Extracted {len(rows)} activities for {month} (types={type_ids}).")
    print(f"Raw JSON:      {RAW_DIR}")
    print(f"Staging JSONL: {STAGING_DIR}")


if __name__ == "__main__":
    main()
