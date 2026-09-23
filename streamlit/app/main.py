"""Landini Dashboard — entry point.

st.navigation across three pages: Home (stato infrastruttura + etl_runs),
Manutenzioni (porting di maintenance_activities/app), Scadenze dipendenti
(porting di employee_deadlines_certificates/app). Each page reads from
PostgreSQL via services/database.py and triggers the ETL in-process via
services/etl.py — never straight from the gestionale, never a subprocess.

Usage (inside the streamlit container): streamlit run app/main.py
"""

import streamlit as st

st.set_page_config(page_title="Landini Dashboard", page_icon="📊", layout="wide")

pages = st.navigation(
    [
        st.Page("pages/home.py", title="Home", icon="🏠"),
        st.Page("pages/manutenzioni.py", title="Manutenzioni", icon="🛠️"),
        st.Page("pages/scadenze.py", title="Scadenze dipendenti", icon="📋"),
    ]
)
pages.run()
