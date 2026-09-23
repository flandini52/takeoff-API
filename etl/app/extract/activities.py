"""Extract step: planned maintenance Activities from Takeoff CRM.

Ported from the old maintenance_activities/extract_to_json.py pipeline —
same pagination, same normalization, same default activity type id
(16602, "Manutenzione ordinaria programmata", confirmed via
GET /api/activitytypes on the live API).

No raw JSON is written to disk anymore (see README, "Perché niente
raw_*"): extraction against the live API is cheap and idempotent, so
there's currently no consumer that needs a local replay copy.
"""

import calendar
from datetime import datetime, timezone
from typing import Any, Dict, List

from ..api.client import TakeoffClient

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


def extract(client: TakeoffClient, month: str, type_ids: List[int]) -> List[Dict[str, Any]]:
    start, end = month_bounds(month)
    activities = fetch_activities(client, type_ids, start, end)
    extracted_at = datetime.now(timezone.utc).isoformat()
    return [build_row(a, extracted_at) for a in activities]
