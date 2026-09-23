"""Scadenze & Certificati per persona.

Porting di employee_deadlines_certificates/app/ sulla nuova architettura:
stessa logica di stato/filtri di prima, ma dati letti da PostgreSQL invece
che da SQLite locale, e refresh in-process (services/etl.py) invece che
via subprocess.
"""

from datetime import date

import pandas as pd
import streamlit as st

from components.charts import horizontal_bar_chart
from components.kpi import render_kpi_row
from components.sidebar import render_last_update, render_refresh_button
from services import database as db
from utils.access import require_access
from utils.status import DEADLINE_STATUS_COLOR, DEADLINE_STATUS_ICON, DEADLINE_STATUS_ORDER, compute_deadline_status

require_access()

st.title("Scadenze & Certificati per persona")

with st.sidebar:
    st.header("📋 Scadenze & Certificati")
    render_last_update("deadlines")
    with st.expander("🔄 Aggiorna dati da Takeoff CRM"):
        company_name = st.text_input("Ragione sociale", value="LANDINI SRL", key="deadlines_company")
        exact = st.checkbox("Corrispondenza esatta", value=True, key="deadlines_exact")
        render_refresh_button("deadlines", {"company_name": company_name, "exact": exact})
    st.divider()

df = db.get_deadlines()

if df.empty:
    st.info("Nessuna scadenza/certificato in PostgreSQL. Usa '🔄 Aggiorna dati' nella sidebar per eseguire l'ETL.")
    st.stop()

df["expiry_date"] = pd.to_datetime(df["expiry_date"], errors="coerce").dt.date
today = date.today()
df["status"] = df["expiry_date"].apply(lambda d: compute_deadline_status(d, today))
df["status_label"] = df["status"].map(lambda s: f"{DEADLINE_STATUS_ICON[s]} {s}")

with st.sidebar:
    only_employees = st.toggle("Solo dipendenti (escludi es. veicoli)", value=True)
    name_query = st.text_input("Cerca persona", placeholder="es. Arnone")
    categories = sorted(df["element_category"].dropna().unique().tolist())
    category_filter = st.multiselect("Tipologia certificato", categories, default=[])
    status_filter = st.multiselect("Stato", DEADLINE_STATUS_ORDER, default=[])

filtered = df.copy()
if only_employees:
    filtered = filtered[filtered["is_employee"]]
if name_query:
    filtered = filtered[filtered["subject_name"].str.contains(name_query, case=False, na=False)]
if category_filter:
    filtered = filtered[filtered["element_category"].isin(category_filter)]
if status_filter:
    filtered = filtered[filtered["status"].isin(status_filter)]

# --- KPI row -------------------------------------------------------------

n_people = filtered["subject_id"].nunique()
n_certs = len(filtered)
n_expired = (filtered["status"] == "Scaduto").sum()
n_soon = (filtered["status"] == "Entro 30 giorni").sum()
n_valid = (filtered["status"] == "Valido").sum()

st.caption(f"Fonte: {df['company_name'].iloc[0] if not df.empty else '—'} (Takeoff CRM, Wiki)")

render_kpi_row(
    [
        ("Persone", n_people),
        ("Certificati", n_certs),
        ("🔴 Scaduti", int(n_expired)),
        ("🟠 Entro 30gg", int(n_soon)),
        ("🟢 Validi", int(n_valid)),
    ]
)

st.divider()

# --- Status distribution chart + upcoming table ---------------------------

col_chart, col_next = st.columns([1, 1.4])

with col_chart:
    st.subheader("Distribuzione per stato")
    counts = filtered["status"].value_counts().reindex(DEADLINE_STATUS_ORDER).fillna(0).astype(int)
    counts = counts[counts > 0]
    fig = horizontal_bar_chart(
        labels=[f"{DEADLINE_STATUS_ICON[s]} {s}" for s in counts.index],
        values=counts.values,
        colors=[DEADLINE_STATUS_COLOR[s] for s in counts.index],
        text=counts.values,
        height=280,
        reversed_yaxis=True,
    )
    st.plotly_chart(fig, width="stretch")

with col_next:
    st.subheader("Prossime scadenze")
    upcoming = (
        filtered[filtered["status"].isin(["Scaduto", "Entro 30 giorni", "Entro 90 giorni"])]
        .sort_values("expiry_date")[["subject_name", "element_name", "expiry_date", "status_label"]]
        .rename(
            columns={
                "subject_name": "Persona",
                "element_name": "Certificato",
                "expiry_date": "Scadenza",
                "status_label": "Stato",
            }
        )
    )
    st.dataframe(upcoming, hide_index=True, width="stretch", height=280)

st.divider()

# --- Per-person breakdown --------------------------------------------------

st.subheader(f"Dettaglio per persona ({n_people})")

# Sort people by their most urgent certificate (earliest expiry / worst status).
severity_rank = {s: i for i, s in enumerate(DEADLINE_STATUS_ORDER)}
person_order = (
    filtered.assign(_rank=filtered["status"].map(severity_rank))
    .sort_values(["_rank", "expiry_date"])
    .groupby("subject_name", sort=False)
    .first()
    .index.tolist()
)

if not person_order:
    st.info("Nessun risultato con i filtri correnti.")

for person in person_order:
    person_rows = filtered[filtered["subject_name"] == person].sort_values("expiry_date")
    worst_status = person_rows.iloc[person_rows["status"].map(severity_rank).values.argmin()]["status"]
    badge = f"{DEADLINE_STATUS_ICON[worst_status]}"
    with st.expander(f"{badge} **{person}** — {len(person_rows)} certificati"):
        table = person_rows[["element_name", "element_category", "expiry_date", "status_label", "document_filename"]].rename(
            columns={
                "element_name": "Certificato",
                "element_category": "Tipologia",
                "expiry_date": "Scadenza",
                "status_label": "Stato",
                "document_filename": "Documento",
            }
        )
        st.dataframe(table, hide_index=True, width="stretch")
