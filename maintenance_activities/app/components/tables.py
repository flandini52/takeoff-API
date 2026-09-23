"""Tables and map: per-worker completion, per-worker detail, missing by location."""

import pandas as pd
import streamlit as st

from utils.status import STATUS_COLOR, STATUS_ICON


def render_per_worker_table(per_worker: pd.DataFrame) -> None:
    st.dataframe(
        per_worker.rename(
            columns={
                "assigned_user_name": "Operaio",
                "pianificate": "Pianificate",
                "completate": "Completate",
                "in_ritardo": "In ritardo",
                "da_fare": "Da fare",
                "pct_completamento": "% Completamento",
            }
        ),
        hide_index=True,
        width="stretch",
    )


def render_worker_detail(per_worker: pd.DataFrame, filtered: pd.DataFrame) -> None:
    for _, row in per_worker.iterrows():
        worker = row["assigned_user_name"]
        missing = filtered[(filtered["assigned_user_name"] == worker) & (filtered["status"] != "Completata")].sort_values(
            "planned_start_dt"
        )
        if missing.empty:
            continue
        worst = "In ritardo" if (missing["status"] == "In ritardo").any() else "Da fare"
        with st.expander(f"{STATUS_ICON[worst]} **{worker}** — {len(missing)} mancanti ({row['pct_completamento']}% completato)"):
            table = missing[["company_name", "city", "address", "planned_start_dt", "status_label"]].rename(
                columns={
                    "company_name": "Cliente",
                    "city": "Città",
                    "address": "Indirizzo",
                    "planned_start_dt": "Data pianificata",
                    "status_label": "Stato",
                }
            )
            st.dataframe(table, hide_index=True, width="stretch")


def render_missing_by_location(filtered: pd.DataFrame) -> None:
    missing_all = filtered[filtered["status"] != "Completata"].copy()

    if missing_all.empty:
        st.success("Nessuna attività mancante con i filtri correnti.")
        return

    by_city = (
        missing_all.groupby("city")
        .agg(
            mancanti=("activity_id", "count"),
            operai=("assigned_user_name", lambda s: ", ".join(sorted(set(s.dropna())))),
        )
        .reset_index()
        .sort_values("mancanti", ascending=False)
        .rename(columns={"city": "Città", "mancanti": "Mancanti", "operai": "Operai coinvolti"})
    )
    col_table, col_map = st.columns([1, 1.2])
    with col_table:
        st.dataframe(by_city, hide_index=True, width="stretch", height=320)
    with col_map:
        map_df = missing_all.dropna(subset=["latitude", "longitude"])
        map_df = map_df[(map_df["latitude"] != 0) & (map_df["longitude"] != 0)]
        if map_df.empty:
            st.info("Nessuna coordinata disponibile per la mappa.")
        else:
            map_df = map_df.assign(color=map_df["status"].map(STATUS_COLOR))
            st.map(map_df, latitude="latitude", longitude="longitude", color="color", size=60)
