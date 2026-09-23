"""Read access to the local SQLite DB built by extract_to_json.py + load_sqlite.py."""

import sqlite3
from datetime import date

import pandas as pd
import streamlit as st

from config.settings import DB_PATH
from utils.status import STATUS_ICON, compute_status


@st.cache_data
def load_data(db_mtime: float) -> pd.DataFrame:
    """db_mtime is part of the cache key: pass the file's mtime so the cache
    invalidates automatically whenever the DB is reloaded (e.g. after the
    sidebar refresh button re-runs the pipeline)."""
    conn = sqlite3.connect(DB_PATH)
    try:
        df = pd.read_sql_query(
            """
            SELECT s.subject_id, s.subject_name, s.subject_category, s.is_employee,
                   s.company_name, d.element_id, d.element_name, d.element_category,
                   d.expiry_date, d.document_filename
            FROM subjects s
            JOIN deadlines_certificates d ON d.subject_id = s.subject_id
            """,
            conn,
        )
    finally:
        conn.close()
    df["expiry_date"] = pd.to_datetime(df["expiry_date"], errors="coerce").dt.date
    today = date.today()
    df["status"] = df["expiry_date"].apply(lambda d: compute_status(d, today))
    df["status_label"] = df["status"].map(lambda s: f"{STATUS_ICON[s]} {s}")
    return df
