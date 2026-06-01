from __future__ import annotations

import pandas as pd


def contains_token(series: pd.Series, token: str) -> pd.Series:
    if token == "All":
        return pd.Series(True, index=series.index)
    return series.fillna("").str.contains(token, case=False, regex=False)


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
    mask &= contains_token(papers["institutions_text"], institution)
    return papers.loc[mask].copy()

