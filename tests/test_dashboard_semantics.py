from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from app.charts.creative import metadata_weather_table, paper_universe_points, topic_dna_table, topic_rank_table
from app.charts.geography import country_counts_by_year, make_country_map
from app.charts.network import make_topic_network
from app.charts.utils import country_iso3, explode_tokens


def test_country_conversion_supports_iso2_and_names():
    assert country_iso3("US") == "USA"
    assert country_iso3("United States") == "USA"
    assert country_iso3("GB") == "GBR"
    assert country_iso3("Unknown") is None


def test_country_counts_use_participation_semantics():
    papers = pd.DataFrame(
        {
            "paper_id": ["p1", "p2"],
            "year": [2024, 2024],
            "countries_text": ["US, GB", "Unknown"],
            "countries_iso2_text": ["US, GB", "Unknown"],
        }
    )
    counts = country_counts_by_year(papers)
    assert counts["participations"].sum() == 2
    assert set(counts["country_iso3"]) == {"USA", "GBR"}
    assert isinstance(make_country_map(papers), go.Figure)


def test_exploded_participations_can_exceed_unique_papers_by_design():
    papers = pd.DataFrame({"paper_id": ["p1", "p2"], "institutions_text": ["A, B, C", "D"]})
    exploded = explode_tokens(papers, "institutions_text", "institution")
    assert len(exploded) == 4
    assert exploded["paper_id"].nunique() == 2


def test_topic_network_filters_edge_candidates_before_top_selection():
    papers = pd.DataFrame(
        {
            "paper_id": ["p1", "p2"],
            "topic_label": ["Visible A", "Visible B"],
        }
    )
    edges = pd.DataFrame(
        {
            "source_topic_label": ["Hidden A", "Visible A"],
            "target_topic_label": ["Hidden B", "Visible B"],
            "weight": [99.0, 0.3],
        }
    )
    fig = make_topic_network(papers, edges)
    assert isinstance(fig, go.Figure)
    edge_traces = [trace for trace in fig.data if getattr(trace, "mode", "") == "lines"]
    assert len(edge_traces) == 1


def test_topic_race_ranks_are_computed_per_year():
    papers = pd.DataFrame(
        {
            "paper_id": [f"p{i}" for i in range(6)],
            "year": [2024, 2024, 2024, 2025, 2025, 2025],
            "topic_label": ["A", "A", "B", "B", "B", "A"],
        }
    )
    ranks = topic_rank_table(papers, top_n=2)
    assert ranks[ranks["year"].eq(2024)].sort_values("rank").iloc[0]["topic_label"] == "A"
    assert ranks[ranks["year"].eq(2025)].sort_values("rank").iloc[0]["topic_label"] == "B"


def test_topic_dna_yearly_shares_sum_to_one():
    papers = pd.DataFrame(
        {
            "paper_id": [f"p{i}" for i in range(8)],
            "year": [2024] * 4 + [2025] * 4,
            "topic_label": ["A", "A", "B", "C", "A", "B", "B", "C"],
        }
    )
    dna = topic_dna_table(papers, top_n=2)
    totals = dna.groupby("year")["topic_share"].sum()
    assert totals.sub(1).abs().lt(1e-9).all()


def test_paper_universe_caps_points_and_returns_numeric_coordinates():
    papers = pd.DataFrame(
        {
            "paper_id": [f"p{i}" for i in range(25)],
            "year": [2025] * 25,
            "title": [f"paper about topic {i % 3}" for i in range(25)],
            "authors_text": ["Author"] * 25,
            "topic_label": [f"Topic {i % 3}" for i in range(25)],
        }
    )
    points = paper_universe_points(papers, max_points=10)
    assert len(points) == 10
    assert points[["x", "y"]].notna().all().all()


def test_metadata_weather_score_bounds():
    papers = pd.DataFrame(
        {
            "paper_id": ["p1", "p2"],
            "year": [2024, 2024],
            "institution_known": [True, False],
            "country_known": [True, True],
            "affiliation_confidence": [0.9, 0.4],
            "topic_review_flag": [False, True],
        }
    )
    weather = metadata_weather_table(papers)
    assert weather["quality_score"].between(0, 1).all()
