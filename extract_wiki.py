"""Export Wiki data (folders/elements/properties) for a Contact from Takeoff CRM.

Unlike the entities in extract_data.py (flat, paginated lists), Wiki data is
scoped to a single Contact and nested: a Contact has Wiki Folders, each
Folder has Wiki Elements, each Element has Properties (key/value, possibly a
file). This script resolves a contact by company name, fetches its full wiki
tree via GET /api/wiki/folders?contactId=..., and flattens it into rows
(one per property, or one per element if it has no properties) for CSV/JSONL
export.

Usage:
    uv run python extract_wiki.py "Landini Srl" [--exact] [--format csv|jsonl] [--output path]
"""

import argparse
import csv
import json
import sys
from typing import Any, Dict, Iterator, List

from pydantic import ValidationError

from takeoff_client import TakeoffApiError, TakeoffClient


def find_contacts(client: TakeoffClient, company_name: str, exact: bool = False) -> List[Dict[str, Any]]:
    params = {"skip": 0, "take": 50}
    if exact:
        params["companyName"] = company_name
    else:
        params["companyNameLike"] = company_name
    return client.get_json("/api/contacts", params=params)


def fetch_wiki_folders(client: TakeoffClient, contact_id: int) -> List[Dict[str, Any]]:
    return client.get_json("/api/wiki/folders", params={"contactId": contact_id})


def flatten_folders(contact: Dict[str, Any], folders: List[Dict[str, Any]]) -> Iterator[Dict[str, Any]]:
    """Yield one row per (folder, element, property), or one row per element
    if it has no properties, or one row per folder if it has no elements."""
    base = {
        "contactId": contact["id"],
        "companyName": contact.get("companyName", "").strip(),
    }
    for folder in folders:
        folder_row = {
            **base,
            "folderId": folder.get("id"),
            "folderName": folder.get("name"),
            "folderTypology": (folder.get("typology") or {}).get("name"),
        }
        elements = folder.get("elements") or []
        if not elements:
            yield {**folder_row, "elementId": None, "elementName": None, "elementTypology": None,
                   "propertyName": None, "propertyDataType": None, "propertyValue": None}
            continue
        for element in elements:
            element_row = {
                **folder_row,
                "elementId": element.get("id"),
                "elementName": element.get("name"),
                "elementTypology": (element.get("typology") or {}).get("name"),
            }
            properties = element.get("properties") or []
            if not properties:
                yield {**element_row, "propertyName": None, "propertyDataType": None, "propertyValue": None}
                continue
            for prop in properties:
                yield {
                    **element_row,
                    "propertyName": prop.get("name"),
                    "propertyDataType": prop.get("dataType"),
                    "propertyValue": prop.get("value"),
                }


def export_jsonl(rows: List[Dict[str, Any]], output_path: str) -> int:
    with open(output_path, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return len(rows)


def export_csv(rows: List[Dict[str, Any]], output_path: str) -> int:
    if not rows:
        with open(output_path, "w", encoding="utf-8"):
            pass
        return 0
    fieldnames = list(rows[0].keys())
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Export Wiki data for a Contact from Takeoff CRM.")
    parser.add_argument("company_name", help="Company name (or partial name) to search for")
    parser.add_argument("--exact", action="store_true", help="Match companyName exactly instead of a substring search")
    parser.add_argument("--format", choices=["jsonl", "csv"], default="csv")
    parser.add_argument("--output", default=None, help="Output file path")
    args = parser.parse_args()

    try:
        client = TakeoffClient.from_settings()
    except ValidationError as exc:
        for error in exc.errors():
            print(f"Invalid configuration: {error['msg']}", file=sys.stderr)
        sys.exit(1)

    try:
        contacts = find_contacts(client, args.company_name, exact=args.exact)
    except TakeoffApiError as exc:
        print(f"Takeoff API error: {exc}", file=sys.stderr)
        sys.exit(1)

    if not contacts:
        print(f"No contact found matching '{args.company_name}'", file=sys.stderr)
        sys.exit(1)

    if len(contacts) > 1:
        print(f"Found {len(contacts)} matching contacts, exporting wiki data for all of them:", file=sys.stderr)
        for c in contacts:
            print(f"  - id={c['id']} companyName={c.get('companyName', '').strip()!r}", file=sys.stderr)

    all_rows: List[Dict[str, Any]] = []
    for contact in contacts:
        try:
            folders = fetch_wiki_folders(client, contact["id"])
        except TakeoffApiError as exc:
            print(f"Takeoff API error for contact {contact['id']}: {exc}", file=sys.stderr)
            continue
        all_rows.extend(flatten_folders(contact, folders))

    output_path = args.output or f"wiki_{args.company_name.strip().replace(' ', '_')}.{args.format}"
    count = export_csv(all_rows, output_path) if args.format == "csv" else export_jsonl(all_rows, output_path)
    print(f"Exported {count} wiki rows to {output_path}")


if __name__ == "__main__":
    main()
