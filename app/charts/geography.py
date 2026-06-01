from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from .theme import TEAL_ROSE_SCALE, apply_research_layout


COUNTRY_CODES = {
    "US": "United States",
    "GB": "United Kingdom",
    "UK": "United Kingdom",
    "CA": "Canada",
    "CN": "China",
    "DE": "Germany",
    "FR": "France",
    "JP": "Japan",
    "KR": "South Korea",
    "SG": "Singapore",
    "CH": "Switzerland",
    "NL": "Netherlands",
}


def country_name(value: str) -> str:
    value = str(value)
    return COUNTRY_CODES.get(value.upper(), value)


def make_country_map(papers: pd.DataFrame) -> go.Figure:
    if papers.empty:
        return apply_research_layout(go.Figure().update_layout(title="Geographic distribution"), legend=False)
    data = papers.assign(country=papers["countries_text"].str.split(", ")).explode("country")
    data["country"] = data["country"].fillna("Unknown").apply(country_name)
    data = data[data["country"].ne("Unknown")]
    if data.empty:
        return apply_research_layout(go.Figure().update_layout(title="Geographic distribution"), legend=False)
    country_counts = data.groupby("country", as_index=False).agg(paper_count=("paper_id", "count"))
    fig = px.choropleth(
        country_counts,
        locations="country",
        locationmode="country names",
        color="paper_count",
        hover_name="country",
        title="Geographic distribution",
        labels={"paper_count": "Papers"},
        color_continuous_scale=TEAL_ROSE_SCALE,
    )
    fig.update_geos(
        bgcolor="rgba(0,0,0,0)",
        showframe=False,
        showcoastlines=False,
        landcolor="#fffafd",
        countrycolor="#ead4df",
    )
    fig.update_layout(coloraxis_colorbar={"title": "Papers", "thickness": 12, "len": 0.72})
    return apply_research_layout(fig, height=420, legend=False)
