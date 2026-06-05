from __future__ import annotations

import pandas as pd


def _token_set(value: object, sep: str = ",") -> set[str]:
    """Return the set of stripped, non-empty tokens split by sep."""
    if value is None or isinstance(value, float):
        return set()
    return {part.strip() for part in str(value).split(sep) if part.strip()}


def contains_token(series: pd.Series, token: str, sep: str = ",") -> pd.Series:
    """Return a boolean mask: True where token is an exact split member."""
    if token == "All":
        return pd.Series(True, index=series.index)
    return series.fillna("").apply(lambda v: token in _token_set(v, sep))


def apply_filters(
    papers: pd.DataFrame,
    year_range: tuple[int, int] | list[int],
    topic: str,
    country: str,
    institution: str,
) -> pd.DataFrame:
    start, end = int(year_range[0]), int(year_range[1])
    mask = papers["year"].between(start, end)
    if topic != "All":
        mask &= papers["topic_label"].eq(topic)
    mask &= contains_token(papers["countries_text"], country)
    mask &= contains_token(papers["institutions_text"], institution, sep=" | ")
    return papers.loc[mask].copy()
