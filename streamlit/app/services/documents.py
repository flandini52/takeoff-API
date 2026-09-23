"""Live document download from Takeoff CRM (Wiki module).

Unlike the rest of the dashboard, this DOES call the gestionale directly in
real time (see README, "chiamate API dirette... solo dove necessario").
Reason: GET /api/wiki/{elementId} returns a short-lived Azure Blob SAS URL
(~24h) for the "Documento" property — it can't be extracted once by the
ETL and stored in Postgres for later use, it has to be fetched fresh at
download time.
"""

import io
import zipfile
from typing import Iterable, List, Optional, Set, Tuple

import requests

from landini_etl.api.client import TakeoffClient

DOCUMENT_PROPERTY_NAME = "documento"


def _fetch_document_url(client: TakeoffClient, element_id: int) -> Optional[Tuple[str, str]]:
    """(url, filename) for the wiki element's "Documento" property, or
    None if it has none."""
    detail = client.get_json(f"/api/wiki/{element_id}")
    for group in detail.get("properties") or []:
        for prop in group.get("properties") or []:
            if (prop.get("name") or "").strip().lower() == DOCUMENT_PROPERTY_NAME and prop.get("url"):
                filename = prop.get("fileNameLabel") or f"{element_id}.pdf"
                return prop["url"], filename
    return None


def _dedupe_name(filename: str, used_names: Set[str]) -> str:
    if filename not in used_names:
        used_names.add(filename)
        return filename
    stem, dot, ext = filename.rpartition(".")
    n = 1
    while True:
        candidate = f"{stem} ({n}).{ext}" if dot else f"{filename} ({n})"
        if candidate not in used_names:
            used_names.add(candidate)
            return candidate
        n += 1


def download_documents_zip(element_ids: Iterable[int]) -> Tuple[bytes, List[str]]:
    """Downloads the "Documento" file for each wiki element id and bundles
    them into a single zip. Returns (zip_bytes, missing_ids) — missing_ids
    lists which element ids had no document, or failed to download.
    """
    client = TakeoffClient.from_settings()
    buffer = io.BytesIO()
    missing: List[str] = []
    used_names: Set[str] = set()

    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for element_id in element_ids:
            try:
                result = _fetch_document_url(client, int(element_id))
                if result is None:
                    missing.append(str(element_id))
                    continue
                url, filename = result
                response = requests.get(url, timeout=30)
                response.raise_for_status()
            except Exception:
                missing.append(str(element_id))
                continue
            zf.writestr(_dedupe_name(filename, used_names), response.content)

    return buffer.getvalue(), missing
