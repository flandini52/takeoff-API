"""Shared horizontal bar chart — used for both "% completamento per
operaio" (Manutenzioni) and "distribuzione per stato" (Scadenze dipendenti);
each page computes its own data/colors and passes them in."""

from typing import Any, Optional, Sequence

import plotly.graph_objects as go


def horizontal_bar_chart(
    labels: Sequence[str],
    values: Sequence[float],
    colors: Sequence[str],
    text: Optional[Sequence[Any]] = None,
    x_title: Optional[str] = None,
    height: Optional[int] = None,
    x_range: Optional[Sequence[float]] = None,
    reversed_yaxis: bool = False,
) -> go.Figure:
    fig = go.Figure(
        go.Bar(
            x=list(values),
            y=list(labels),
            orientation="h",
            marker_color=list(colors),
            text=list(text) if text is not None else None,
            textposition="outside",
        )
    )
    fig.update_layout(
        height=height or max(220, 40 * len(labels)),
        margin=dict(l=0, r=80, t=10, b=10),
        xaxis_title=x_title,
        yaxis_title=None,
        xaxis_range=list(x_range) if x_range is not None else None,
        showlegend=False,
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
    )
    if reversed_yaxis:
        fig.update_yaxes(autorange="reversed")
    return fig
