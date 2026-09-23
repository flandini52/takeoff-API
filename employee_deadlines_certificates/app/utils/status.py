"""Status classification and palette for certificate/deadline expiry.

Status palette (fixed status roles — never reused for categorical series).
Severity order: critical > serious > warning > good.
"""

from datetime import date

import pandas as pd

STATUS_ORDER = ["Scaduto", "Entro 30 giorni", "Entro 90 giorni", "Valido", "Senza scadenza"]
STATUS_COLOR = {
    "Scaduto": "#d03b3b",  # critical
    "Entro 30 giorni": "#ec835a",  # serious
    "Entro 90 giorni": "#fab219",  # warning
    "Valido": "#0ca30c",  # good
    "Senza scadenza": "#898781",  # muted / neutral (no status claim)
}
STATUS_ICON = {
    "Scaduto": "🔴",
    "Entro 30 giorni": "🟠",
    "Entro 90 giorni": "🟡",
    "Valido": "🟢",
    "Senza scadenza": "⚪",
}


def compute_status(expiry: "date | None", today: "date") -> str:
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
