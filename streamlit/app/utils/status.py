"""Status classification and palettes that depend on "oggi" — kept in the
dashboard (not the DB) since "oggi" changes on every page load, unlike
anything the ETL could precompute once at load time.

Two independent status domains, ported unchanged from the old
maintenance_activities/app and employee_deadlines_certificates/app:
activities (Completata/In ritardo/Da fare) and deadlines (Scaduto/Entro 30
giorni/Entro 90 giorni/Valido/Senza scadenza).
"""

from datetime import date
from typing import Optional

import pandas as pd

# --- activities (Manutenzioni) ------------------------------------------
# Status palette (fixed status roles — never reused for categorical series).

ACTIVITY_STATUS_ORDER = ["In ritardo", "Da fare", "Completata"]
ACTIVITY_STATUS_COLOR = {
    "In ritardo": "#d03b3b",  # critical
    "Da fare": "#fab219",  # warning
    "Completata": "#0ca30c",  # good
}
ACTIVITY_STATUS_ICON = {"In ritardo": "🔴", "Da fare": "🟡", "Completata": "🟢"}


def compute_activity_status(completed: bool, planned_end: Optional[date], today: date) -> str:
    if completed:
        return "Completata"
    if planned_end is not None and not pd.isna(planned_end) and planned_end < today:
        return "In ritardo"
    return "Da fare"


def completion_color(pct: float) -> str:
    if pct >= 80:
        return ACTIVITY_STATUS_COLOR["Completata"]
    if pct >= 50:
        return ACTIVITY_STATUS_COLOR["Da fare"]
    return ACTIVITY_STATUS_COLOR["In ritardo"]


# --- deadlines (Scadenze dipendenti) -------------------------------------
# Severity order: critical > serious > warning > good.

DEADLINE_STATUS_ORDER = ["Scaduto", "Entro 30 giorni", "Entro 90 giorni", "Valido", "Senza scadenza"]
DEADLINE_STATUS_COLOR = {
    "Scaduto": "#d03b3b",  # critical
    "Entro 30 giorni": "#ec835a",  # serious
    "Entro 90 giorni": "#fab219",  # warning
    "Valido": "#0ca30c",  # good
    "Senza scadenza": "#898781",  # muted / neutral (no status claim)
}
DEADLINE_STATUS_ICON = {
    "Scaduto": "🔴",
    "Entro 30 giorni": "🟠",
    "Entro 90 giorni": "🟡",
    "Valido": "🟢",
    "Senza scadenza": "⚪",
}


def compute_deadline_status(expiry: Optional[date], today: date) -> str:
    if expiry is None or pd.isna(expiry):
        return "Senza scadenza"
    delta = (expiry - today).days
    if delta < 0:
        return "Scaduto"
    if delta <= 30:
        return "Entro 30 giorni"
    if delta <= 90:
        return "Entro 90 giorni"
    return "Valido"
