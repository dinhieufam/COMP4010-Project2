from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from .theme import TOPIC_COLORS, apply_research_layout, empty_figure


def hex_rgba(hex_color: str, alpha: float) -> str:
    color = hex_color.lstrip("#")
    red, green, blue = (int(color[idx : idx + 2], 16) for idx in (0, 2, 4))
    return f"rgba({red},{green},{blue},{alpha})"


def make_forecast_focus(papers: pd.DataFrame, forecast: pd.DataFrame | None) -> go.Figure:
    if papers.empty:
        return empty_figure("Forecast focus")
    if forecast is None or forecast.empty:
        return empty_figure("Forecast focus", "No forecast output is available.")

    observed = (
        papers.groupby(["year", "topic_label"], as_index=False)
        .agg(paper_count=("paper_id", "count"))
        .sort_values(["topic_label", "year"])
    )
    if observed.empty:
        return empty_figure("Forecast focus")

    focus_topics = observed.groupby("topic_label")["paper_count"].sum().sort_values(ascending=False).head(5).index.tolist()
    fig = go.Figure()
    for idx, topic in enumerate(focus_topics):
        color = TOPIC_COLORS[idx % len(TOPIC_COLORS)]
        obs = observed[observed["topic_label"].eq(topic)]
        pred = forecast[forecast["topic_label"].eq(topic)].sort_values("year")
        fig.add_trace(
            go.Scatter(
                x=obs["year"],
                y=obs["paper_count"],
                mode="lines",
                name=topic,
                line={"color": color, "width": 2.4},
                hovertemplate=f"{topic}<br>%{{x}}<br>%{{y:,.0f}} observed papers<extra></extra>",
            )
        )
        if pred.empty:
            continue
        lower = pred["lower"].clip(lower=0) if "lower" in pred.columns else pred["forecast_count"].clip(lower=0)
        upper = pred["upper"].clip(lower=0) if "upper" in pred.columns else pred["forecast_count"].clip(lower=0)
        fig.add_trace(
            go.Scatter(
                x=pd.concat([pred["year"], pred["year"][::-1]]),
                y=pd.concat([upper, lower[::-1]]),
                fill="toself",
                fillcolor=hex_rgba(color, 0.12),
                line={"color": "rgba(0,0,0,0)"},
                name=f"{topic} interval",
                hoverinfo="skip",
                showlegend=False,
            )
        )
        fig.add_trace(
            go.Scatter(
                x=pred["year"],
                y=pred["forecast_count"],
                mode="lines+markers",
                name=f"{topic} forecast",
                line={"color": color, "width": 2, "dash": "dot"},
                marker={"size": 5},
                showlegend=False,
                hovertemplate=f"{topic}<br>%{{x}}<br>%{{y:,.0f}} forecast papers<extra></extra>",
            )
        )

    fig.update_layout(title="Forecast focus · leading topics", yaxis_title="Papers", xaxis_title="Year")
    return apply_research_layout(fig, height=440)
