# AI Conference Research Observatory

Local Tier 1 MVP for COMP4010 Project 2. The app explores accepted NeurIPS papers across years, topics, institutions, countries, and citation impact.

This repository intentionally excludes shinyapps.io deployment, the report, and slides for the local MVP pass.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-pipeline.txt
pip install -r requirements-app.txt
```

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
python pipeline/02b_enrich_doi_citations.py
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

`02b_enrich_doi_citations.py` is intentionally conservative. NeurIPS proceedings pages
usually do not expose DOI metadata, and broad Crossref title search can return false
matches. By default the step normalizes any DOI already found and uses DOI-based
Crossref lookups for extra citation counts. Optional title-search probes are available:

```bash
python pipeline/02b_enrich_doi_citations.py --crossref-title-limit 100
SEMANTIC_SCHOLAR_API_KEY=... python pipeline/02b_enrich_doi_citations.py --semantic-scholar-limit 1000
```

Topics use a curated NeurIPS taxonomy in `pipeline/topic_taxonomy.json`. The topic
step writes `reports/topic_audit.csv` and supports manual paper-level corrections in
`data/manual/topic_overrides.csv` with these columns:

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
- `data/processed/citation_impact.parquet`
- `data/processed/topic_edges.parquet`
- `data/processed/forecast.parquet`
- `data/processed/coverage.parquet`

The pipeline also writes `reports/coverage.csv` for completeness and metadata coverage.
