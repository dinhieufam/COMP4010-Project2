from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from .annotations import add_era_bands, add_event_markers
from .theme import apply_research_layout

_CORAL = "#cc785c"


def make_papers_per_year(papers: pd.DataFrame) -> go.Figure:
    counts = (
        papers.groupby("year", as_index=False)
        .size()
        .rename(columns={"size": "papers"})
        .sort_values("year")
    )

    fig = go.Figure(
        go.Scatter(
            x=counts["year"],
            y=counts["papers"],
            mode="lines",
            fill="tozeroy",
            fillcolor="rgba(204,120,92,0.12)",
            line=dict(color=_CORAL, width=2.4),
            hovertemplate="%{x}<br><b>%{y:,}</b> papers accepted<extra></extra>",
            name="Papers",
        )
    )

    apply_research_layout(fig, height=480, legend=False)
    add_era_bands(fig)
    add_event_markers(fig)

    if not counts.empty:
        peak_year = int(counts.loc[counts["papers"].idxmax(), "year"])
        peak_val  = int(counts["papers"].max())
        fig.add_annotation(
            x=peak_year,
            y=peak_val,
            text=f"{peak_val:,}",
            showarrow=True,
            arrowhead=2,
            arrowcolor=_CORAL,
            ax=0,
            ay=-40,
            font=dict(color=_CORAL, size=12, family="Cormorant Garamond, serif"),
        )

    fig.update_layout(
        title="NeurIPS papers per year · 1987–2025",
        xaxis_title="Year",
        yaxis_title="Papers accepted",
    )
    return fig
