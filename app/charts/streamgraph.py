from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from .theme import TOPIC_COLORS, apply_research_layout


def focus_topics(papers: pd.DataFrame, max_topics: int = 8) -> pd.DataFrame:
    counts = papers.groupby("topic_label")["paper_id"].count().sort_values(ascending=False)
    if len(counts) <= max_topics:
        return papers.copy()
    keep = set(counts.head(max_topics - 1).index)
    data = papers.copy()
    data["topic_label"] = data["topic_label"].where(data["topic_label"].isin(keep), "Other topics")
    return data


def make_topic_growth(papers: pd.DataFrame, forecast: pd.DataFrame | None = None) -> go.Figure:
    if papers.empty:
        return apply_research_layout(go.Figure().update_layout(title="Topic growth over time"), height=520)
    papers = focus_topics(papers)
    data = (
        papers.groupby(["year", "topic_label"], as_index=False)
        .agg(paper_count=("paper_id", "count"))
        .sort_values("year")
    )
    fig = px.area(
        data,
        x="year",
        y="paper_count",
        color="topic_label",
        title="Topic growth over time",
        labels={"paper_count": "Papers", "topic_label": "Topic"},
        color_discrete_sequence=TOPIC_COLORS,
    )
    if forecast is not None and not forecast.empty and data["topic_label"].nunique() <= 3:
        for topic in data["topic_label"].unique()[:6]:
            forecast_topic = forecast[forecast["topic_label"].eq(topic)]
            if not forecast_topic.empty:
                fig.add_trace(
                    go.Scatter(
                        x=forecast_topic["year"],
                        y=forecast_topic["forecast_count"],
                        mode="lines",
                        name=f"{topic} forecast",
                        line={"dash": "dot", "width": 2, "color": "#8f174f"},
                        showlegend=False,
                    )
                )
    fig.update_traces(line={"width": 0.6})
    fig.update_layout(legend_title_text="Topic")
    return apply_research_layout(fig, height=520)
