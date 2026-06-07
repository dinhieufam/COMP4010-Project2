from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from .theme import CORAL_SCALE, apply_research_layout, empty_figure

_CORAL = "#cc785c"


def make_topic_network(papers: pd.DataFrame, edges: pd.DataFrame) -> go.Figure:
    """Topic similarity matrix — colour-encoded adjacency heatmap.

    Replaces edge-thickness encoding: each cell shows the pairwise similarity
    weight between two topics. Diagonal = relative paper count (self-weight).
    Click a cell to filter by the y-axis topic.
    """
    if papers.empty:
        return empty_figure("Topic similarity matrix")

    topic_counts = papers.groupby("topic_label")["paper_id"].count().sort_values(ascending=False)
    topics = topic_counts.head(16).index.tolist()
    if not topics:
        return empty_figure("Topic similarity matrix")

    matrix = pd.DataFrame(0.0, index=topics, columns=topics)

    if edges is not None and not edges.empty:
        allowed = set(topics)
        filtered = edges[
            edges["source_topic_label"].isin(allowed) & edges["target_topic_label"].isin(allowed)
        ]
        for _, row in filtered.iterrows():
            src = row.get("source_topic_label")
            tgt = row.get("target_topic_label")
            w = float(row.get("weight", 0))
            matrix.loc[src, tgt] = w
            matrix.loc[tgt, src] = w

    # Diagonal encodes relative paper volume
    max_count = max(int(topic_counts.max()), 1)
    for t in topics:
        matrix.loc[t, t] = topic_counts.get(t, 0) / max_count

    # Raw counts for hover
    count_matrix = pd.DataFrame(0, index=topics, columns=topics)
    for t in topics:
        count_matrix.loc[t, t] = int(topic_counts.get(t, 0))

    fig = go.Figure(
        go.Heatmap(
            x=topics,
            y=list(reversed(topics)),
            z=matrix.reindex(index=list(reversed(topics))).values,
            colorscale=CORAL_SCALE,
            showscale=True,
            colorbar={
                "title": {"text": "Similarity", "side": "right"},
                "thickness": 12,
                "len": 0.8,
                "tickfont": {"size": 10},
            },
            hovertemplate=(
                "<b>%{y}</b> × <b>%{x}</b><br>"
                "Similarity weight: %{z:.3f}<br>"
                "<i>Click to filter by row topic</i><extra></extra>"
            ),
            xgap=1,
            ygap=1,
        )
    )
    fig.update_layout(
        title="Topic similarity · pairwise co-occurrence matrix",
        xaxis={"tickangle": -40, "tickfont": {"size": 9}, "side": "bottom"},
        yaxis={"tickfont": {"size": 9}},
        margin={"l": 160, "r": 20, "t": 52, "b": 120},
    )
    return apply_research_layout(fig, height=500, legend=False)


def make_topic_connections_ranked(
    papers: pd.DataFrame,
    edges: pd.DataFrame,
    selected_topic: str | None,
) -> go.Figure:
    """Ranked bar chart: other topics by co-occurrence strength with the selected topic.

    Shows which topics appear most alongside `selected_topic` in the same papers,
    ranked by edge weight descending. Click a bar to cross-filter to that topic.
    """
    if papers.empty or not selected_topic:
        return empty_figure("Topic Connections", "Select a topic above to see its connections.")

    if edges is None or edges.empty:
        return empty_figure("Topic Connections", "No co-occurrence data available.")

    mask = (
        edges["source_topic_label"].eq(selected_topic)
        | edges["target_topic_label"].eq(selected_topic)
    )
    relevant = edges[mask].copy()

    if relevant.empty:
        return empty_figure("Topic Connections", f"No co-occurrence data for '{selected_topic}'.")

    relevant["other_topic"] = relevant.apply(
        lambda r: r["target_topic_label"]
        if r["source_topic_label"] == selected_topic
        else r["source_topic_label"],
        axis=1,
    )

    result = (
        relevant[["other_topic", "weight"]]
        .sort_values("weight", ascending=True)
    )

    fig = go.Figure(
        go.Bar(
            x=result["weight"].tolist(),
            y=result["other_topic"].tolist(),
            orientation="h",
            marker_color=_CORAL,
            hovertemplate="%{y}<br>Co-occurrence weight: %{x:.3f}<extra></extra>",
        )
    )
    fig.update_layout(
        title=f"Topics most connected to · {selected_topic}",
        xaxis_title="Co-occurrence weight",
        margin={"l": 200, "r": 20, "t": 52, "b": 40},
    )
    return apply_research_layout(fig, height=420, legend=False)
