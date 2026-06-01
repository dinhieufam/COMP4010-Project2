from __future__ import annotations

import pandas as pd


def paper_table(papers: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "year",
        "title",
        "authors_text",
        "topic_label",
        "secondary_topic_labels_text",
        "topic_review_flag",
        "citation_count",
        "citation_source",
        "doi",
        "countries_text",
        "institutions_text",
        "url",
    ]
    available = [column for column in columns if column in papers.columns]
    return papers[available].sort_values(["year", "title"], ascending=[False, True]).head(500)
