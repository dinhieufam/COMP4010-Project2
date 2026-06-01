from __future__ import annotations

import networkx as nx
import pandas as pd
import plotly.graph_objects as go

from .theme import TOPIC_COLORS, apply_research_layout


def make_topic_network(papers: pd.DataFrame, edges: pd.DataFrame) -> go.Figure:
    if papers.empty:
        return apply_research_layout(go.Figure().update_layout(title="Topic similarity network"), legend=False)
    topic_counts = papers.groupby("topic_label", as_index=False).agg(paper_count=("paper_id", "count"))
    graph = nx.Graph()
    for row in topic_counts.to_dict("records"):
        graph.add_node(row["topic_label"], paper_count=int(row["paper_count"]))
    if edges is not None and not edges.empty:
        allowed = set(topic_counts["topic_label"])
        for row in edges.to_dict("records"):
            source = row.get("source_topic_label")
            target = row.get("target_topic_label")
            if source in allowed and target in allowed:
                graph.add_edge(source, target, weight=float(row.get("weight", 0.1)))
    if graph.number_of_edges() == 0 and graph.number_of_nodes() > 1:
        nodes = list(graph.nodes)
        for idx in range(len(nodes) - 1):
            graph.add_edge(nodes[idx], nodes[idx + 1], weight=0.1)

    pos = nx.spring_layout(graph, seed=42)
    edge_x: list[float | None] = []
    edge_y: list[float | None] = []
    for source, target in graph.edges():
        x0, y0 = pos[source]
        x1, y1 = pos[target]
        edge_x += [x0, x1, None]
        edge_y += [y0, y1, None]

    node_x = []
    node_y = []
    sizes = []
    labels = []
    for node, attrs in graph.nodes(data=True):
        x, y = pos[node]
        node_x.append(x)
        node_y.append(y)
        count = attrs.get("paper_count", 1)
        sizes.append(16 + count * 2)
        labels.append(f"{node}<br>{count} papers")

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=edge_x, y=edge_y, mode="lines", line={"width": 1, "color": "#e7bfd1"}, hoverinfo="skip"))
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
        title="Topic similarity network",
        showlegend=False,
        xaxis={"visible": False},
        yaxis={"visible": False},
    )
    return apply_research_layout(fig, height=420, legend=False)
