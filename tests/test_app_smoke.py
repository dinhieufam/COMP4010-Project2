from __future__ import annotations

import plotly.graph_objects as go

from app.charts.geography import make_country_map
from app.charts.heatmap import make_topic_heatmap
from app.charts.impact import make_citation_impact
from app.charts.institutions import make_institution_leaderboard
from app.charts.network import make_topic_network
from app.charts.streamgraph import make_topic_growth
from pipeline.sample_data import processed_frames


def test_chart_builders_return_plotly_figures():
    frames = processed_frames()
    papers = frames["papers"]
    assert isinstance(make_topic_growth(papers, frames["forecast"]), go.Figure)
    assert isinstance(make_citation_impact(papers), go.Figure)
    assert isinstance(make_country_map(papers), go.Figure)
    assert isinstance(make_institution_leaderboard(papers), go.Figure)
    assert isinstance(make_topic_heatmap(papers), go.Figure)
    assert isinstance(make_topic_network(papers, frames["topic_edges"]), go.Figure)


def test_app_imports():
    from app.app import app

    assert app is not None

