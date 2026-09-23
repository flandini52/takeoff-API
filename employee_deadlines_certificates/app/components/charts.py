"""Status-distribution chart."""

import pandas as pd
import plotly.graph_objects as go

from utils.status import STATUS_COLOR, STATUS_ICON, STATUS_ORDER


def build_status_distribution_chart(filtered: pd.DataFrame) -> go.Figure:
    counts = filtered["status"].value_counts().reindex(STATUS_ORDER).fillna(0).astype(int)
    counts = counts[counts > 0]
    fig = go.Figure(
        go.Bar(
            x=counts.values,
            y=[f"{STATUS_ICON[s]} {s}" for s in counts.index],
            orientation="h",
            marker_color=[STATUS_COLOR[s] for s in counts.index],
            text=counts.values,
            textposition="outside",
        )
    )
    fig.update_layout(
        height=280,
        margin=dict(l=0, r=20, t=10, b=10),
        xaxis_title=None,
        yaxis_title=None,
        showlegend=False,
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
    )
    fig.update_yaxes(autorange="reversed")
    return fig
