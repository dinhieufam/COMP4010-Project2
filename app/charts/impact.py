from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from .theme import TOPIC_COLORS, apply_research_layout


def focus_topics(papers: pd.DataFrame, max_topics: int = 7) -> pd.DataFrame:
    counts = papers.groupby("topic_label")["paper_id"].count().sort_values(ascending=False)
    if len(counts) <= max_topics:
        return papers.copy()
    keep = set(counts.head(max_topics - 1).index)
    data = papers.copy()
    data["topic_label"] = data["topic_label"].where(data["topic_label"].isin(keep), "Other topics")
    return data


def make_citation_impact(papers: pd.DataFrame) -> go.Figure:
    if papers.empty:
        return apply_research_layout(go.Figure().update_layout(title="Age-normalized citation impact"))
    latest_year = max(int(papers["year"].max()), 2026)
    data = focus_topics(papers)
    data["normalized_impact"] = data["citation_count"] / data["year"].apply(lambda year: max(1, latest_year - int(year) + 1))
    impact = (
        data.groupby(["year", "topic_label"], as_index=False)
        .agg(normalized_impact=("normalized_impact", "mean"), paper_count=("paper_id", "count"))
        .sort_values("year")
    )
    fig = px.line(
        impact,
        x="year",
        y="normalized_impact",
        color="topic_label",
        markers=True,
        title="Age-normalized citation impact",
        labels={"normalized_impact": "Citations per paper-year", "topic_label": "Topic"},
        color_discrete_sequence=TOPIC_COLORS,
    )
    fig.update_traces(line={"width": 2}, marker={"size": 4})
    return apply_research_layout(fig, height=420)
