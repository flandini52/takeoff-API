"""Streamlit dashboard: planned maintenance activities per worker.

For the selected month: how many "Manutenzione ordinaria programmata"
activities were planned, how many are done as of today, the completion %
per worker, what's still missing, and where (client site / city).

Reads the local SQLite DB built by extract_to_json.py + load_sqlite.py
(read-only — this file never talks to the Takeoff API directly, except via
the optional "refresh" button in the sidebar, which just shells out to
those same two pipeline scripts).

Usage:
    uv run streamlit run app/main.py
"""

import streamlit as st

from components.charts import build_completion_chart, compute_per_worker
from components.kpi import render_kpi_row
from components.sidebar import render_filters, render_refresh_panel
from components.tables import render_missing_by_location, render_per_worker_table, render_worker_detail
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
        "```\nuv run python extract_to_json.py --month YYYY-MM\nuv run python load_sqlite.py\n```"
    )
    st.stop()

df = load_data(DB_PATH.stat().st_mtime)

if df.empty:
    st.info("Il DB è vuoto. Esegui la pipeline di estrazione (vedi sidebar).")
    st.stop()

with st.sidebar:
    filtered = render_filters(df)

month_label = manifest.get("month", "—")
type_names = ", ".join(sorted(filtered["activity_type_name"].dropna().unique().tolist())) or "—"

st.title("Manutenzioni ordinarie pianificate")
st.caption(f"Mese: {month_label} · Tipo attività: {type_names}")

render_kpi_row(filtered)

st.divider()

st.subheader("Percentuale di completamento per operaio")
per_worker = compute_per_worker(filtered)
st.plotly_chart(build_completion_chart(per_worker), width="stretch")
render_per_worker_table(per_worker)

st.divider()

st.subheader("Dettaglio per operaio: cosa manca e dove")
render_worker_detail(per_worker, filtered)

st.divider()

st.subheader("Attività mancanti per posto")
render_missing_by_location(filtered)
