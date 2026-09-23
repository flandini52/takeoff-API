"""Home: stato infrastruttura + ultimi run ETL."""

import streamlit as st

from services import database as db
from utils.access import require_access

require_access()

st.title("Landini Dashboard")
st.caption("Home")

status = db.get_connection_status()

if status.ok:
    st.success("Connesso a PostgreSQL")
    st.metric("Tabelle nello schema public", status.table_count)
    st.caption(f"Database: `{status.database}` · Host: `{status.host}:{status.port}`")
    st.caption(status.version)
else:
    st.error("Connessione a PostgreSQL fallita")
    st.caption(f"Database: `{status.database}` · Host: `{status.host}:{status.port}`")
    st.code(status.error)
    st.stop()

st.divider()

st.subheader("Ultimi aggiornamenti (etl_runs)")

runs = db.get_recent_etl_runs(limit=20)
if runs.empty:
    st.info("Nessun run ETL ancora eseguito. Usa '🔄 Aggiorna dati' nella sidebar di Manutenzioni o Scadenze dipendenti.")
else:
    display = runs.drop(columns=["id", "params"]).rename(
        columns={
            "entity": "Entità",
            "started_at": "Iniziato",
            "finished_at": "Terminato",
            "status": "Stato",
            "rows_loaded": "Righe caricate",
            "error": "Errore",
        }
    )
    st.dataframe(display, hide_index=True, width="stretch")
