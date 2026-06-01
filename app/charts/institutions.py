from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from .theme import TOPIC_COLORS, apply_research_layout, empty_figure
from .utils import explode_tokens


def make_institution_leaderboard(papers: pd.DataFrame) -> go.Figure:
    if papers.empty:
        return empty_figure("Institution participation leaderboard")
    data = explode_tokens(papers, "institutions_text", "institution")
    if data.empty:
        return empty_figure("Institution participation leaderboard", "No known institution metadata in the current selection.")
    grouped = (
        data.groupby("institution", as_index=False)
        .agg(participations=("paper_id", "count"))
        .sort_values("participations", ascending=False)
        .head(12)
    )
    fig = px.bar(
        grouped.sort_values("participations"),
        x="participations",
        y="institution",
        orientation="h",
        title="Institution participation leaderboard",
        labels={"participations": "Institution-paper participations", "institution": "Institution"},
        color_discrete_sequence=[TOPIC_COLORS[0]],
    )
    fig.update_traces(marker={"color": TOPIC_COLORS[0], "line": {"color": "#a82255", "width": 0.5}})
    return apply_research_layout(fig, height=420, legend=False)
