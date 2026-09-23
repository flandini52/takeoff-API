"""Per-worker completion aggregation and chart."""

import pandas as pd
import plotly.graph_objects as go

from utils.status import completion_color


def compute_per_worker(filtered: pd.DataFrame) -> pd.DataFrame:
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
    return per_worker.sort_values("pct_completamento")


def build_completion_chart(per_worker: pd.DataFrame) -> go.Figure:
    fig = go.Figure(
        go.Bar(
            x=per_worker["pct_completamento"],
            y=per_worker["assigned_user_name"],
            orientation="h",
            marker_color=[completion_color(p) for p in per_worker["pct_completamento"]],
            text=[
                f"{p}% ({c}/{t})"
                for p, c, t in zip(per_worker["pct_completamento"], per_worker["completate"], per_worker["pianificate"])
            ],
            textposition="outside",
        )
    )
    fig.update_layout(
        height=max(220, 40 * len(per_worker)),
        margin=dict(l=0, r=80, t=10, b=10),
        xaxis_title="% completamento",
        yaxis_title=None,
        xaxis_range=[0, 110],
        showlegend=False,
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
    )
    return fig
