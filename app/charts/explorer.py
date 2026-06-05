from __future__ import annotations

import html
from typing import Optional

import pandas as pd

_COLS_ORDERED = [
    "year",
    "title",
    "authors_text",
    "topic_label",
    "secondary_topic_labels_text",
    "institutions_text",
    "countries_text",
    "abstract",
    "url",
]

_HEADER_LABELS = {
    "year": "Year",
    "title": "Title",
    "authors_text": "Authors",
    "topic_label": "Topic",
    "secondary_topic_labels_text": "Secondary Topics",
    "institutions_text": "Institution",
    "countries_text": "Country",
    "abstract": "Abstract",
    "url": "Link",
}

_MAX_DEFAULT = 2000


def _safe(value: object, maxlen: int = 0) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    s = str(value).strip()
    if maxlen and len(s) > maxlen:
        s = s[:maxlen] + "…"
    return s


def make_explorer_html(papers: pd.DataFrame, max_rows: int = _MAX_DEFAULT) -> str:
    """Build a styled HTML table with clickable URL links for the Explorer tab."""
    avail = [c for c in _COLS_ORDERED if c in papers.columns]
    data = papers[avail].sort_values(
        ["year", "title"] if "title" in avail else ["year"],
        ascending=[False, True] if "title" in avail else [False],
    )

    total = len(data)
    if total == 0:
        return '<p class="explorer-status">No papers match the current filters.</p>'

    truncated = total > max_rows
    if truncated:
        data = data.head(max_rows)
        status = (
            f'<p class="explorer-status">Showing first {max_rows:,} of {total:,} papers. '
            f'Apply more specific filters to see all results.</p>'
        )
    else:
        status = f'<p class="explorer-status">{total:,} paper{"s" if total != 1 else ""}</p>'

    header_cells = "".join(
        f'<th>{_HEADER_LABELS.get(c, c)}</th>' for c in avail
    )

    rows_html: list[str] = []
    for row in data.itertuples(index=False):
        row_dict = row._asdict()
        cells: list[str] = []
        for col in avail:
            val = row_dict.get(col, "")
            raw = _safe(val)

            if col == "url":
                if raw:
                    safe_href = html.escape(raw, quote=True)
                    cells.append(
                        f'<td class="cell-link">'
                        f'<a href="{safe_href}" target="_blank" rel="noopener noreferrer">Link</a>'
                        f'</td>'
                    )
                else:
                    cells.append('<td class="cell-link">—</td>')

            elif col == "year":
                cells.append(f'<td class="cell-year">{html.escape(raw)}</td>')

            elif col == "title":
                cells.append(f'<td class="cell-title">{html.escape(raw)}</td>')

            elif col == "authors_text":
                cells.append(f'<td class="cell-authors">{html.escape(_safe(val, 100))}</td>')

            elif col == "topic_label":
                if raw:
                    cells.append(
                        f'<td class="cell-topic">'
                        f'<span class="topic-badge">{html.escape(raw)}</span>'
                        f'</td>'
                    )
                else:
                    cells.append('<td class="cell-topic">—</td>')

            elif col == "secondary_topic_labels_text":
                if raw:
                    parts = [p.strip() for p in raw.split(",") if p.strip()]
                    badges = " ".join(
                        f'<span class="topic-badge">{html.escape(p)}</span>'
                        for p in parts[:3]
                    )
                    cells.append(f'<td class="cell-topic">{badges}</td>')
                else:
                    cells.append('<td class="cell-topic">—</td>')

            elif col == "abstract":
                cells.append(f'<td class="cell-abstract">{html.escape(_safe(val, 220))}</td>')

            else:
                cells.append(f'<td>{html.escape(_safe(val, 120))}</td>')

        rows_html.append(f'<tr>{"".join(cells)}</tr>')

    return f"""{status}
<div class="explorer-table-wrapper">
  <table class="explorer-table">
    <thead><tr>{header_cells}</tr></thead>
    <tbody>{"".join(rows_html)}</tbody>
  </table>
</div>"""
