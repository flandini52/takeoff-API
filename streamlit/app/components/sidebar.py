"""Shared "Aggiorna dati" sidebar control — same mechanics (button,
spinner, lock handling, cache clear + rerun) on every business page; each
page supplies its own entity name and input widgets/params.
"""

import streamlit as st

from services import database as db
from services.etl import trigger_refresh


def render_refresh_button(entity: str, params: dict) -> None:
    if st.button("Aggiorna ora", type="primary", key=f"refresh_{entity}"):
        with st.spinner("Estrazione da Takeoff CRM e caricamento in PostgreSQL..."):
            ok, message = trigger_refresh(entity, **params)
        if ok:
            st.success(message)
            st.cache_data.clear()
            st.rerun()
        else:
            st.error(message)


def render_last_update(entity: str) -> None:
    last_run = db.get_last_successful_run(entity)
    if last_run is None:
        st.caption("Ultimo aggiornamento: mai")
    else:
        finished_at = last_run["finished_at"]
        rows = int(last_run["rows_loaded"]) if last_run["rows_loaded"] is not None else 0
        st.caption(f"Ultimo aggiornamento: {finished_at:%d/%m/%Y %H:%M} — {rows} record")
