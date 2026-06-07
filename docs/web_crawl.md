# NeurIPS Proceedings Web Crawling

This document describes the web crawling process used to collect NeurIPS paper metadata
from `proceedings.neurips.cc`. It covers the architecture, discovery logic, page parsing,
concurrency model, caching, and output format.

---

## Overview

The crawler is implemented as a scraper for `proceedings.neurips.cc`, the official
host of accepted NeurIPS papers going back to 1987. It is designed as a two-phase
process:

1. **Year discovery** — identify all years the conference has records for
2. **Paper collection** — for each year, collect every accepted paper's metadata

The entry point is `pipeline/01_scrape.py`, which delegates to a source adapter
(`pipeline/sources/neurips.py`) that handles all NeurIPS-specific HTML structure.

---

## Architecture

### Source adapter pattern

The scraper uses a `VenueSource` base class (`pipeline/sources/base.py`) that defines
the interface any conference source must implement:

```python
class VenueSource:
    venue: str
    def list_years(self) -> list[int]: ...
    def fetch_papers(self, year: int) -> list[dict]: ...
```

`NeurIPSSource` implements this interface. The design allows future venues (ICML,
ICLR, etc.) to be added without changing the main pipeline script.

### Component diagram

```
01_scrape.py
    │
    └── NeurIPSSource
            │
            ├── list_years()
            │       └── GET proceedings.neurips.cc
            │           GET proceedings.neurips.cc/papers
            │
            └── fetch_papers(year)
                    │
                    ├── detail_links(year)
                    │       └── GET /paper_files/paper/<year>
                    │           BeautifulSoup → href list
                    │
                    └── ThreadPoolExecutor (6 workers)
                            └── fetch_detail(url, year)  [×N papers]
                                    └── GET <detail URL>
                                        BeautifulSoup → PaperRecord
```

---

## Phase 1: Year Discovery

### Primary method

The crawler fetches two pages and scans them for year links:

- `https://proceedings.neurips.cc`
- `https://proceedings.neurips.cc/papers`

It searches for all hrefs matching the pattern `/paper_files/paper/<4-digit-year>`
using a compiled regex:

```python
YEAR_RE = re.compile(r"/paper_files/paper/(\d{4})")
```

All matched years between 1987 and 2100 are collected into a sorted list.

### Fallback method

If both primary pages fail (e.g., network error or the index structure changes),
the crawler falls back to probing each year from 1987 to the current year directly:

```python
for year in range(1987, date.today().year + 1):
    response = session.get(f".../paper_files/paper/{year}", timeout=timeout)
    if response.status_code == 200 and "-Abstract" in response.text:
        years.append(year)
```

The presence of `-Abstract` in the body is a reliable indicator that the year
index contains actual papers (all NeurIPS detail page links use this suffix).

---

## Phase 2: Paper Collection

### Step 1 — Discover detail page links

For each year, the crawler fetches the year's index page
(`proceedings.neurips.cc/paper_files/paper/<year>`) and parses it with BeautifulSoup:

```python
soup = BeautifulSoup(self._get(self.index_url(year)), "html.parser")
for link in soup.find_all("a", href=True):
    href = link["href"]
    if "-Abstract" not in href:
        continue
    if f"/paper/{year}/" not in href and f"/paper_files/paper/{year}/" not in href:
        continue
    full = urljoin(NEURIPS_BASE_URL, href)
    links.append(full)
```

Two URL path formats are handled because NeurIPS reorganised its URL structure between
older and newer proceedings years.

Each link uniquely identifies one accepted paper. Duplicates are deduplicated using a
`seen` set before the list is returned.

### Step 2 — Fetch and parse each paper's detail page

Detail pages are fetched concurrently using `concurrent.futures.ThreadPoolExecutor`
with a default of 6 workers. Each worker calls `fetch_detail(url, year)`.

---

## HTML Parsing: What Is Extracted

### Title

Primary source: `<meta name="citation_title" content="...">` — populated by the
proceedings CMS for all modern years.

Fallback chain (for older pages or missing meta tags):

```python
for tag in ("h1", "h2", "title", "h3", "h4"):
    node = soup.find(tag)
    if node:
        text = clean_text(node.get_text(" ", strip=True))
        if text and text.lower() not in {"abstract", "name change policy"}:
            return text
```

Any leading "Abstract" prefix is stripped (some older pages render the title
inside the abstract section).

### Authors

Primary source: all `<meta name="citation_author" content="...">` tags (one per author).

Fallback chain:
```python
for css in ("i", ".author", ".authors"):
    for node in soup.select(css):
        text = clean_text(node.get_text(" ", strip=True))
        return [part for part in re.split(r",|\band\b", text)]
```

Both comma-separated and ` and `-separated author lists are handled.
Returns `["Unknown"]` if nothing is found.

### Abstract

Primary source: paragraph following an "Abstract" heading:

```python
heading = soup.find(string=re.compile(r"^\s*Abstract\s*$", re.I))
for sibling in heading.parent.find_all_next(["p", "div"], limit=4):
    text = clean_text(sibling.get_text(" ", strip=True))
    if text and text.lower() != "abstract":
        return text
```

Fallback: `<meta name="description">` or `<meta name="citation_abstract">`.

Returns `None` if no abstract is found (older proceedings years often lack abstracts
in the HTML).

### PDF URL

Scans all `<a href>` tags for either:
- An href ending in `.pdf`
- A link whose visible text is `"paper"`

The first match is resolved to an absolute URL via `urljoin`. Returns `None` if absent.

### DOI

Checks four meta tag names in priority order: `citation_doi`, `dc.identifier`,
`dc.identifier.doi`, `doi`. Also scans all hrefs for DOI-shaped strings.

DOI normalization strips protocol prefixes (`https://doi.org/`, `doi:`), extracts
the `10.XXXX/...` pattern, and lowercases the result.

### Paper ID

```python
def parse_paper_id(url: str, year: int, title: str) -> str:
    match = re.search(r"/hash/([^/]+)-Abstract", url)
    if match:
        suffix = match.group(1)
    else:
        suffix = sha1(f"{year}:{title}:{url}".encode("utf-8")).hexdigest()[:16]
    return f"neurips_{year}_{suffix}"
```

For modern proceedings pages, the NeurIPS hash (a 32-character hex string embedded
in the URL path) is used directly. This hash is content-addressable — the same paper
always has the same hash — and is also used by the OpenAlex enrichment stage to
match papers by URL.

For older pages that use a different URL structure, a 16-character SHA-1 of
`<year>:<title>:<url>` is used as a stable fallback.

The resulting IDs have the form:
```
neurips_2024_a3f9c8b1d2e7...   (hash-based)
neurips_1995_4e1a2c9f8b3d7e1a  (SHA-1 fallback)
```

---

## Data Model

Each scraped record is a `PaperRecord` dataclass:

```python
@dataclass
class PaperRecord:
    venue: str        # "neurips"
    year: int
    paper_id: str     # "neurips_<year>_<hash>"
    title: str
    authors: list[str]
    abstract: str | None
    url: str | None   # detail page URL
    pdf_url: str | None
    doi: str | None
    source: str       # "proceedings.neurips.cc"
```

---

## Output Format

Each year's records are written as newline-delimited JSON (JSONL):

```
data/raw/neurips_1987.jsonl
data/raw/neurips_1988.jsonl
...
data/raw/neurips_2025.jsonl
```

Each line is one JSON object (one paper). JSONL was chosen over a single JSON array
because:
- Individual lines can be read without loading the entire file
- Partial writes are recoverable (complete lines are valid)
- The format is natural for streaming and `wc -l` file counts

### Example record

```json
{
  "venue": "neurips",
  "year": 2024,
  "paper_id": "neurips_2024_a3f9c8b1...",
  "title": "Attention Is All You Need",
  "authors": ["Ashish Vaswani", "Noam Shazeer", "Niki Parmar"],
  "abstract": "The dominant sequence transduction models...",
  "url": "https://proceedings.neurips.cc/paper_files/paper/2024/hash/a3f9c8b1...-Abstract.html",
  "pdf_url": "https://proceedings.neurips.cc/paper_files/paper/2024/file/a3f9c8b1...-Paper.pdf",
  "doi": "10.48550/arxiv.1706.03762",
  "source": "proceedings.neurips.cc"
}
```

---

## Concurrency Model

```
Year 1987  ─────────── serial (one detail page at a time if workers=1)
Year 2024  ─┬── worker 1 → fetch_detail(url_1, 2024)
             ├── worker 2 → fetch_detail(url_2, 2024)
             ├── worker 3 → fetch_detail(url_3, 2024)
             ├── worker 4 → fetch_detail(url_4, 2024)
             ├── worker 5 → fetch_detail(url_5, 2024)
             └── worker 6 → fetch_detail(url_6, 2024)
```

The year loop is **serial** — years are processed one at a time. Within each year,
paper detail pages are fetched **concurrently** using `ThreadPoolExecutor`:

```python
with ThreadPoolExecutor(max_workers=self.workers) as executor:
    futures = {executor.submit(self.fetch_detail, url, year): url for url in links}
    for future in as_completed(futures):
        papers.append(future.result().to_dict())
```

`as_completed()` collects results as they finish rather than in submission order;
the final list is sorted by `paper_id` before writing.

### Why thread-based, not async

The HTTP calls are I/O-bound and the `requests` library is synchronous.
ThreadPoolExecutor gives effective concurrency for I/O-bound work without requiring
an async rewrite. 6 workers is a conservative default that avoids triggering
`proceedings.neurips.cc`'s rate limiter.

---

## HTTP Caching

The crawler uses `requests_cache` (if installed) to cache HTTP responses:

```python
session = requests_cache.CachedSession(
    str(CACHE_DIR / "neurips"),  # data/http_cache/neurips
    expire_after=60 * 60 * 24 * 30,  # 30-day TTL
)
```

Cached responses are served from disk without hitting the server. Cached responses
do not count toward the throttle delay (`from_cache` is checked before sleeping).

If `requests_cache` is not installed, the crawler falls back to a plain
`requests.Session()` — all requests hit the live server.

### Cache directory

```
data/http_cache/
└── neurips.sqlite  (requests_cache SQLite backend)
```

The cache directory is defined in `pipeline/config.py` as `DATA_DIR / "http_cache"`
and is created by `ensure_dirs()` if absent.

---

## Rate Limiting

A configurable throttle delay is applied after each **uncached** request:

```python
if not getattr(response, "from_cache", False):
    time.sleep(self.throttle_seconds)  # default 0.05s
```

With 6 concurrent workers and a 50ms throttle per worker, the effective request rate
is approximately 120 requests/minute — well within the server's limits.

If a year index or detail page returns an error, `response.raise_for_status()` raises
a `requests.HTTPError`. The outer year loop catches this via the `ThreadPoolExecutor`
`future.result()` call and propagates it as a task failure without aborting the entire
crawl.

---

## Incremental / Idempotent Runs

The main script skips years that already have a raw JSONL file:

```python
path = raw_file(args.venue, year)
if path.exists() and not args.force:
    continue
```

This makes the crawler safe to run multiple times — already-scraped years are
untouched. Use `--force` to re-scrape specific years (e.g., after a proceedings
correction).

### Running specific years

```bash
# Re-scrape only 2024 and 2025
python pipeline/01_scrape.py --venue neurips --years 2024 2025 --force

# Scrape everything new (default — skips existing files)
python pipeline/01_scrape.py --venue neurips
```

---

## Error Handling

| Scenario | Behaviour |
|---|---|
| Year index page returns 4xx/5xx | `raise_for_status()` propagates; year is skipped with a warning |
| Individual detail page fails | Worker raises exception; collected by `as_completed()` propagation |
| No years discovered | `RuntimeError("No years discovered")` halts the script |
| No raw files found downstream | `RuntimeError` in `02_enrich_openalex.py` prevents running on empty data |
| `requests_cache` not installed | Falls back to plain `requests.Session()` silently |

---

## Full Example Run

```
$ python pipeline/01_scrape.py --venue neurips
Scraping neurips:   0%|          | 0/38 [00:00<?, ?it/s]
neurips 1987: wrote 90 records to data/raw/neurips_1987.jsonl
neurips 1988: wrote 105 records to data/raw/neurips_1988.jsonl
...
neurips 2024: wrote 3,737 records to data/raw/neurips_2024.jsonl
neurips 2025: wrote 5,823 records to data/raw/neurips_2025.jsonl
Scraping neurips: 100%|██████████| 38/38 [12:43<00:00, 20.1s/it]
```

Total scrape time for the full corpus (38 years, ~30,000 papers) is approximately
10–15 minutes with 6 workers and HTTP caching cold. Subsequent runs are near-instant
for already-scraped years.

---

## What Is NOT Scraped

The scraper collects only **publicly available HTML metadata** from the proceedings
pages. It does not:

- Download or parse full paper PDFs at this stage (that is done selectively in
  `02c_affiliations_pdf.py` only for papers with missing affiliations)
- Access author affiliation pages on the proceedings site (affiliations come from
  OpenAlex and OpenReview in later stages)
- Follow links to external sites (arXiv, institutional pages, etc.)
- Scrape workshop papers or non-accepted submissions

The scraper produces only the core bibliographic record: title, authors, abstract,
URLs, and DOI.
