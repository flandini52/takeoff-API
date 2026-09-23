"""KPI row for the certificates/deadlines dashboard."""

import pandas as pd
import streamlit as st


def render_kpi_row(filtered: pd.DataFrame) -> None:
    n_people = filtered["subject_id"].nunique()
    n_certs = len(filtered)
    n_expired = (filtered["status"] == "Scaduto").sum()
    n_soon = (filtered["status"] == "Entro 30 giorni").sum()
    n_valid = (filtered["status"] == "Valido").sum()

    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("Persone", n_people)
    k2.metric("Certificati", n_certs)
    k3.metric("🔴 Scaduti", int(n_expired))
    k4.metric("🟠 Entro 30gg", int(n_soon))
    k5.metric("🟢 Validi", int(n_valid))
