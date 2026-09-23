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
        df = pd.read_sql_query("SELECT * FROM activities", conn)
    finally:
        conn.close()
    df["planned_start_dt"] = pd.to_datetime(df["planned_start"], errors="coerce")
    df["planned_end_dt"] = pd.to_datetime(df["planned_end"], errors="coerce")
    df["planned_start_date"] = df["planned_start_dt"].dt.date
    df["planned_end_date"] = df["planned_end_dt"].dt.date
    today = date.today()
    df["status"] = df.apply(
        lambda r: compute_status(bool(r["completed"]), r["planned_end_date"] or r["planned_start_date"], today),
        axis=1,
    )
    df["status_label"] = df["status"].map(lambda s: f"{STATUS_ICON[s]} {s}")
    return df
