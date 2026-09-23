"""Tables: upcoming expirations and per-person detail."""

import pandas as pd
import streamlit as st

from utils.status import STATUS_ICON, STATUS_ORDER


def render_upcoming_table(filtered: pd.DataFrame) -> None:
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


def render_person_detail(filtered: pd.DataFrame) -> None:
    # Sort people by their most urgent certificate (earliest expiry / worst status).
    severity_rank = {s: i for i, s in enumerate(STATUS_ORDER)}
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
        badge = f"{STATUS_ICON[worst_status]}"
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
