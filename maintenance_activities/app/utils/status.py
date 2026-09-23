"""Status classification and palette for planned maintenance activities.

Status palette (fixed status roles — never reused for categorical series).
"""

from datetime import date

import pandas as pd

STATUS_ORDER = ["In ritardo", "Da fare", "Completata"]
STATUS_COLOR = {
    "In ritardo": "#d03b3b",  # critical
    "Da fare": "#fab219",  # warning
    "Completata": "#0ca30c",  # good
}
STATUS_ICON = {"In ritardo": "🔴", "Da fare": "🟡", "Completata": "🟢"}


def compute_status(completed: bool, planned_end: "date | None", today: "date") -> str:
    if completed:
        return "Completata"
    if planned_end is not None and not pd.isna(planned_end) and planned_end < today:
        return "In ritardo"
    return "Da fare"


def completion_color(pct: float) -> str:
    if pct >= 80:
        return STATUS_COLOR["Completata"]
    if pct >= 50:
        return STATUS_COLOR["Da fare"]
    return STATUS_COLOR["In ritardo"]
