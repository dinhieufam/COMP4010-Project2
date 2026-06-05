from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
APP_ROOT = ROOT / "app"
for p in (ROOT, APP_ROOT):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from filters import apply_filters, contains_token


def test_contains_token_exact_not_substring():
    """'Microsoft' must NOT match 'Microsoft Research' — exact comma-token match only."""
    series = pd.Series(["Microsoft Research, Google", "Microsoft, DeepMind", "Apple"])
    mask = contains_token(series, "Microsoft")
    assert mask.tolist() == [False, True, False]


def test_contains_token_all_returns_all_true():
    series = pd.Series(["United States", "China", None])
    assert contains_token(series, "All").all()


def test_contains_token_handles_none_and_nan():
    series = pd.Series([None, float("nan"), "United States"])
    mask = contains_token(series, "United States")
    assert mask.tolist() == [False, False, True]


def test_contains_token_whitespace_trimmed():
    """Values with extra spaces around commas should still match."""
    series = pd.Series(["  MIT  ,  Harvard  "])
    assert contains_token(series, "MIT").tolist() == [True]
    assert contains_token(series, "MIT  ").tolist() == [False]


def test_apply_filters_country_exact():
    papers = pd.DataFrame({
        "year": [2020, 2020, 2020],
        "topic_label": ["Deep Learning", "Deep Learning", "Reinforcement Learning"],
        "countries_text": ["United States, China", "United Kingdom", "United States"],
        "institutions_text": ["MIT", "Oxford", "Stanford"],
    })
    result = apply_filters(papers, (2018, 2025), "All", "United States", "All")
    assert len(result) == 2
    assert set(result["institutions_text"]) == {"MIT", "Stanford"}


def test_apply_filters_institution_exact():
    papers = pd.DataFrame({
        "year": [2022, 2022],
        "topic_label": ["NLP", "NLP"],
        "countries_text": ["United States", "United States"],
        "institutions_text": ["Microsoft Research, Google", "Microsoft"],
    })
    result = apply_filters(papers, (2020, 2025), "All", "All", "Microsoft")
    assert len(result) == 1
    assert result.iloc[0]["institutions_text"] == "Microsoft"
