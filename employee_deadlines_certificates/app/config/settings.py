"""Paths and static page config for the employee_deadlines_certificates dashboard."""

from pathlib import Path

# app/config/settings.py -> config/ -> app/ -> employee_deadlines_certificates/
PIPELINE_DIR = Path(__file__).resolve().parent.parent.parent
DB_PATH = PIPELINE_DIR / "db" / "employee_deadlines_certificates.db"
MANIFEST_PATH = PIPELINE_DIR / "data" / "staging" / "_manifest.json"

PAGE_TITLE = "Scadenze & Certificati"
PAGE_ICON = "📋"
