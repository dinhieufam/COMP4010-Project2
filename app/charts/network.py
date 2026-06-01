from __future__ import annotations

import math

import networkx as nx
import pandas as pd
import plotly.graph_objects as go

from .theme import TOPIC_COLORS, apply_research_layout, empty_figure


def make_topic_network(papers: pd.DataFrame, edges: pd.DataFrame) -> go.Figure:
    if papers.empty:
        return empty_figure("Topic similarity network")
    topic_counts = papers.groupby("topic_label", as_index=False).agg(paper_count=("paper_id", "count"))
    graph = nx.Graph()
    for row in topic_counts.to_dict("records"):
        graph.add_node(row["topic_label"], paper_count=int(row["paper_count"]))
    if edges is not None and not edges.empty:
        allowed = set(topic_counts["topic_label"])
        filtered_edges = edges[
            edges["source_topic_label"].isin(allowed) & edges["target_topic_label"].isin(allowed)
        ].sort_values("weight", ascending=False).head(40)
        for row in filtered_edges.to_dict("records"):
            source = row.get("source_topic_label")
            target = row.get("target_topic_label")
            graph.add_edge(source, target, weight=float(row.get("weight", 0.1)))
    if graph.number_of_edges() == 0 and graph.number_of_nodes() > 1:
        nodes = list(graph.nodes)
        for idx in range(len(nodes) - 1):
            graph.add_edge(nodes[idx], nodes[idx + 1], weight=0.1)

    pos = nx.spring_layout(graph, seed=42, k=0.8, iterations=120, weight="weight")
    edge_traces = []
    for source, target in graph.edges():
        x0, y0 = pos[source]
        x1, y1 = pos[target]
        weight = float(graph[source][target].get("weight", 0.1))
        edge_traces.append(
            go.Scatter(
                x=[x0, x1],
                y=[y0, y1],
                mode="lines",
                line={"width": 0.8 + 4 * weight, "color": "rgba(216, 137, 164, 0.48)"},
                hoverinfo="skip",
                showlegend=False,
            )
        )

    node_x = []
    node_y = []
    sizes = []
    labels = []
    max_count = max((attrs.get("paper_count", 1) for _, attrs in graph.nodes(data=True)), default=1)
    for node, attrs in graph.nodes(data=True):
        x, y = pos[node]
        node_x.append(x)
        node_y.append(y)
        count = attrs.get("paper_count", 1)
        sizes.append(12 + 34 * math.sqrt(count / max(max_count, 1)))
        labels.append(f"{node}<br>{count} papers")

    fig = go.Figure()
    for trace in edge_traces:
        fig.add_trace(trace)
    fig.add_trace(
        go.Scatter(
            x=node_x,
            y=node_y,
            mode="markers+text",
            text=list(graph.nodes),
            hovertext=labels,
            hoverinfo="text",
            textposition="top center",
            marker={"size": sizes, "color": TOPIC_COLORS[: len(node_x)], "opacity": 0.88, "line": {"color": "#ffffff", "width": 1}},
            textfont={"size": 10, "color": "#3b303b"},
        )
    )
    fig.update_layout(
        title="Topic similarity network · filtered topic co-structure",
        showlegend=False,
        xaxis={"visible": False},
        yaxis={"visible": False},
    )
    return apply_research_layout(fig, height=420, legend=False)
