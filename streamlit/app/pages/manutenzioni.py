"""Manutenzioni ordinarie pianificate.

Porting di maintenance_activities/app/ sulla nuova architettura: stessa
logica di stato/filtri/aggregazione di prima, ma dati letti da PostgreSQL
invece che da SQLite locale, e refresh in-process (services/etl.py) invece
che via subprocess.
"""

from datetime import date

import pandas as pd
import streamlit as st

from components.charts import horizontal_bar_chart
from components.kpi import render_kpi_row
from components.sidebar import render_last_update, render_refresh_button
from services import database as db
from utils.access import require_access
from utils.status import ACTIVITY_STATUS_COLOR, ACTIVITY_STATUS_ICON, compute_activity_status, completion_color

require_access()

st.title("Manutenzioni ordinarie pianificate")

with st.sidebar:
    st.header("🛠️ Manutenzioni")
    render_last_update("activities")
    with st.expander("🔄 Aggiorna dati da Takeoff CRM"):
        month_input = st.text_input("Mese (YYYY-MM)", value=date.today().strftime("%Y-%m"), key="maint_month")
        types_input = st.text_input("Id tipi attività (separati da virgola)", value="16602", key="maint_types")
        type_ids = [int(t) for t in types_input.split(",")] if types_input else None
        render_refresh_button("activities", {"month": month_input, "type_ids": type_ids})
    st.divider()

df = db.get_activities()

if df.empty:
    st.info("Nessuna attività in PostgreSQL. Usa '🔄 Aggiorna dati' nella sidebar per eseguire l'ETL.")
    st.stop()

df["planned_start_dt"] = pd.to_datetime(df["planned_start"], errors="coerce")
df["planned_end_dt"] = pd.to_datetime(df["planned_end"], errors="coerce")
df["planned_start_date"] = df["planned_start_dt"].dt.date
df["planned_end_date"] = df["planned_end_dt"].dt.date
today = date.today()
df["status"] = df.apply(
    lambda r: compute_activity_status(bool(r["completed"]), r["planned_end_date"] or r["planned_start_date"], today),
    axis=1,
)
df["status_label"] = df["status"].map(lambda s: f"{ACTIVITY_STATUS_ICON[s]} {s}")

with st.sidebar:
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

type_names = ", ".join(sorted(filtered["activity_type_name"].dropna().unique().tolist())) or "—"
st.caption(f"Tipo attività: {type_names}")

# --- KPI row -------------------------------------------------------------

n_total = len(filtered)
n_done = int((filtered["status"] == "Completata").sum())
n_late = int((filtered["status"] == "In ritardo").sum())
n_todo = int((filtered["status"] == "Da fare").sum())
pct_done = round(100 * n_done / n_total, 1) if n_total else 0.0

render_kpi_row(
    [
        ("Pianificate", n_total),
        ("🟢 Completate", n_done),
        ("% Completamento", f"{pct_done}%"),
        ("🔴 In ritardo", n_late),
        ("🟡 Da fare", n_todo),
    ]
)

st.divider()

# --- Per-worker completion % ---------------------------------------------

st.subheader("Percentuale di completamento per operaio")

per_worker = (
    filtered.groupby("assigned_user_name")
    .agg(
        pianificate=("activity_id", "count"),
        completate=("status", lambda s: (s == "Completata").sum()),
        in_ritardo=("status", lambda s: (s == "In ritardo").sum()),
        da_fare=("status", lambda s: (s == "Da fare").sum()),
    )
    .reset_index()
)
per_worker["pct_completamento"] = (100 * per_worker["completate"] / per_worker["pianificate"]).round(1)
per_worker = per_worker.sort_values("pct_completamento")

fig = horizontal_bar_chart(
    labels=per_worker["assigned_user_name"],
    values=per_worker["pct_completamento"],
    colors=[completion_color(p) for p in per_worker["pct_completamento"]],
    text=[
        f"{p}% ({c}/{t})"
        for p, c, t in zip(per_worker["pct_completamento"], per_worker["completate"], per_worker["pianificate"])
    ],
    x_title="% completamento",
    x_range=[0, 110],
)
st.plotly_chart(fig, width="stretch")

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

st.divider()

# --- Per-worker detail: what's missing, and where -------------------------

st.subheader("Dettaglio per operaio: cosa manca e dove")

for _, row in per_worker.iterrows():
    worker = row["assigned_user_name"]
    missing = filtered[(filtered["assigned_user_name"] == worker) & (filtered["status"] != "Completata")].sort_values(
        "planned_start_dt"
    )
    if missing.empty:
        continue
    worst = "In ritardo" if (missing["status"] == "In ritardo").any() else "Da fare"
    with st.expander(f"{ACTIVITY_STATUS_ICON[worst]} **{worker}** — {len(missing)} mancanti ({row['pct_completamento']}% completato)"):
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

st.divider()

# --- Missing by location ---------------------------------------------------

st.subheader("Attività mancanti per posto")

missing_all = filtered[filtered["status"] != "Completata"].copy()

if missing_all.empty:
    st.success("Nessuna attività mancante con i filtri correnti.")
else:
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
            map_df = map_df.assign(color=map_df["status"].map(ACTIVITY_STATUS_COLOR))
            st.map(map_df, latitude="latitude", longitude="longitude", color="color", size=60)
