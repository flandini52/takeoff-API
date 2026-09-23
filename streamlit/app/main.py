"""Landini Dashboard — infrastructure check page.

Verifies that the container is running and that Streamlit can reach
PostgreSQL. No business pages/charts yet — see services/database.py for
the DB layer future pages will build on, and pages/ / components/ / utils/
for where that work will live.

Usage (inside the streamlit container): streamlit run app/main.py
"""

import streamlit as st

from services.database import get_connection_status

st.set_page_config(page_title="Landini Dashboard", page_icon="📊", layout="centered")

st.title("Landini Dashboard")
st.caption("Infrastructure check")

status = get_connection_status()

if status.ok:
    st.success("Connesso a PostgreSQL")
    st.metric("Tabelle nello schema public", status.table_count)
    st.caption(f"Database: `{status.database}` · Host: `{status.host}:{status.port}`")
    st.caption(status.version)
else:
    st.error("Connessione a PostgreSQL fallita")
    st.caption(f"Database: `{status.database}` · Host: `{status.host}:{status.port}`")
    st.code(status.error)

st.divider()
st.caption("Dashboard e pagine business verranno aggiunte nelle fasi successive.")
