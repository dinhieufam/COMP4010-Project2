from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from .theme import TOPIC_COLORS, apply_research_layout, empty_figure
from .utils import country_display, explode_tokens


def make_collaboration_flow(papers: pd.DataFrame, top_n: int = 8) -> go.Figure:
    if papers.empty:
        return empty_figure("Country-topic exposure flow")
    country_source = "countries_iso2_text" if "countries_iso2_text" in papers.columns else "countries_text"
    countries = explode_tokens(papers, country_source, "country")
    if countries.empty:
        return empty_figure("Country-topic exposure flow", "No known country metadata in the current selection.")
    countries["country"] = countries["country"].apply(country_display)
    grouped = (
        countries.groupby(["country", "topic_label"], as_index=False)
        .agg(participations=("paper_id", "count"))
        .sort_values("participations", ascending=False)
    )
    top_countries = grouped.groupby("country")["participations"].sum().sort_values(ascending=False).head(top_n).index
    top_topics = grouped.groupby("topic_label")["participations"].sum().sort_values(ascending=False).head(top_n).index
    grouped = grouped[grouped["country"].isin(top_countries) & grouped["topic_label"].isin(top_topics)]
    grouped = grouped.sort_values("participations", ascending=False).head(36)
    if grouped.empty:
        return empty_figure("Country-topic exposure flow")

    country_nodes = grouped["country"].drop_duplicates().tolist()
    topic_nodes = grouped["topic_label"].drop_duplicates().tolist()
    labels = country_nodes + topic_nodes
    index = {label: idx for idx, label in enumerate(labels)}
    source = grouped["country"].map(index).tolist()
    target = grouped["topic_label"].map(index).tolist()
    values = grouped["participations"].tolist()
    node_colors = [TOPIC_COLORS[1]] * len(country_nodes) + [TOPIC_COLORS[i % len(TOPIC_COLORS)] for i in range(len(topic_nodes))]
    fig = go.Figure(
        go.Sankey(
            arrangement="snap",
            node={
                "pad": 14,
                "thickness": 13,
                "line": {"color": "rgba(122, 70, 91, 0.25)", "width": 0.7},
                "label": labels,
                "color": node_colors,
            },
            link={
                "source": source,
                "target": target,
                "value": values,
                "color": "rgba(217, 79, 131, 0.22)",
                "hovertemplate": "%{source.label} → %{target.label}<br>%{value:,} country-topic participations<extra></extra>",
            },
        )
    )
    fig.update_layout(title="Country-topic exposure flow · participations")
    return apply_research_layout(fig, height=450, legend=False)
