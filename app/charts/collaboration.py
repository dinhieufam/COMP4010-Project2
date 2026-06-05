from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from .theme import CORAL_SCALE, apply_research_layout, empty_figure
from .utils import country_display, explode_tokens


def make_collaboration_flow(papers: pd.DataFrame, top_n: int = 12) -> go.Figure:
    """Country-topic focus heatmap.

    Rows = top countries; columns = top topics.
    Colour = percentage of that country's papers in each topic (row-normalised),
    so each row answers "which topics does this country focus on?"
    """
    if papers.empty:
        return empty_figure("Country-topic focus")

    country_source = "countries_iso2_text" if "countries_iso2_text" in papers.columns else "countries_text"
    countries = explode_tokens(papers, country_source, "country")
    if countries.empty:
        return empty_figure("Country-topic focus", "No known country metadata in the current selection.")

    countries["country"] = countries["country"].apply(country_display)
    grouped = (
        countries.groupby(["country", "topic_label"], as_index=False)
        .agg(papers=("paper_id", "count"))
    )

    top_countries = (
        grouped.groupby("country")["papers"].sum()
        .sort_values(ascending=False).head(top_n).index
    )
    top_topics = (
        grouped.groupby("topic_label")["papers"].sum()
        .sort_values(ascending=False).head(top_n).index
    )
    grouped = grouped[grouped["country"].isin(top_countries) & grouped["topic_label"].isin(top_topics)]
    if grouped.empty:
        return empty_figure("Country-topic focus")

    matrix = grouped.pivot_table(index="country", columns="topic_label", values="papers", fill_value=0)
    # Row-normalise: % of each country's papers per topic
    row_totals = matrix.sum(axis=1).replace(0, 1)
    normalised = (matrix.div(row_totals, axis=0) * 100).round(1)

    # Order countries by total paper count (most papers at top)
    country_order = (
        grouped.groupby("country")["papers"].sum()
        .sort_values(ascending=True).index.tolist()
    )
    normalised = normalised.reindex([c for c in country_order if c in normalised.index])

    # Raw counts for hover
    raw = matrix.reindex(normalised.index)

    fig = go.Figure(
        go.Heatmap(
            x=normalised.columns.tolist(),
            y=normalised.index.tolist(),
            z=normalised.values,
            customdata=raw.values,
            colorscale=CORAL_SCALE,
            showscale=True,
            colorbar={
                "title": {"text": "% of country<br>papers", "side": "right"},
                "thickness": 12,
                "len": 0.8,
                "ticksuffix": "%",
                "tickfont": {"size": 10},
            },
            hovertemplate=(
                "<b>%{y}</b><br>"
                "Topic: %{x}<br>"
                "%{z:.1f}% of country papers<br>"
                "(%{customdata:,} papers)<extra></extra>"
            ),
            xgap=1,
            ygap=1,
        )
    )
    fig.update_layout(
        title="Country-topic focus · normalised topic share per country",
        xaxis={"tickangle": -40, "tickfont": {"size": 9}, "side": "bottom"},
        yaxis={"tickfont": {"size": 10}},
        margin={"l": 140, "r": 20, "t": 52, "b": 120},
    )
    return apply_research_layout(fig, height=460, legend=False)
