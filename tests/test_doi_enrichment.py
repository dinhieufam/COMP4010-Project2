from __future__ import annotations

import importlib


doi_enrichment = importlib.import_module("pipeline.02b_enrich_doi_citations")


def test_normalize_doi_accepts_common_forms():
    assert doi_enrichment.normalize_doi("https://doi.org/10.1145/3065386") == "10.1145/3065386"
    assert doi_enrichment.normalize_doi("doi:10.5555/1234567.") == "10.5555/1234567"
    assert not doi_enrichment.has_doi(float("nan"))


def test_crossref_title_acceptance_requires_neurips_container():
    assert doi_enrichment.NEURIPS_CONTAINER_RE.search("Advances in Neural Information Processing Systems")
    assert not doi_enrichment.NEURIPS_CONTAINER_RE.search("Communications of the ACM")


def test_title_similarity_handles_punctuation():
    assert doi_enrichment.title_similarity("Attention is All you Need", "Attention Is All You Need") == 1.0
