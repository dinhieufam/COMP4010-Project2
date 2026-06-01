from __future__ import annotations

from pipeline.sample_data import sample_raw_rows
from pipeline.sources.neurips import parse_paper_id


def test_no_duplicate_ids_in_sample_contract():
    rows = sample_raw_rows()
    ids = [(row["venue"], row["paper_id"]) for row in rows]
    assert len(ids) == len(set(ids))


def test_required_raw_fields_present():
    required = {"venue", "year", "paper_id", "title", "authors", "url", "pdf_url", "doi", "source"}
    for row in sample_raw_rows():
        assert required.issubset(row)
        assert row["title"].strip()
        assert row["authors"]
        assert row["url"] or row["pdf_url"] or row["doi"]


def test_neurips_paper_id_is_stable_for_hash_urls():
    url = "https://proceedings.neurips.cc/paper_files/paper/2025/hash/abc123-Abstract-Conference.html"
    assert parse_paper_id(url, 2025, "Example") == "neurips_2025_abc123"

