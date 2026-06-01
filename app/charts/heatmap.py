from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from .theme import PINK_SCALE, apply_research_layout, empty_figure


def make_topic_heatmap(papers: pd.DataFrame) -> go.Figure:
    if papers.empty:
        return empty_figure("Topic share by year", height=520)
    data = (
        papers.groupby(["topic_label", "year"], as_index=False)
        .agg(paper_count=("paper_id", "count"))
        .sort_values(["topic_label", "year"])
    )
    totals = data.groupby("year")["paper_count"].transform("sum")
    data["topic_share"] = data["paper_count"] / totals.replace(0, pd.NA) * 100
    topic_order = (
        data.groupby("topic_label")["paper_count"].sum().sort_values(ascending=True).index.tolist()
    )
    matrix = (
        data.pivot_table(index="topic_label", columns="year", values="topic_share", fill_value=0)
        .reindex(topic_order)
    )
    fig = go.Figure(
        data=go.Heatmap(
            x=matrix.columns.tolist(),
            y=matrix.index.tolist(),
            z=matrix.values,
            colorscale=PINK_SCALE,
            colorbar={"title": "Share", "ticksuffix": "%", "thickness": 12, "len": 0.72},
            hovertemplate="Year %{x}<br>%{y}<br>%{z:.1f}% of papers<extra></extra>",
        )
    )
    fig.update_layout(title="Topic share by year")
    fig.update_xaxes(title="Year", tickmode="linear", dtick=5)
    fig.update_yaxes(title="", automargin=True)
    fig = apply_research_layout(fig, height=520, legend=False)
    fig.update_layout(margin={"l": 245, "r": 58, "t": 58, "b": 54})
    return fig
