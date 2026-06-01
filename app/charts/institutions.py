from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from .theme import TOPIC_COLORS, apply_research_layout


def make_institution_leaderboard(papers: pd.DataFrame, metric: str = "output") -> go.Figure:
    if papers.empty:
        return apply_research_layout(go.Figure().update_layout(title="Institution leaderboard"), legend=False)
    data = papers.assign(institution=papers["institutions_text"].str.split(", ")).explode("institution")
    data["institution"] = data["institution"].fillna("Unknown")
    grouped = (
        data.groupby("institution", as_index=False)
        .agg(paper_count=("paper_id", "count"), citation_count=("citation_count", "sum"))
        .sort_values("paper_count" if metric == "output" else "citation_count", ascending=False)
        .head(12)
    )
    y_value = "paper_count" if metric == "output" else "citation_count"
    title = "Institution output leaderboard" if metric == "output" else "Institution citation leaderboard"
    fig = px.bar(
        grouped.sort_values(y_value),
        x=y_value,
        y="institution",
        orientation="h",
        title=title,
        labels={y_value: "Papers" if metric == "output" else "Citations", "institution": "Institution"},
        color_discrete_sequence=[TOPIC_COLORS[0]],
    )
    fig.update_traces(marker={"color": TOPIC_COLORS[0], "line": {"color": "#8f174f", "width": 0.5}})
    return apply_research_layout(fig, height=420, legend=False)
