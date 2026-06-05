from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from .theme import TEAL_ROSE_SCALE, TOPIC_COLORS, apply_research_layout, empty_figure
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


def make_country_trend(papers: pd.DataFrame, top_n: int = 10) -> go.Figure:
    """Line chart: annual paper-participation count for the top-N countries.

    Each line is one country; x = year, y = papers that year.
    Thicker line + filled area below for the top country; plain lines for the rest.
    """
    if papers.empty:
        return empty_figure("Top countries per year")

    counts = country_counts_by_year(papers)
    if counts.empty:
        return empty_figure("Top countries per year", "No country metadata in the current selection.")

    # Identify top-N countries by total participations across all years
    totals = counts.groupby("country")["participations"].sum().sort_values(ascending=False)
    top_countries = totals.head(top_n).index.tolist()
    data = counts[counts["country"].isin(top_countries)].copy()
    if data.empty:
        return empty_figure("Top countries per year")

    # Ensure every country has an entry for every year (fill 0 for gaps)
    all_years = sorted(data["year"].unique())
    rows = []
    for country in top_countries:
        iso3 = data[data["country"] == country]["country_iso3"].iloc[0] if not data[data["country"] == country].empty else ""
        cdf = data[data["country"] == country].set_index("year")["participations"]
        for y in all_years:
            rows.append({"year": y, "country": country, "country_iso3": iso3, "participations": int(cdf.get(y, 0))})
    plot_df = pd.DataFrame(rows)

    def _hex_to_rgba(hex_color: str, alpha: float) -> str:
        h = hex_color.lstrip("#")
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        return f"rgba({r},{g},{b},{alpha})"

    fig = go.Figure()
    for i, country in enumerate(top_countries):
        cdf = plot_df[plot_df["country"] == country].sort_values("year")
        color = TOPIC_COLORS[i % len(TOPIC_COLORS)]
        is_top = i == 0
        fig.add_trace(go.Scatter(
            x=cdf["year"],
            y=cdf["participations"],
            name=country,
            mode="lines",
            line={"color": color, "width": 2.5 if is_top else 1.8},
            fill="tozeroy" if is_top else "none",
            fillcolor=_hex_to_rgba(color, 0.08) if is_top else None,
            hovertemplate=f"<b>{country}</b><br>Year: %{{x}}<br>Papers: %{{y:,}}<extra></extra>",
        ))

    fig.update_layout(
        title=f"Top {top_n} countries · annual paper participations",
        xaxis={"title": "Year", "tickangle": 0},
        yaxis={"title": "Paper participations"},
        legend={
            "orientation": "v",
            "x": 1.01,
            "y": 1,
            "xanchor": "left",
            "font": {"size": 10},
        },
        margin={"l": 60, "r": 140, "t": 52, "b": 48},
    )
    return apply_research_layout(fig, height=420)


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
            marker={"line": {"color": "#e6dfd8", "width": 0.35}},
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
            "landcolor": "#f5f0e8",
            "showocean": True,
            "oceancolor": "#d4e8e6",
            "showcountries": True,
            "countrycolor": "#e6dfd8",
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
