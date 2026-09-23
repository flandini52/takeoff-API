"""Extract step: employee certificates/deadlines (Wiki module) from Takeoff CRM.

Ported from the old employee_deadlines_certificates/extract_to_json.py
pipeline — same contact lookup, same folder/element/property flattening,
same expiry-date normalization (Takeoff returns dd/mm/yyyy; normalized to
ISO 8601 so it sorts/compares correctly).

No raw JSON is written to disk anymore — see README, "Perché niente raw_*".
raw_properties is kept as a Python object (not a pre-serialized string):
load/postgres.py stores it in a JSONB column, which is the "correct type"
for it in Postgres (unlike SQLite, which has no native JSON type).
"""

from datetime import datetime, timezone
from typing import Any, Dict, Iterator, List, Optional, Tuple

from ..api.client import TakeoffClient

SOURCE_SYSTEM = "takeoff_crm"

# The two property names the live API actually uses for "expiry date"
# across folder typologies (Personale uses "Scadenza", Scadenze varie uses
# "Data scadenza"). Kept as a set so a new variant is a one-line fix.
EXPIRY_PROPERTY_NAMES = {"scadenza", "data scadenza"}
DOCUMENT_PROPERTY_NAMES = {"documento"}


def find_contacts(client: TakeoffClient, company_name: str, exact: bool) -> List[Dict[str, Any]]:
    params: Dict[str, Any] = {"skip": 0, "take": 50}
    if exact:
        params["companyName"] = company_name
    else:
        params["companyNameLike"] = company_name
    return client.get_json("/api/contacts", params=params)


def fetch_wiki_folders(client: TakeoffClient, contact_id: int) -> List[Dict[str, Any]]:
    return client.get_json("/api/wiki/folders", params={"contactId": contact_id})


def _normalize_date(value: Optional[str]) -> Optional[str]:
    """Takeoff returns dates as dd/mm/yyyy; normalize to ISO 8601 (yyyy-mm-dd)
    so they sort/compare correctly in any downstream DB. Falls back to the
    raw value if the format ever changes, rather than dropping the data."""
    if not value:
        return None
    try:
        return datetime.strptime(value, "%d/%m/%Y").date().isoformat()
    except ValueError:
        return value


def build_subject_row(contact: Dict[str, Any], folder: Dict[str, Any], extracted_at: str) -> Dict[str, Any]:
    category = (folder.get("typology") or {}).get("name") or ""
    return {
        "subject_id": folder["id"],
        "contact_id": contact["id"],
        "company_name": (contact.get("companyName") or "").strip(),
        "subject_name": folder.get("name"),
        "subject_category": category,
        "is_employee": category.strip().lower() == "personale",
        "source_system": SOURCE_SYSTEM,
        "extracted_at": extracted_at,
    }


def build_deadline_rows(folder: Dict[str, Any], extracted_at: str) -> Iterator[Dict[str, Any]]:
    for element in folder.get("elements") or []:
        properties = element.get("properties") or []
        expiry_date = None
        document_filename = None
        for prop in properties:
            name = (prop.get("name") or "").strip().lower()
            value = prop.get("value") or None
            if name in EXPIRY_PROPERTY_NAMES and value:
                expiry_date = _normalize_date(value)
            elif name in DOCUMENT_PROPERTY_NAMES and value:
                document_filename = value
        yield {
            "element_id": element["id"],
            "subject_id": folder["id"],
            "element_name": element.get("name"),
            "element_category": (element.get("typology") or {}).get("name"),
            "expiry_date": expiry_date,
            "document_filename": document_filename,
            "raw_properties": properties,
            "source_system": SOURCE_SYSTEM,
            "extracted_at": extracted_at,
        }


def extract(client: TakeoffClient, company_name: str, exact: bool) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    contacts = find_contacts(client, company_name, exact)
    if not contacts:
        return [], []

    extracted_at = datetime.now(timezone.utc).isoformat()
    subject_rows: List[Dict[str, Any]] = []
    deadline_rows: List[Dict[str, Any]] = []

    for contact in contacts:
        folders = fetch_wiki_folders(client, contact["id"])
        for folder in folders:
            subject_rows.append(build_subject_row(contact, folder, extracted_at))
            deadline_rows.extend(build_deadline_rows(folder, extracted_at))

    return subject_rows, deadline_rows
