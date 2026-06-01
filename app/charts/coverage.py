from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from .theme import TOPIC_COLORS, apply_research_layout, empty_figure


def make_coverage_strip(coverage: pd.DataFrame | None = None, papers: pd.DataFrame | None = None) -> go.Figure:
    if papers is not None and not papers.empty:
        aggregations = {
            "paper_count": ("paper_id", "count"),
            "institution_coverage": ("institution_known", "mean"),
            "country_coverage": ("country_known", "mean"),
        }
        if "affiliation_confidence" in papers.columns:
            aggregations["affiliation_confidence"] = ("affiliation_confidence", "mean")
        data = papers.groupby("year", as_index=False).agg(**aggregations).sort_values("year")
        title = "Metadata coverage in current filters"
    elif coverage is not None and not coverage.empty and "institution_coverage" in coverage.columns:
        data = coverage.sort_values("year").copy()
        title = "Metadata coverage by year"
    else:
        return empty_figure("Metadata coverage by year", "No coverage data is available.", height=360)

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=data["year"],
            y=data["institution_coverage"] * 100,
            mode="lines+markers",
            name="Known institutions",
            line={"color": TOPIC_COLORS[0], "width": 3},
            marker={"size": 5, "color": TOPIC_COLORS[0]},
            hovertemplate="Year %{x}<br>Institution coverage %{y:.1f}%<extra></extra>",
        )
    )
    if "country_coverage" in data.columns:
        fig.add_trace(
            go.Scatter(
                x=data["year"],
                y=data["country_coverage"] * 100,
                mode="lines+markers",
                name="Known countries",
                line={"color": TOPIC_COLORS[1], "width": 2},
                marker={"size": 4, "color": TOPIC_COLORS[1]},
                hovertemplate="Year %{x}<br>Country coverage %{y:.1f}%<extra></extra>",
            )
        )
    if "affiliation_confidence" in data.columns:
        fig.add_trace(
            go.Scatter(
                x=data["year"],
                y=data["affiliation_confidence"] * 100,
                mode="lines",
                name="Avg affiliation confidence",
                line={"color": TOPIC_COLORS[2], "width": 2, "dash": "dot"},
                hovertemplate="Year %{x}<br>Avg confidence %{y:.1f}%<extra></extra>",
            )
        )
    fig.update_layout(
        title=title,
        yaxis={"range": [0, 100], "ticksuffix": "%"},
        legend_title_text="Coverage",
    )
    return apply_research_layout(fig, height=360)
