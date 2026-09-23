"""Sidebar: refresh panel and filters."""

from datetime import date, datetime

import pandas as pd
import streamlit as st

from config.settings import PAGE_ICON, PAGE_TITLE
from services.pipeline import run_pipeline_refresh


def render_refresh_panel(manifest: dict) -> None:
    st.header(f"{PAGE_ICON} {PAGE_TITLE}")

    if manifest:
        extracted_at = manifest.get("extracted_at", "")
        try:
            extracted_dt = datetime.fromisoformat(extracted_at)
            st.caption(f"Ultima estrazione: {extracted_dt.strftime('%d/%m/%Y %H:%M')} UTC — mese {manifest.get('month', '—')}")
        except ValueError:
            st.caption(f"Ultima estrazione: {extracted_at}")

    with st.expander("🔄 Aggiorna dati da Takeoff CRM"):
        default_month = manifest.get("month", date.today().strftime("%Y-%m"))
        month_input = st.text_input("Mese (YYYY-MM)", value=default_month)
        default_types = ",".join(str(t) for t in manifest.get("type_ids", [16602]))
        types_input = st.text_input("Id tipi attività (separati da virgola)", value=default_types)
        if st.button("Aggiorna ora", type="primary"):
            with st.spinner("Estrazione da Takeoff CRM e ricarica del DB locale..."):
                ok, log = run_pipeline_refresh(month_input, types_input)
            if ok:
                st.success("Dati aggiornati.")
                st.cache_data.clear()
                st.rerun()
            else:
                st.error("Aggiornamento fallito, vedi log:")
                st.code(log)

    st.divider()


def render_filters(df: pd.DataFrame) -> pd.DataFrame:
    worker_query = st.text_input("Cerca operaio", placeholder="es. Arnone")
    workers = sorted(df["assigned_user_name"].dropna().unique().tolist())
    worker_filter = st.multiselect("Operaio", workers, default=[])
    cities = sorted(df["city"].dropna().unique().tolist())
    city_filter = st.multiselect("Città", cities, default=[])

    filtered = df.copy()
    if worker_query:
        filtered = filtered[filtered["assigned_user_name"].str.contains(worker_query, case=False, na=False)]
    if worker_filter:
        filtered = filtered[filtered["assigned_user_name"].isin(worker_filter)]
    if city_filter:
        filtered = filtered[filtered["city"].isin(city_filter)]
    return filtered
