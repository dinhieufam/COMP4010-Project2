from __future__ import annotations

import plotly.graph_objects as go

from app.charts.geography import make_country_map
from app.charts.heatmap import make_topic_heatmap
from app.charts.institutions import make_institution_leaderboard
from app.charts.network import make_topic_network
from app.charts.streamgraph import make_topic_growth
from app.charts.coverage import make_coverage_strip
from app.charts.collaboration import make_collaboration_flow
from app.charts.creative import (
    make_institution_country_orbit,
    make_metadata_weather,
    make_paper_universe,
    make_research_bloom,
    make_research_river,
    make_topic_dna,
    make_topic_galaxy,
    make_topic_race,
)
from app.charts.forecast import make_forecast_focus
from app.charts.momentum import make_topic_momentum
from app.charts.provenance import make_affiliation_provenance
from pipeline.sample_data import processed_frames


def test_chart_builders_return_plotly_figures():
    frames = processed_frames()
    papers = frames["papers"]
    assert isinstance(make_topic_growth(papers, frames["forecast"]), go.Figure)
    assert isinstance(make_country_map(papers), go.Figure)
    assert isinstance(make_institution_leaderboard(papers), go.Figure)
    assert isinstance(make_coverage_strip(frames["coverage"]), go.Figure)
    assert isinstance(make_topic_heatmap(papers), go.Figure)
    assert isinstance(make_topic_network(papers, frames["topic_edges"]), go.Figure)
    assert isinstance(make_forecast_focus(papers, frames["forecast"]), go.Figure)
    assert isinstance(make_topic_momentum(papers), go.Figure)
    assert isinstance(make_affiliation_provenance(papers), go.Figure)
    assert isinstance(make_collaboration_flow(papers), go.Figure)
    assert isinstance(make_coverage_strip(frames["coverage"], papers), go.Figure)
    assert isinstance(make_topic_galaxy(papers), go.Figure)
    assert isinstance(make_research_river(papers), go.Figure)
    assert isinstance(make_topic_race(papers), go.Figure)
    assert isinstance(make_research_bloom(papers), go.Figure)
    assert isinstance(make_institution_country_orbit(papers), go.Figure)
    assert isinstance(make_metadata_weather(papers), go.Figure)
    assert isinstance(make_paper_universe(papers), go.Figure)
    assert isinstance(make_topic_dna(papers), go.Figure)


def test_chart_builders_handle_empty_filters():
    frames = processed_frames()
    papers = frames["papers"].iloc[0:0]
    assert isinstance(make_topic_growth(papers, frames["forecast"]), go.Figure)
    assert isinstance(make_country_map(papers), go.Figure)
    assert isinstance(make_institution_leaderboard(papers), go.Figure)
    assert isinstance(make_topic_heatmap(papers), go.Figure)
    assert isinstance(make_topic_network(papers, frames["topic_edges"]), go.Figure)
    assert isinstance(make_forecast_focus(papers, frames["forecast"]), go.Figure)
    assert isinstance(make_topic_momentum(papers), go.Figure)
    assert isinstance(make_affiliation_provenance(papers), go.Figure)
    assert isinstance(make_collaboration_flow(papers), go.Figure)
    assert isinstance(make_topic_galaxy(papers), go.Figure)
    assert isinstance(make_research_river(papers), go.Figure)
    assert isinstance(make_topic_race(papers), go.Figure)
    assert isinstance(make_research_bloom(papers), go.Figure)
    assert isinstance(make_institution_country_orbit(papers), go.Figure)
    assert isinstance(make_metadata_weather(papers), go.Figure)
    assert isinstance(make_paper_universe(papers), go.Figure)
    assert isinstance(make_topic_dna(papers), go.Figure)


def test_app_imports():
    from app.app import app

    assert app is not None
