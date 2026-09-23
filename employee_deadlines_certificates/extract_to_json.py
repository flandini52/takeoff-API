"""Extract-to-JSON step of the employee_deadlines_certificates pipeline.

Pulls Wiki data (certificates/deadlines) for a company's contacts from
Takeoff CRM and writes it as JSON, in two layers (the standard raw/staging
split for a small ELT pipeline):

  data/raw/<contact_id>_wiki_folders.json
      Untouched API response for that contact, one file per contact. Kept
      for lineage/debugging: if a downstream field mapping turns out to be
      wrong, we can re-derive it without calling the API again.

  data/staging/subjects.jsonl
  data/staging/deadlines_certificates.jsonl
      Normalized, flat, one JSON object per line (NDJSON) -- the format
      every cloud warehouse/DB loader speaks natively (bq load,
      Snowflake COPY INTO, Postgres/Mongo bulk import, S3 -> Athena, ...).
      This is deliberately the *only* thing a future cloud-loading step
      should need to read: extraction and loading stay decoupled, so
      swapping the local SQLite loader for a cloud one doesn't touch this
      script at all.

  data/staging/_manifest.json
      Metadata about the run (when, which contacts, row counts) for
      auditability and idempotency checks.

Usage:
    uv run python extract_to_json.py "LANDINI SRL" --exact
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

# Reuse the shared API client from the repo root instead of duplicating it.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from takeoff_client import TakeoffApiError, TakeoffClient  # noqa: E402

PIPELINE_DIR = Path(__file__).resolve().parent
RAW_DIR = PIPELINE_DIR / "data" / "raw"
STAGING_DIR = PIPELINE_DIR / "data" / "staging"

SOURCE_SYSTEM = "takeoff_crm"

# The two property names the live API actually uses for "expiry date"
# across folder typologies (Personale uses "Scadenza", Scadenze varie uses
# "Data scadenza"). Kept as a list so a new variant is a one-line fix.
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
            "raw_properties": json.dumps(properties, ensure_ascii=False),
            "source_system": SOURCE_SYSTEM,
            "extracted_at": extracted_at,
        }


def write_jsonl(rows: List[Dict[str, Any]], path: Path) -> None:
    with open(path, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract Takeoff CRM Wiki data (employee deadlines/certificates) to JSON.")
    parser.add_argument("company_name", help="Company name (or partial name) to search for")
    parser.add_argument("--exact", action="store_true", help="Match companyName exactly instead of a substring search")
    args = parser.parse_args()

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    STAGING_DIR.mkdir(parents=True, exist_ok=True)

    try:
        client = TakeoffClient.from_settings()
    except Exception as exc:  # pydantic ValidationError or missing .env
        print(f"Configuration error: {exc}", file=sys.stderr)
        sys.exit(1)

    try:
        contacts = find_contacts(client, args.company_name, exact=args.exact)
    except TakeoffApiError as exc:
        print(f"Takeoff API error: {exc}", file=sys.stderr)
        sys.exit(1)

    if not contacts:
        print(f"No contact found matching '{args.company_name}'", file=sys.stderr)
        sys.exit(1)

    extracted_at = datetime.now(timezone.utc).isoformat()
    subject_rows: List[Dict[str, Any]] = []
    deadline_rows: List[Dict[str, Any]] = []
    contacts_processed: List[Dict[str, Any]] = []

    for contact in contacts:
        try:
            folders = fetch_wiki_folders(client, contact["id"])
        except TakeoffApiError as exc:
            print(f"Takeoff API error for contact {contact['id']}: {exc}", file=sys.stderr)
            continue

        with open(RAW_DIR / f"{contact['id']}_wiki_folders.json", "w", encoding="utf-8") as f:
            json.dump(folders, f, ensure_ascii=False, indent=2)

        for folder in folders:
            subject_rows.append(build_subject_row(contact, folder, extracted_at))
            deadline_rows.extend(build_deadline_rows(folder, extracted_at))

        contacts_processed.append({"contact_id": contact["id"], "company_name": (contact.get("companyName") or "").strip()})

    write_jsonl(subject_rows, STAGING_DIR / "subjects.jsonl")
    write_jsonl(deadline_rows, STAGING_DIR / "deadlines_certificates.jsonl")

    manifest = {
        "extracted_at": extracted_at,
        "source_system": SOURCE_SYSTEM,
        "search_term": args.company_name,
        "exact_match": args.exact,
        "contacts": contacts_processed,
        "row_counts": {
            "subjects": len(subject_rows),
            "deadlines_certificates": len(deadline_rows),
        },
    }
    with open(STAGING_DIR / "_manifest.json", "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    print(f"Extracted {len(subject_rows)} subjects and {len(deadline_rows)} deadlines/certificates "
          f"for {len(contacts_processed)} contact(s).")
    print(f"Raw JSON:      {RAW_DIR}")
    print(f"Staging JSONL: {STAGING_DIR}")


if __name__ == "__main__":
    main()
