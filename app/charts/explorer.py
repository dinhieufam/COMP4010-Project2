from __future__ import annotations

import html
import re as _re
from typing import Optional

import pandas as pd


def _strip_latex(text: str) -> str:
    """Remove LaTeX markup from paper titles, returning readable plain text."""
    # Iteratively strip \cmd{content} → content (handles nesting up to 5 deep)
    for _ in range(5):
        prev = text
        text = _re.sub(r'\\[a-zA-Z]+\{([^{}]*)\}', r'\1', text)
        if text == prev:
            break
    # Strip inline/display math $...$ or $$...$$ → content
    text = _re.sub(r'\$\$?([^$]*?)\$\$?', r'\1', text)
    # Remove remaining \commands (e.g. \alpha → alpha)
    text = _re.sub(r'\\([a-zA-Z]+)', r'\1', text)
    # Remove backslash before non-alpha chars (\, \! etc.)
    text = _re.sub(r'\\[^a-zA-Z]', ' ', text)
    # Remove leftover braces
    text = text.replace('{', '').replace('}', '')
    # Normalise whitespace
    text = _re.sub(r'\s+', ' ', text).strip()
    return text

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


_CARD_MAX = 150


def make_paper_cards_html(papers: pd.DataFrame, max_cards: int = _CARD_MAX) -> str:
    """Card-layout HTML view of papers matching the Papers tab design."""
    if papers.empty:
        return '<p class="explorer-status">No papers match the current filters.</p>'

    data = papers.sort_values(
        ["year", "title"] if "title" in papers.columns else ["year"],
        ascending=[False, True] if "title" in papers.columns else [False],
    )
    total = len(data)
    truncated = total > max_cards
    if truncated:
        data = data.head(max_cards)
        status = (
            f'<p class="explorer-status">Showing first {max_cards:,} of {total:,} papers'
            f" — refine filters to narrow the results.</p>"
        )
    else:
        status = f'<p class="explorer-status">{total:,} paper{"s" if total != 1 else ""}</p>'

    cards: list[str] = []
    for row in data.itertuples(index=False):
        d = row._asdict()
        year       = _safe(d.get("year", ""))
        title      = _strip_latex(_safe(d.get("title", "")))
        authors    = _safe(d.get("authors_text", ""), 140)
        topic      = _safe(d.get("topic_label", ""))
        insts      = _safe(d.get("institutions_text", ""), 100)
        countries  = _safe(d.get("countries_text", ""), 80)
        url        = _safe(d.get("url", ""))
        pdf_url    = _safe(d.get("pdf_url", ""))

        topic_badge = f'<span class="pcard-topic">{html.escape(topic)}</span>' if topic else ""
        inst_html   = f'<div class="pcard-inst">{html.escape(insts)}</div>' if insts else ""
        country_html = f'<span class="pcard-country">{html.escape(countries)}</span>' if countries else ""

        links: list[str] = []
        if pdf_url:
            links.append(f'<a href="{html.escape(pdf_url, quote=True)}" target="_blank" rel="noopener" class="pcard-link">PDF</a>')
        if url:
            links.append(f'<a href="{html.escape(url, quote=True)}" target="_blank" rel="noopener" class="pcard-link pcard-link-sec">Proceedings</a>')
        links_html = "".join(links)

        cards.append(f"""<div class="pcard">
  <div class="pcard-meta-row">
    <span class="pcard-year">{html.escape(year)}</span>
    {topic_badge}
  </div>
  <div class="pcard-title">{html.escape(title)}</div>
  <div class="pcard-authors">{html.escape(authors)}</div>
  {inst_html}
  <div class="pcard-footer">
    {country_html}
    <div class="pcard-links">{links_html}</div>
  </div>
</div>"""
        )

    return f"""{status}<div class="pcards-container">{"".join(cards)}</div>"""
