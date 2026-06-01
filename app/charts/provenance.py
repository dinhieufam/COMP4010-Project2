from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from .theme import TOPIC_COLORS, apply_research_layout, empty_figure


SOURCE_LABELS = {
    "pdf_text": "PDF text",
    "openalex_hash": "OpenAlex URL",
    "openalex_title": "OpenAlex title",
    "openalex_doi": "OpenAlex DOI",
    "openreview": "OpenReview",
    "none": "Unknown",
}


def make_affiliation_provenance(papers: pd.DataFrame) -> go.Figure:
    if papers.empty or "affiliation_source" not in papers.columns:
        return empty_figure("Affiliation provenance")
    data = (
        papers.assign(source=papers["affiliation_source"].fillna("none").map(lambda value: SOURCE_LABELS.get(value, str(value))))
        .groupby(["year", "source"], as_index=False)
        .agg(paper_count=("paper_id", "count"))
        .sort_values(["year", "source"])
    )
    if data.empty:
        return empty_figure("Affiliation provenance")
    fig = px.area(
        data,
        x="year",
        y="paper_count",
        color="source",
        title="Affiliation provenance over time",
        labels={"paper_count": "Papers", "source": "Source"},
        color_discrete_sequence=TOPIC_COLORS,
    )
    fig.update_traces(line={"width": 0.8}, hovertemplate="%{fullData.name}<br>%{x}<br>%{y:,} papers<extra></extra>")
    return apply_research_layout(fig, height=420)
