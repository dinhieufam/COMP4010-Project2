# AI Conference Research Observatory

Local Tier 1 MVP for COMP4010 Project 2. The app explores accepted NeurIPS papers across years, topics, institutions, countries, and metadata coverage.

This repository intentionally excludes shinyapps.io deployment, the report, and slides for the local MVP pass.

## Task Allocation

| Member | Responsibilities |
|--------|-----------------|
| Pham Dinh Hieu | Pipeline architecture, data scraping & enrichment (OpenAlex, OpenReview, PDF), topic modeling, ML forecast, Shiny app structure |
| Nguyen Tien Dat | Chart modules (geography, heatmap, network, streamgraph), cross-filtering interactivity, Shiny reactive patterns |
| Nguyen Nhat Minh | Creative visual lab (galaxy, river, race, bloom, orbit, weather, universe, DNA), CSS theming, visual design |
| Hoang Duc Minh | Data quality, tests, documentation, coverage & provenance panels |

## Setup

**Python version: 3.11** (recommended via `pyenv` or `conda`).

```bash
python3.11 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements-pipeline.txt   # full pipeline + tests
pip install -r requirements-app.txt        # app only (lighter)
```

Dependencies are fully pinned in both requirements files for reproducibility.

## Quick Local Demo

Generate deterministic sample data and start the dashboard:

```bash
python pipeline/00_seed_sample.py
shiny run app/app.py --reload
```

The app also creates sample processed data automatically if `data/processed/*.parquet` is missing.

## Full NeurIPS Pipeline

Run from the repository root:

```bash
python pipeline/01_scrape.py --venue neurips
python pipeline/02_enrich_openalex.py
python pipeline/02d_enrich_openreview.py --years 2023 2024 2025
python pipeline/03_clean_normalize.py
python pipeline/04_topic_modeling.py
python pipeline/05_network_and_embedding.py
python pipeline/06_forecast.py
python pipeline/07_aggregate_for_app.py
```

For a network-light development pass after scraping, use:

```bash
python pipeline/02_enrich_openalex.py --offline
```

Scholarly citation-count metrics are intentionally excluded from the app-ready dataset because coverage is too sparse for reliable comparison.

OpenAlex bulk enrichment is the default institution/country source. The OpenAlex
stage first tries exact NeurIPS URL-hash matching, then falls back to title/year
matching. Recent-year OpenReview affiliation recovery is available through
`pipeline/02d_enrich_openreview.py`; it caches notes and profiles under
`data/interim/openreview_*.json` so interrupted runs are resumable. If profile
fetching is slow, use `--limit-profiles` and rerun later.

To experiment with PDF-header affiliation recovery for OpenAlex-unmatched papers,
install `pdftotext` (Poppler) and run a bounded pass before normalization:

```bash
python pipeline/02c_affiliations_pdf.py --limit 500
```

Topics use a curated NeurIPS taxonomy in `pipeline/topic_taxonomy.json`. The topic
step now blends TF-IDF cosine similarity to fixed topic prototypes with the curated
keyword/seed-phrase scores. It writes `reports/topic_audit.csv` and supports manual
paper-level corrections in `data/manual/topic_overrides.csv` with these columns:

```csv
paper_id,title,primary_topic,secondary_topics,notes
```

Use semicolons between secondary topics, for example:

```csv
neurips_2025_example,Example Paper,Natural Language Processing & LLMs,"Robustness, Safety & Alignment; Data, Evaluation & Benchmarks",reviewed
```

## Tests

```bash
python -m pytest
```

## Outputs

The Shiny app reads only compact app-ready files:

- `data/processed/papers.parquet`
- `data/processed/topic_year.parquet`
- `data/processed/country_year.parquet`
- `data/processed/institution_year.parquet`
- `data/processed/topic_edges.parquet`
- `data/processed/forecast.parquet`
- `data/processed/coverage.parquet`
- `data/processed/affiliation_source_year.parquet`

The pipeline also writes `reports/coverage.csv` for completeness and metadata coverage, and `reports/forecast_backtest.csv` with per-topic Holt-Winters back-test MAPE scores.
