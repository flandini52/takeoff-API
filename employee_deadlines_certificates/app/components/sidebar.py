"""Sidebar: refresh panel and filters."""

from datetime import datetime

import pandas as pd
import streamlit as st

from config.settings import PAGE_ICON, PAGE_TITLE
from services.pipeline import run_pipeline_refresh
from utils.status import STATUS_ORDER


def render_refresh_panel(manifest: dict) -> None:
    st.header(f"{PAGE_ICON} {PAGE_TITLE}")

    if manifest:
        extracted_at = manifest.get("extracted_at", "")
        try:
            extracted_dt = datetime.fromisoformat(extracted_at)
            st.caption(f"Ultima estrazione: {extracted_dt.strftime('%d/%m/%Y %H:%M')} UTC")
        except ValueError:
            st.caption(f"Ultima estrazione: {extracted_at}")

    with st.expander("🔄 Aggiorna dati da Takeoff CRM"):
        default_term = manifest.get("search_term", "LANDINI SRL")
        search_term = st.text_input("Ragione sociale", value=default_term)
        exact = st.checkbox("Corrispondenza esatta", value=manifest.get("exact_match", True))
        if st.button("Aggiorna ora", type="primary"):
            with st.spinner("Estrazione da Takeoff CRM e ricarica del DB locale..."):
                ok, log = run_pipeline_refresh(search_term, exact)
            if ok:
                st.success("Dati aggiornati.")
                st.cache_data.clear()
                st.rerun()
            else:
                st.error("Aggiornamento fallito, vedi log:")
                st.code(log)

    st.divider()


def render_filters(df: pd.DataFrame) -> pd.DataFrame:
    only_employees = st.toggle("Solo dipendenti (escludi es. veicoli)", value=True)
    name_query = st.text_input("Cerca persona", placeholder="es. Arnone")
    categories = sorted(df["element_category"].dropna().unique().tolist())
    category_filter = st.multiselect("Tipologia certificato", categories, default=[])
    status_filter = st.multiselect("Stato", STATUS_ORDER, default=[])

    filtered = df.copy()
    if only_employees:
        filtered = filtered[filtered["is_employee"] == 1]
    if name_query:
        filtered = filtered[filtered["subject_name"].str.contains(name_query, case=False, na=False)]
    if category_filter:
        filtered = filtered[filtered["element_category"].isin(category_filter)]
    if status_filter:
        filtered = filtered[filtered["status"].isin(status_filter)]
    return filtered
