from __future__ import annotations

from pipeline.sample_data import processed_frames


def test_papers_have_valid_core_fields():
    papers = processed_frames()["papers"]
    assert papers["title"].str.len().gt(0).all()
    assert papers["year"].between(1987, 2100).all()
    assert papers["authors_text"].str.len().gt(0).all()
    assert "citation_count" not in papers.columns


def test_unknown_buckets_are_explicit_when_present():
    papers = processed_frames()["papers"]
    assert not papers["countries_text"].isna().any()
    assert not papers["institutions_text"].isna().any()
