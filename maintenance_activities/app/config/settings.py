"""Paths and static page config for the maintenance_activities dashboard."""

from pathlib import Path

# app/config/settings.py -> config/ -> app/ -> maintenance_activities/
PIPELINE_DIR = Path(__file__).resolve().parent.parent.parent
DB_PATH = PIPELINE_DIR / "db" / "maintenance_activities.db"
MANIFEST_PATH = PIPELINE_DIR / "data" / "staging" / "_manifest.json"

PAGE_TITLE = "Manutenzioni ordinarie"
PAGE_ICON = "🛠️"
