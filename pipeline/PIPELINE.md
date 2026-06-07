# Data Processing Pipeline

This document describes every stage of the AI Conference Research Observatory pipeline.
The pipeline transforms raw NeurIPS proceedings pages into compact, app-ready Parquet
datasets used by the Shiny dashboard.

---

## Overview

```
proceedings.neurips.cc
        │
        ▼
01_scrape.py            →  data/raw/neurips_<year>.jsonl
        │
        ▼
02_enrich_openalex.py   →  data/interim/enriched.parquet
        │
        ├─ 02c_affiliations_pdf.py   (fills unknown affiliations from PDFs)
        │
        └─ 02d_enrich_openreview.py  (fills recent affiliations from OpenReview)
        │
        ▼
03_clean_normalize.py   →  data/interim/clean.parquet
        │
        ▼
04_topic_modeling.py    →  data/interim/topics.parquet
        │                   data/interim/topic_assignments.parquet
        │
        ▼
05_network_and_embedding.py  →  data/interim/topic_edges.parquet
        │
        ▼
06_forecast.py          →  data/interim/forecast.parquet
        │
        ▼
07_aggregate_for_app.py →  data/processed/papers.parquet
                            data/processed/topic_year.parquet
                            data/processed/country_year.parquet
                            data/processed/institution_year.parquet
                            data/processed/topic_edges.parquet
                            data/processed/forecast.parquet
                            data/processed/coverage.parquet
                            data/processed/affiliation_source_year.parquet

08_apply_institution_feedback.py  (optional manual correction pass)
        └─ re-runs 07 internally after patching interim files
```

---

## Stage 00 — Seed Sample Data

**Script:** `pipeline/00_seed_sample.py`

Generates deterministic synthetic sample data so the dashboard can start without
running the full pipeline. Useful for local development and testing.

```bash
python pipeline/00_seed_sample.py
```

---

## Stage 01 — Scraping

**Script:** `pipeline/01_scrape.py`  
**Input:** `proceedings.neurips.cc`  
**Output:** `data/raw/neurips_<year>.jsonl` (one file per year)

### What it does

1. Discovers all available NeurIPS years by parsing the proceedings index page
   (`https://proceedings.neurips.cc`) for year links.
2. For each year, fetches the year's index page and collects all `-Abstract` detail
   page links (one per accepted paper).
3. Concurrently fetches each paper's detail page (default 6 workers) and extracts:
   - `title` — from `<meta name="citation_title">` or the first heading tag
   - `authors` — from `<meta name="citation_author">` tags, or `<i>`/`.author` elements
   - `abstract` — from the paragraph after an "Abstract" heading, or from `<meta name="description">`
   - `url` — the canonical proceedings page URL
   - `pdf_url` — link ending in `.pdf` or labeled "paper"
   - `doi` — from `<meta name="citation_doi">` or any DOI-shaped href
   - `paper_id` — derived from the URL hash (`neurips_<year>_<hash>`) or a SHA-1 of
     title + year if no hash is present
4. Writes records as newline-delimited JSON (JSONL) to `data/raw/`.

### Key options

| Flag | Default | Purpose |
|---|---|---|
| `--venue` | `neurips` | Which conference to scrape |
| `--years` | all discovered | Restrict to specific years |
| `--force` | off | Re-scrape years that already have raw files |
| `--workers` | 6 | Concurrent detail-page fetches per year |

---

## Stage 02 — Enrichment: OpenAlex

**Script:** `pipeline/02_enrich_openalex.py`  
**Input:** `data/raw/*.jsonl`  
**Output:** `data/interim/enriched.parquet`

### What it does

Queries the [OpenAlex](https://openalex.org) API to add institution, country, DOI,
and concept metadata to each paper.

#### Matching strategy (bulk mode — default)

1. **Bulk download:** Fetches all OpenAlex works published in the NeurIPS source
   (`source_id=S4306420609`) in one paginated pull (cursor-based, 200 records/page).
2. **Hash matching:** Extracts the 32-character NeurIPS URL hash from OpenAlex
   location URLs and matches against the scraped paper's `url`/`pdf_url`. This is
   the most reliable match (`openalex_hash`, score = 1.0).
3. **DOI matching:** If a raw DOI is present, matches by exact normalized DOI
   (`openalex_doi`, score = 1.0).
4. **Title + author matching:** Normalized title similarity (SequenceMatcher ratio)
   combined with author surname overlap:
   - Score ≥ 0.90 → accepted as `openalex_title`
   - Score ≥ 0.82 AND author overlap ≥ 0.50 → accepted as `openalex_title_author`
   - Score ≥ 0.80 AND author overlap ≥ 0.34 → accepted
   - Otherwise → `unmatched`

#### Institution extraction

From each matched OpenAlex work's `authorships` list:
- `institutions` — display names of all author affiliations
- `institution_rors` — ROR (Research Organization Registry) identifiers
- `countries` — ISO 2-letter country codes from institution records

Unmatched papers get `["Unknown"]` for institutions and countries.

#### Fields added to each record

| Field | Description |
|---|---|
| `openalex_id` | OpenAlex work URI |
| `doi` | Normalized DOI |
| `institutions` | List of institution display names |
| `institution_rors` | List of ROR identifiers |
| `countries` | List of ISO2 country codes |
| `concepts` | Top 8 OpenAlex concept labels |
| `openalex_match_method` | How the match was made |
| `openalex_match_score` | Title similarity score (0–1) |
| `affiliation_source` | `openalex_hash`, `openalex_doi`, `openalex_title`, `none`, etc. |
| `affiliation_confidence` | Numeric confidence: 1.0 (hash/DOI), 0.86 (title), 0.0 (unmatched) |
| `institution_coverage` | Boolean — at least one known institution |
| `country_coverage` | Boolean — at least one known country |
| `has_abstract` | Boolean |
| `metadata_quality_flag` | `matched` or `openalex_unmatched` |

### Key options

| Flag | Default | Purpose |
|---|---|---|
| `--bulk-source-id` | NeurIPS source | Pull all works for this source, match locally |
| `--title-search` | off | Per-title API search instead of bulk pull |
| `--offline` | off | Skip API; produce all-Unknown enrichment |
| `--workers` | 6 | Concurrent lookups (title-search mode only) |
| `--resume` | off | Restart from `enriched.partial.parquet` checkpoint |
| `--checkpoint-every` | 1000 | Write checkpoint every N rows |

---

## Stage 02c — Affiliation Recovery: PDF Headers

**Script:** `pipeline/02c_affiliations_pdf.py`  
**Input:** `data/interim/enriched.parquet`  
**Output:** `data/interim/enriched.parquet` (updated in-place)

### What it does

For papers still showing `["Unknown"]` institutions after the OpenAlex pass, this
stage downloads the first page of each paper's PDF and extracts affiliations from
the author header text.

#### Pipeline

1. **Candidate selection:** Papers with unknown institutions and a non-empty `pdf_url`,
   sorted newest-first, limited to `--limit` papers per run (default 500).
2. **PDF download and caching:** Downloads each PDF to `data/interim/pdf_cache/`
   keyed by a SHA-1 hash of the paper ID / URL. Cached downloads are reused.
3. **Text extraction:** Uses `pypdf` to extract text from the first N pages (default 1).
   The extracted text is cached to `data/interim/pdf_text_cache/` so re-runs are free.
   The raw PDF is deleted after text extraction to save disk space.
4. **Header isolation:** Cuts the text at the first occurrence of "Abstract",
   "Introduction", or "Keywords" — everything before that is the author header.
5. **Institution extraction (two passes):**
   - **Known-alias matching:** Checks the header against a static dictionary of ~60
     major institutions and their known abbreviations/alternate names (e.g., `"mit"`
     → `"Massachusetts Institute of Technology"`). Also matches institutions seen ≥ 2
     times in the existing enriched data.
   - **Pattern mining:** If no known institution matches, uses regex patterns to find
     organization-like phrases: lines containing keywords like `university`, `institute`,
     `laboratory`, `research`, `Google`, `DeepMind`, etc. Cleans footnote markers,
     digits, and email addresses. Removes subsumed candidates (e.g., if both `"MIT"` and
     `"Massachusetts Institute of Technology"` are found, keeps only the longer one).
6. **Country extraction:**
   - From email domain TLDs (e.g., `.edu` → US, `.cn` → CN, `.ac.uk` → GB)
   - From country name phrases in the header text (e.g., "United States", "China")
   - From the static institution→country lookup table
7. **Confidence scoring:** Known-alias matches score 0.68, pattern-mined candidates 0.54;
   +0.07 if at least one country is resolved. Maximum confidence = 0.75.
   Records with confidence < `--min-confidence` (default 0.50) are discarded.
8. **Writing back:** Updates `institutions`, `countries`, `affiliation_source` (= `pdf_text`),
   and `affiliation_confidence` columns. Checkpoints every 100 recovered rows.

### Key options

| Flag | Default | Purpose |
|---|---|---|
| `--limit` | 500 | Max PDFs to inspect per run |
| `--years` | all | Restrict to specific years |
| `--pages` | 1 | Number of PDF pages to extract |
| `--min-confidence` | 0.50 | Minimum score to accept an extraction |
| `--refresh-source` | None | Reset rows from this affiliation source before processing |

---

## Stage 02d — Affiliation Recovery: OpenReview

**Script:** `pipeline/02d_enrich_openreview.py`  
**Input:** `data/interim/enriched.parquet`  
**Output:** `data/interim/enriched.parquet` (updated in-place)

### What it does

For recent NeurIPS years (default 2023, 2024, 2025), queries the
[OpenReview API v2](https://api2.openreview.net) to recover author affiliations
from author profiles.

#### Pipeline

1. **Fetch notes:** Downloads all accepted-paper notes for each target year from
   the NeurIPS venue (`NeurIPS.cc/<year>/Conference`). Notes include `title`,
   `authors`, and `authorids` (OpenReview `~` profile IDs). Results are cached
   to `data/interim/openreview_notes.json`.
2. **Match papers:** Joins each note to the enriched DataFrame by normalized title
   (lowercased, non-alphanumeric stripped).
3. **Fetch author profiles:** For each matched author ID not yet in the profile
   cache, fetches the OpenReview profile (with 16 concurrent workers). Profiles
   include institutional `history` entries with start/end years and institution
   `name` + `domain`. Cached to `data/interim/openreview_profiles.json`.
4. **Resolve institution and country:** For each author, selects the history entry
   whose date range covers the paper's year. Extracts the institution name and
   infers the country from the domain TLD (e.g., `oxford.ac.uk` → GB) or from a
   hardcoded institution-name lookup.
5. **Write back:** Only fills rows still showing `["Unknown"]` institutions.
   Sets `affiliation_source = "openreview"` and `affiliation_confidence = 0.9`.

### Key options

| Flag | Default | Purpose |
|---|---|---|
| `--years` | 2023 2024 2025 | Years to process |
| `--workers` | 16 | Concurrent profile fetches |
| `--sleep` | 0.02 | Delay between profile requests (seconds) |

---

## Stage 03 — Cleaning and Normalization

**Script:** `pipeline/03_clean_normalize.py`  
**Input:** `data/interim/enriched.parquet`  
**Output:** `data/interim/clean.parquet`

### What it does

Applies lightweight, non-destructive normalization across all columns:

| Column | Transformation |
|---|---|
| `title` | Collapse whitespace; strip leading/trailing space |
| `abstract` | Fill NaN → `""`; collapse whitespace |
| `authors` | Coerce to `list[str]`; empty → `["Unknown"]` |
| `institutions` | Coerce to `list[str]`; empty → `["Unknown"]` |
| `institution_rors` | Coerce to `list[str]`; add column if missing |
| `countries` | Coerce to `list[str]`; empty → `["Unknown"]` |
| `countries_iso2` | Coerce; default to `countries` if column absent |
| `affiliation_source` | Fill NaN → `"none"` |
| `affiliation_confidence` | Coerce to float; clip to [0, 1] |
| `institution_coverage` | Boolean — `institutions != ["Unknown"]` |
| `country_coverage` | Boolean — `countries != ["Unknown"]` |
| `has_abstract` | Boolean — `len(abstract) > 0` |
| `metadata_quality_flag` | `"usable"` if title and authors known, else `"needs_review"` |

No records are dropped. The output is a clean, type-stable Parquet for downstream
modeling stages.

---

## Stage 04 — Topic Modeling

**Script:** `pipeline/04_topic_modeling.py`  
**Input:** `data/interim/clean.parquet`, `pipeline/topic_taxonomy.json`  
**Output:** `data/interim/topics.parquet`, `data/interim/topic_assignments.parquet`  
**Audit:** `audits/topic_audit.csv`

### Curated taxonomy

Papers are classified into **15 fixed topics** from a hand-curated NeurIPS
taxonomy. Each topic has:
- **keywords** — individual tokens that contribute scores
- **seed_phrases** — multi-word phrases that strongly signal topic membership

| ID | Topic Label |
|---|---|
| 0 | Foundations & Theory |
| 1 | Optimization & Learning Algorithms |
| 2 | Deep Learning Architectures |
| 3 | Computer Vision & Multimodal Learning |
| 4 | Natural Language Processing & LLMs |
| 5 | Reinforcement Learning & Decision Making |
| 6 | Probabilistic Modeling & Bayesian Inference |
| 7 | Graph Learning & Network Science |
| 8 | Generative Models |
| 9 | Robustness, Safety & Alignment |
| 10 | Fairness, Privacy & Security |
| 11 | Neuroscience & Cognitive Science |
| 12 | Robotics & Control |
| 13 | Data, Evaluation & Benchmarks |
| 14 | Applications & Scientific ML |
| 15 | General / Other ML *(fallback)* |

### Scoring algorithm

Each paper is scored against all topics using a **hybrid keyword + vector** approach:

**1. Keyword score** (weight = 0.38)

Computed over `"<title> <title> <abstract>"` (title is doubled to up-weight it):
- Seed phrase match: **+4.0** per phrase
- Multi-word keyword match: **+2.5** per phrase
- Single-word keyword: **+min(count, 3)** per token

**2. Vector score** (weight = 0.62)

Uses `TF-IDF` (bigrams, `min_df=2`, `sublinear_tf=True`) fitted jointly on all paper
texts and topic prototype texts. Prototype text = `"<label>. <label>. <seed_phrases>. <keywords>"`.
Similarity is cosine distance between each paper vector and each topic prototype vector.

**3. Combined score**

```
score = 0.62 × (vector_score / max_vector) + 0.38 × (keyword_score / max(max_keyword, 8))
```

Topics are ranked by combined score. The highest-scoring topic wins the primary
assignment unless both keyword and vector scores fall below their thresholds
(in which case the paper is assigned to the **General / Other ML** fallback).

**4. Secondary topics**

Up to 3 secondary topics are recorded: any topic with score ≥ the primary threshold
AND score ≥ 82% of the primary topic's score.

**5. Review flag**

A `topic_review_flag = True` is set when:
- The primary assignment is the fallback topic, OR
- The softmax probability of the top topic is < 0.34 (low confidence), OR
- The margin between top and second topic probabilities is < 0.045

**6. Manual overrides**

`data/manual/topic_overrides.csv` lets reviewers pin `paper_id` → `primary_topic`
(and optionally `secondary_topics`) directly. Overrides set `topic_probability = 1.0`
and clear the review flag.

### Fields added

| Field | Type | Description |
|---|---|---|
| `topic_id` | int | Taxonomy topic identifier |
| `topic_label` | str | Human-readable topic name |
| `topic_probability` | float | Softmax probability of primary assignment |
| `topic_keywords` | str | Top 8 keywords from the assigned topic |
| `secondary_topic_ids` | list[int] | Up to 3 secondary topic IDs |
| `secondary_topic_labels` | list[str] | Secondary topic names |
| `topic_score` | float | Raw combined score |
| `secondary_topic_score` | float | Score of the top secondary topic |
| `topic_review_flag` | bool | True if assignment has low confidence |

---

## Stage 05 — Topic Network

**Script:** `pipeline/05_network_and_embedding.py`  
**Input:** `data/interim/topics.parquet`  
**Output:** `data/interim/topic_edges.parquet`

### What it does

Builds a weighted graph of topic relationships based on **keyword overlap** (Jaccard
similarity) and **co-occurrence size affinity**:

```
similarity   = |keywords_A ∩ keywords_B| / |keywords_A ∪ keywords_B|
size_weight  = min(papers_A, papers_B) / max(papers_A, papers_B)
edge_weight  = max(similarity, 0.15 × size_weight)
```

Edges with weight < 0.05 are discarded. The resulting edge table powers the
"Topic Connections" network chart in the dashboard's Topics tab.

### Output schema

| Column | Description |
|---|---|
| `source_topic_id` | Numeric ID of the source topic |
| `source_topic_label` | Name of the source topic |
| `target_topic_id` | Numeric ID of the target topic |
| `target_topic_label` | Name of the target topic |
| `weight` | Edge weight (0.05–1.0) |

---

## Stage 06 — Forecasting

**Script:** `pipeline/06_forecast.py`  
**Input:** `data/interim/topics.parquet`  
**Output:** `data/interim/forecast.parquet`  
**Audit:** `audits/forecast_backtest.csv`

### What it does

Forecasts the **paper count for each topic** for the next 2 years using a tiered
exponential smoothing strategy:

| Training years (n) | Model |
|---|---|
| n < 3 | Linear regression (`numpy.polyfit`) |
| 3 ≤ n < 6 | Simple Exponential Smoothing (level only) |
| n ≥ 6 | Holt-Winters additive trend (`ExponentialSmoothing(trend="add")`) |

All models fall back to linear regression if statsmodels raises an error. Point
forecasts are clipped to ≥ 0. **95% prediction intervals** are computed as
`point ± 1.96 × residual_std`.

**Backtesting:** For topics with ≥ 5 years of data, the last 2 years are held out
and MAPE (Mean Absolute Percentage Error) is computed. Results are written to
`audits/forecast_backtest.csv`.

### Output schema

| Column | Description |
|---|---|
| `venue` | Conference name |
| `year` | Forecast year |
| `topic_id` | Topic identifier |
| `topic_label` | Topic name |
| `forecast_count` | Predicted paper count |
| `lower` | Lower bound of 95% interval |
| `upper` | Upper bound of 95% interval |

---

## Stage 07 — Aggregation for the App

**Script:** `pipeline/07_aggregate_for_app.py`  
**Input:** `data/interim/topics.parquet`, `data/interim/topic_edges.parquet`,
`data/interim/forecast.parquet`, `data/raw/*.jsonl`  
**Output:** `data/processed/*.parquet` (8 files)

### What it does

Produces compact, denormalized datasets consumed directly by the Shiny dashboard.

#### papers.parquet

The main flat paper table. List-typed columns (`authors`, `countries`,
`institutions`) are serialized to delimited strings for Shiny compatibility.
Institutions use ` | ` as the delimiter (to avoid ambiguity with institution names
that contain commas). Countries and authors use `, `.

Selected columns written:

```
venue, year, paper_id, title, authors_text, topic_id, topic_label,
secondary_topic_labels_text, topic_score, secondary_topic_score,
topic_review_flag, countries_text, countries_iso2_text, institutions_text,
institution_rors_text, affiliation_source, affiliation_confidence,
country_known, institution_known, url, pdf_url, openalex_match_method, has_abstract
```

#### topic_year.parquet

Paper counts per `(venue, year, topic_id, topic_label)` — the basis for all
topic-trend charts.

#### country_year.parquet

Paper-participations per `(venue, year, country)`. Because a paper with authors
from multiple countries contributes to each country's count (via `pandas.explode`),
a single paper can appear in multiple rows.

#### institution_year.parquet

Paper-participations per `(venue, year, institution)`, generated the same way.

#### topic_edges.parquet

Copied from interim; see Stage 05.

#### forecast.parquet

Copied from interim; see Stage 06.

#### coverage.parquet

Per `(venue, year)` data quality audit:

| Column | Description |
|---|---|
| `scraped_count` | Records in raw JSONL files |
| `index_count` | Records in the processed table |
| `count_status` | `ok` or `mismatch` |
| `abstract_coverage` | Fraction of papers with an abstract |
| `openalex_match_rate` | Fraction matched to OpenAlex |
| `institution_coverage` | Fraction with known institution |
| `country_coverage` | Fraction with known country |
| `affiliation_confidence` | Mean confidence score |

#### affiliation_source_year.parquet

Paper counts broken down by `(venue, year, affiliation_source)`. Tracks what fraction
of affiliations came from each source (`openalex_hash`, `openalex_title`, `pdf_text`,
`openreview`, `none`, etc.).

---

## Stage 08 — Manual Institution Feedback (optional)

**Script:** `pipeline/08_apply_institution_feedback.py`  
**Input:** `data/manual/institution_feedback.csv`, `data/interim/topics.parquet`,
`data/interim/enriched.parquet`  
**Output:** Updated interim Parquets + regenerated `data/processed/` via Stage 07

### What it does

Applies reproducible, human-reviewed corrections to institution names and country
assignments. This stage patches interim files directly and re-runs Stage 07 to
propagate changes to the processed datasets.

#### Feedback CSV format

`data/manual/institution_feedback.csv` has one row per raw institution string:

| Column | Description |
|---|---|
| `raw_institution` | Exact string as it appears in the data |
| `approved` | `TRUE`, `FALSE`, or `REMOVE` |
| `canonical_institutions` | Corrected name(s) for `TRUE` rows |
| `manual_split_institutions` | Replacement list for `FALSE` (merged) rows |
| `current_country_candidates` | ISO2 codes associated with this institution |

#### Correction types

- **TRUE** — The raw string is close to correct; replace it with the canonical name
  (e.g., fixing trailing periods or minor typos).
- **FALSE** — The raw string is a merged multi-institution string (e.g., two
  affiliations concatenated by the PDF extractor). Replace with the `manual_split_institutions` list.
- **REMOVE** — The string is an extraction artifact (e.g., a department name or a
  generic phrase) — drop it entirely.

#### Country improvement

If the feedback CSV supplies `current_country_candidates` for an institution, those
ISO2 codes replace any previously inferred country data for papers that list that
institution. Papers already having OpenAlex country data keep the manual-derived data
(manual labels are considered more trustworthy for the cases where feedback was added).

---

## Data Directory Layout

```
data/
├── raw/                        # Per-year JSONL files from Stage 01
│   └── neurips_<year>.jsonl
├── interim/                    # Working datasets (not committed)
│   ├── enriched.parquet        # After Stage 02/02c/02d
│   ├── enriched.partial.parquet
│   ├── clean.parquet           # After Stage 03
│   ├── topics.parquet          # After Stage 04
│   ├── topic_assignments.parquet
│   ├── topic_edges.parquet     # After Stage 05
│   ├── forecast.parquet        # After Stage 06
│   ├── openalex_http_cache/    # 90-day HTTP response cache
│   ├── openreview_notes.json   # OpenReview note cache
│   ├── openreview_profiles.json
│   ├── pdf_text_cache/         # Extracted PDF header texts
│   └── pdf_cache/              # Temporary PDF downloads (auto-deleted)
├── manual/                     # Human-reviewed correction files
│   ├── institution_feedback.csv
│   ├── institution_aliases.csv
│   ├── institution_splits.csv
│   ├── institution_country_overrides.csv
│   ├── institution_review_queue.csv
│   └── topic_overrides.csv
└── processed/                  # App-ready Parquet files (committed)
    ├── papers.parquet
    ├── topic_year.parquet
    ├── country_year.parquet
    ├── institution_year.parquet
    ├── topic_edges.parquet
    ├── forecast.parquet
    ├── coverage.parquet
    └── affiliation_source_year.parquet
```

---

## Running the Pipeline

### Quick start (sample data)

```bash
python pipeline/00_seed_sample.py
shiny run app/app.py --reload
```

### Full pipeline

```bash
python pipeline/01_scrape.py --venue neurips
python pipeline/02_enrich_openalex.py
python pipeline/02c_affiliations_pdf.py          # optional affiliation recovery
python pipeline/02d_enrich_openreview.py --years 2023 2024 2025
python pipeline/03_clean_normalize.py
python pipeline/04_topic_modeling.py
python pipeline/05_network_and_embedding.py
python pipeline/06_forecast.py
python pipeline/07_aggregate_for_app.py
python pipeline/08_apply_institution_feedback.py # optional manual corrections
```

### Dependencies

Install all pipeline dependencies:

```bash
pip install -r requirements-pipeline.txt
```

Python 3.11+ is recommended.

---

## Audit Outputs

| File | Description |
|---|---|
| `audits/topic_audit.csv` | Per-topic paper counts, low-confidence counts, and example titles |
| `audits/forecast_backtest.csv` | Per-topic MAPE and model used for forecasting |
| `audits/coverage.csv` | Per-year metadata coverage rates (copy of `processed/coverage.parquet`) |
| `reports/coverage.csv` | Same coverage data; symlinked or copied for the dashboard's Coverage tab |
