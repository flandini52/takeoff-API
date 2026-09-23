"""Streamlit dashboard: certificates & deadlines per employee.

Reads the local SQLite DB built by extract_to_json.py + load_sqlite.py
(read-only — this file never talks to the Takeoff API directly, except via
the optional "refresh" button in the sidebar, which just shells out to those
same two pipeline scripts).

Usage:
    uv run streamlit run app/main.py
"""

import streamlit as st

from components.charts import build_status_distribution_chart
from components.kpi import render_kpi_row
from components.sidebar import render_filters, render_refresh_panel
from components.tables import render_person_detail, render_upcoming_table
from config.settings import DB_PATH, PAGE_ICON, PAGE_TITLE
from services.database import load_data
from services.pipeline import load_manifest

st.set_page_config(page_title=PAGE_TITLE, page_icon=PAGE_ICON, layout="wide")

manifest = load_manifest()

with st.sidebar:
    render_refresh_panel(manifest)

if not DB_PATH.exists():
    st.warning(
        "Nessun DB locale trovato. Esegui la pipeline di estrazione prima di aprire la dashboard:\n\n"
        "```\nuv run python extract_to_json.py \"NOME AZIENDA\" --exact\nuv run python load_sqlite.py\n```"
    )
    st.stop()

df = load_data(DB_PATH.stat().st_mtime)

if df.empty:
    st.info("Il DB è vuoto. Esegui la pipeline di estrazione (vedi sidebar).")
    st.stop()

with st.sidebar:
    filtered = render_filters(df)

st.title("Scadenze & Certificati per persona")
st.caption(f"Fonte: {df['company_name'].iloc[0] if not df.empty else '—'} (Takeoff CRM, Wiki)")

render_kpi_row(filtered)

st.divider()

col_chart, col_next = st.columns([1, 1.4])
with col_chart:
    st.subheader("Distribuzione per stato")
    st.plotly_chart(build_status_distribution_chart(filtered), width="stretch")
with col_next:
    st.subheader("Prossime scadenze")
    render_upcoming_table(filtered)

st.divider()

st.subheader(f"Dettaglio per persona ({filtered['subject_id'].nunique()})")
render_person_detail(filtered)
