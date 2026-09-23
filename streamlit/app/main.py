"""Landini Dashboard — entry point.

st.navigation: Home (stato infrastruttura + etl_runs) e Manutenzioni
(porting di maintenance_activities/app) sempre presenti. Scadenze
dipendenti (porting di employee_deadlines_certificates/app) solo se
ENABLE_SCADENZE=true (vedi .env.example) — resta nascosta in produzione
finché non c'è il login (V2). Ogni pagina legge da PostgreSQL via
services/database.py e attiva l'ETL in-process via services/etl.py — mai
il gestionale direttamente, mai un subprocess.

Usage: uv run streamlit run streamlit/app/main.py (o, dentro Docker,
streamlit run app/main.py — vedi streamlit/Dockerfile)
"""

import streamlit as st

from landini_etl.config import get_settings

st.set_page_config(page_title="Landini Dashboard", page_icon="📊", layout="wide")

settings = get_settings()

_pages = [
    st.Page("pages/home.py", title="Home", icon="🏠"),
    st.Page("pages/manutenzioni.py", title="Manutenzioni", icon="🛠️"),
]
if settings.enable_scadenze:
    _pages.append(st.Page("pages/scadenze.py", title="Scadenze dipendenti", icon="📋"))

pages = st.navigation(_pages)
pages.run()
