from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from .theme import TOPIC_COLORS, apply_research_layout, empty_figure


def topic_momentum_table(papers: pd.DataFrame, window: int = 3) -> pd.DataFrame:
    if papers.empty:
        return pd.DataFrame(columns=["topic_label", "early_share", "recent_share", "delta_pp", "recent_papers"])
    years = sorted(papers["year"].dropna().astype(int).unique())
    if len(years) < 2:
        return pd.DataFrame(columns=["topic_label", "early_share", "recent_share", "delta_pp", "recent_papers"])
    recent_years = years[-min(window, len(years)) :]
    early_years = years[: min(window, len(years))]
    recent = papers[papers["year"].isin(recent_years)]
    early = papers[papers["year"].isin(early_years)]
    recent_share = recent["topic_label"].value_counts(normalize=True).rename("recent_share")
    early_share = early["topic_label"].value_counts(normalize=True).rename("early_share")
    recent_count = recent["topic_label"].value_counts().rename("recent_papers")
    data = (
        pd.concat([early_share, recent_share, recent_count], axis=1)
        .fillna(0)
        .reset_index(names="topic_label")
    )
    data["delta_pp"] = (data["recent_share"] - data["early_share"]) * 100
    data["early_share"] *= 100
    data["recent_share"] *= 100
    return data.sort_values("delta_pp", ascending=False)


def make_topic_momentum(papers: pd.DataFrame) -> go.Figure:
    data = topic_momentum_table(papers)
    if data.empty:
        return empty_figure("Topic momentum", "Need at least two years of papers to compute momentum.")
    focus = pd.concat([data.head(6), data.tail(6)]).drop_duplicates("topic_label")
    focus = focus.sort_values("delta_pp")
    colors = [TOPIC_COLORS[0] if value >= 0 else TOPIC_COLORS[1] for value in focus["delta_pp"]]
    fig = go.Figure(
        go.Bar(
            x=focus["delta_pp"],
            y=focus["topic_label"],
            orientation="h",
            marker={"color": colors, "line": {"color": "rgba(169, 88, 62, 0.25)", "width": 0.8}},
            customdata=focus[["early_share", "recent_share", "recent_papers"]],
            hovertemplate=(
                "%{y}<br>"
                "Share change %{x:+.1f} pp<br>"
                "Early share %{customdata[0]:.1f}%<br>"
                "Recent share %{customdata[1]:.1f}%<br>"
                "Recent papers %{customdata[2]:,.0f}<extra></extra>"
            ),
        )
    )
    fig.add_vline(x=0, line={"color": "#e6dfd8", "width": 1.5})
    fig.update_layout(title="Topic momentum · recent vs early share", xaxis_title="Change in share, percentage points", yaxis_title="")
    return apply_research_layout(fig, height=430, legend=False)
