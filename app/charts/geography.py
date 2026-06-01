from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from .theme import TEAL_ROSE_SCALE, apply_research_layout, empty_figure
from .utils import country_display, country_iso3, explode_tokens


def country_counts_by_year(papers: pd.DataFrame) -> pd.DataFrame:
    source_column = "countries_iso2_text" if "countries_iso2_text" in papers.columns else "countries_text"
    data = explode_tokens(papers, source_column, "country")
    if data.empty:
        return pd.DataFrame(columns=["year", "country_iso3", "country", "participations"])
    data["country_iso3"] = data["country"].apply(country_iso3)
    data = data.dropna(subset=["country_iso3"])
    data["country"] = data["country_iso3"].apply(country_display)
    if data.empty:
        return pd.DataFrame(columns=["year", "country_iso3", "country", "participations"])
    return data.groupby(["year", "country_iso3", "country"], as_index=False).agg(participations=("paper_id", "count"))


def make_country_map(papers: pd.DataFrame) -> go.Figure:
    if papers.empty:
        return empty_figure("Global research footprint")

    counts = country_counts_by_year(papers)
    if counts.empty:
        return empty_figure("Global research footprint", "No known country metadata in the current selection.")

    cumulative = []
    for year in sorted(counts["year"].unique()):
        year_counts = (
            counts[counts["year"].le(year)]
            .groupby(["country_iso3", "country"], as_index=False)
            .agg(participations=("participations", "sum"))
        )
        year_counts["frame_year"] = year
        cumulative.append(year_counts)
    globe = pd.concat(cumulative, ignore_index=True)
    first_year = int(globe["frame_year"].min())
    first = globe[globe["frame_year"].eq(first_year)]

    def trace_for(frame: pd.DataFrame) -> go.Choropleth:
        return go.Choropleth(
            locations=frame["country_iso3"],
            locationmode="ISO-3",
            z=frame["participations"],
            text=frame["country"],
            colorscale=TEAL_ROSE_SCALE,
            colorbar={"title": "Participations", "thickness": 12, "len": 0.68},
            marker={"line": {"color": "#f7c6d3", "width": 0.35}},
            hovertemplate="%{text}<br>%{z:,} cumulative country-paper participations<extra></extra>",
        )

    frames = [
        go.Frame(data=[trace_for(globe[globe["frame_year"].eq(year)])], name=str(year))
        for year in sorted(globe["frame_year"].unique())
    ]
    fig = go.Figure(data=[trace_for(first)], frames=frames)
    fig.update_layout(
        title="Global research footprint · country-paper participations",
        geo={
            "projection": {"type": "orthographic", "rotation": {"lon": -35, "lat": 22}},
            "showland": True,
            "landcolor": "#fff8fa",
            "showocean": True,
            "oceancolor": "#f8d8e1",
            "showcountries": True,
            "countrycolor": "#e9a9bb",
            "showcoastlines": False,
            "bgcolor": "rgba(0,0,0,0)",
        },
        updatemenus=[
            {
                "type": "buttons",
                "direction": "left",
                "x": 0,
                "y": -0.08,
                "buttons": [
                    {
                        "label": "Play",
                        "method": "animate",
                        "args": [None, {"frame": {"duration": 180, "redraw": True}, "fromcurrent": True}],
                    },
                    {
                        "label": "Pause",
                        "method": "animate",
                        "args": [[None], {"frame": {"duration": 0, "redraw": False}, "mode": "immediate"}],
                    },
                ],
            }
        ],
        sliders=[
            {
                "active": 0,
                "x": 0.15,
                "y": -0.08,
                "len": 0.78,
                "currentvalue": {"prefix": "Year "},
                "steps": [
                    {
                        "label": str(year),
                        "method": "animate",
                        "args": [[str(year)], {"frame": {"duration": 0, "redraw": True}, "mode": "immediate"}],
                    }
                    for year in sorted(globe["frame_year"].unique())
                ],
            }
        ],
    )
    return apply_research_layout(fig, height=480, legend=False)
