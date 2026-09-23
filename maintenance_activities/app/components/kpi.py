"""KPI row for the maintenance activities dashboard."""

import pandas as pd
import streamlit as st


def render_kpi_row(filtered: pd.DataFrame) -> None:
    n_total = len(filtered)
    n_done = int((filtered["status"] == "Completata").sum())
    n_late = int((filtered["status"] == "In ritardo").sum())
    n_todo = int((filtered["status"] == "Da fare").sum())
    pct_done = round(100 * n_done / n_total, 1) if n_total else 0.0

    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("Pianificate", n_total)
    k2.metric("🟢 Completate", n_done)
    k3.metric("% Completamento", f"{pct_done}%")
    k4.metric("🔴 In ritardo", n_late)
    k5.metric("🟡 Da fare", n_todo)
