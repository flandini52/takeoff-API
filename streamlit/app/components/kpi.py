"""Shared KPI row — identical rendering on every business page; each page
computes its own (label, value) pairs."""

from typing import Any, Sequence, Tuple

import streamlit as st


def render_kpi_row(items: Sequence[Tuple[str, Any]]) -> None:
    columns = st.columns(len(items))
    for col, (label, value) in zip(columns, items):
        col.metric(label, value)
