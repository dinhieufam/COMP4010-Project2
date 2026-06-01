from __future__ import annotations

from pipeline.sample_data import processed_frames


def test_topic_year_counts_reconcile_with_papers():
    frames = processed_frames()
    papers = frames["papers"]
    topic_year = frames["topic_year"]
    assert int(topic_year["paper_count"].sum()) == len(papers)


def test_coverage_counts_reconcile_with_papers():
    frames = processed_frames()
    coverage = frames["coverage"]
    assert int(coverage["scraped_count"].sum()) == len(frames["papers"])
    assert coverage["abstract_coverage"].between(0, 1).all()
    assert coverage["openalex_match_rate"].between(0, 1).all()

