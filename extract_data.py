import argparse
import csv
import json
import sys
from typing import Any, Dict, Iterator, List, Optional

from pydantic import ValidationError

from takeoff_client import TakeoffApiError, TakeoffClient

# Each entry describes how to page through a list endpoint of the TakeOff
# Integrators API (https://webapi.takeoffcrm.com/swagger/v1/swagger.json).
#
# pagination="query": skip/take are sent as query string params.
# pagination="body": skip/take are sent in the JSON body.
#
# The swagger docs the response as {"result": ..., "value": [...]} (GET) or
# {"result": ..., "value": {"data": [...]}} (POST), but the live API actually
# returns the payload unwrapped: a plain list for GET, and a plain object
# with a top-level "data" list for POST. _extract_records() below handles
# both shapes defensively.
#
# default_body: extra fields the endpoint requires even though the swagger
# marks them nullable (confirmed against the live API, not just the spec).
ENTITIES: Dict[str, Dict[str, Any]] = {
    "contacts": {"method": "GET", "path": "/api/contacts", "pagination": "query"},
    "jobs": {"method": "GET", "path": "/api/jobs", "pagination": "query"},
    "activities": {"method": "GET", "path": "/api/activities", "pagination": "query"},
    "estimates": {"method": "GET", "path": "/api/estimates", "pagination": "query"},
    "tasks": {"method": "GET", "path": "/api/tasks", "pagination": "query"},
    "contracts": {
        "method": "POST",
        "path": "/api/contracts/list",
        "pagination": "body",
        "default_body": {"filter": {}, "sort": ""},
    },
    "invoices": {"method": "POST", "path": "/api/invoices/search", "pagination": "body"},
}


def _extract_records(payload: Any) -> List[Dict[str, Any]]:
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        if isinstance(payload.get("data"), list):
            return payload["data"]
        value = payload.get("value")
        if isinstance(value, list):
            return value
        if isinstance(value, dict) and isinstance(value.get("data"), list):
            return value["data"]
    return []


def fetch_records(
    client: TakeoffClient,
    entity: str,
    take: int = 100,
    max_records: Optional[int] = None,
    extra_params: Optional[Dict[str, Any]] = None,
) -> Iterator[Dict[str, Any]]:
    config = ENTITIES[entity]
    extra_params = extra_params or {}
    skip = 0
    fetched = 0

    while True:
        page_size = take if max_records is None else min(take, max_records - fetched)
        if page_size <= 0:
            return

        if config["pagination"] == "query":
            params = {"skip": skip, "take": page_size, **extra_params}
            payload = client.get_json(config["path"], params=params)
        else:
            body = {**config.get("default_body", {}), "skip": skip, "take": page_size, **extra_params}
            payload = client.post_json(config["path"], json=body)

        records = _extract_records(payload)

        if not records:
            return

        for record in records:
            if max_records is not None and fetched >= max_records:
                return
            yield record
            fetched += 1

        if len(records) < page_size:
            return
        skip += page_size


def export_jsonl(records: Iterator[Dict[str, Any]], output_path: str) -> int:
    count = 0
    with open(output_path, "w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
            count += 1
    return count


def export_csv(records: Iterator[Dict[str, Any]], output_path: str) -> int:
    records = list(records)
    if not records:
        with open(output_path, "w", encoding="utf-8"):
            pass
        return 0
    fieldnames: List[str] = []
    for record in records:
        for key in record.keys():
            if key not in fieldnames:
                fieldnames.append(key)
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(records)
    return len(records)


def main() -> None:
    parser = argparse.ArgumentParser(description="Export data from Takeoff CRM to JSONL or CSV.")
    parser.add_argument("entity", choices=sorted(ENTITIES.keys()), help="Entity to export")
    parser.add_argument("--take", type=int, default=100, help="Page size (default 100)")
    parser.add_argument("--max-records", type=int, default=None, help="Maximum number of records to export")
    parser.add_argument("--format", choices=["jsonl", "csv"], default="jsonl")
    parser.add_argument("--output", default=None, help="Output file path")
    parser.add_argument(
        "--filter",
        default=None,
        help="JSON with extra params to merge into the query/body (e.g. entity-specific filters)",
    )
    args = parser.parse_args()

    extra_params = json.loads(args.filter) if args.filter else {}
    output_path = args.output or f"{args.entity}.{args.format}"

    try:
        client = TakeoffClient.from_settings()
    except ValidationError as exc:
        for error in exc.errors():
            print(f"Invalid configuration: {error['msg']}", file=sys.stderr)
        sys.exit(1)

    try:
        records = fetch_records(client, args.entity, take=args.take, max_records=args.max_records, extra_params=extra_params)
        if args.format == "jsonl":
            count = export_jsonl(records, output_path)
        else:
            count = export_csv(records, output_path)
    except TakeoffApiError as exc:
        print(f"Takeoff API error: {exc}", file=sys.stderr)
        sys.exit(1)

    print(f"Exported {count} '{args.entity}' records to {output_path}")


if __name__ == "__main__":
    main()
