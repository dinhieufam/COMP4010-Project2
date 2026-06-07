# AI Conference Research Observatory

The AI Conference Research Observatory is an interactive data-visualization system
for exploring how NeurIPS research has evolved across years, topics, countries,
institutions, and collaboration networks.

**Live dashboard:** https://dinhieufam.shinyapps.io/neurips-research-trend/

## System Overview

The system has two connected parts:

1. A reproducible data pipeline collects accepted NeurIPS papers, enriches their
   metadata, assigns research topics, builds network data, and produces forecasts.
2. A Python Shiny dashboard presents the processed data through a guided story and
   an interactive explorer.

The dashboard provides:

- **Story mode** for a guided narrative of publication growth, topic shifts,
  geographic change, institutional participation, and collaboration.
- **Explore mode** for filtering and comparing topics, countries, institutions,
  years, and individual papers.
- **Coverage and provenance views** for communicating metadata quality and source
  limitations.

## Architecture

```text
NeurIPS proceedings
        |
        v
Scraping and metadata enrichment
        |
        v
Cleaning, topic modeling, networks, and forecasting
        |
        v
Compact processed Parquet datasets
        |
        v
Python Shiny dashboard
```

### Data Pipeline

The numbered scripts in `pipeline/` form the main processing workflow:

| Stage | Purpose |
|---|---|
| `01_scrape.py` | Collect accepted-paper metadata from NeurIPS proceedings |
| `02_enrich_openalex.py` | Add institutions, countries, and external metadata from OpenAlex |
| `02c_affiliations_pdf.py` | Recover affiliations from paper PDF headers |
| `02d_enrich_openreview.py` | Recover recent affiliations from OpenReview |
| `03_clean_normalize.py` | Normalize and validate paper metadata |
| `04_topic_modeling.py` | Assign papers to a curated NeurIPS topic taxonomy |
| `05_network_and_embedding.py` | Build topic relationship data |
| `06_forecast.py` | Forecast near-term topic publication counts |
| `07_aggregate_for_app.py` | Produce compact app-ready datasets |
| `08_apply_institution_feedback.py` | Apply reproducible manual institution corrections |

### Dashboard

`app/app.py` defines the Shiny user interface and reactive server logic.
Visualization modules live in `app/charts/`, shared filtering logic lives in
`app/filters.py`, and static styling and interactions live in `app/www/`.

### Data Quality

Automated tests in `tests/` check pipeline aggregation, topic taxonomy, dashboard
semantics, filters, application startup, and data completeness. Manual corrections
and their documentation live in `data/manual/`.

## Repository Structure

```text
.
|-- app/                    # Shiny dashboard, charts, and static assets
|-- data/
|   |-- raw/                # Scraped source records
|   |-- interim/            # Enriched and transformed working data
|   |-- manual/             # Reproducible human-reviewed corrections
|   `-- processed/          # Compact datasets consumed by the dashboard
|-- pipeline/               # Numbered data-processing stages and shared utilities
|-- report/                 # Generated report figures
|-- audits/                 # Data-quality and pipeline audit outputs
|-- tests/                  # Automated test suite
|-- requirements-app.txt    # Dashboard dependencies
`-- requirements-pipeline.txt
```

## Setup

Python 3.11 is recommended.

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements-pipeline.txt -r requirements-app.txt
```

All dependencies are pinned for reproducibility.

## Run the Dashboard

To generate deterministic sample data and launch the dashboard:

```bash
python pipeline/00_seed_sample.py
shiny run app/app.py --reload
```

The dashboard also creates sample processed data automatically when app-ready
Parquet files are unavailable.

## Run the Full Pipeline

Run the stages from the repository root:

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

The pipeline writes final application datasets to `data/processed/` and audit
outputs to `audits/`.

## Tests

```bash
python -m pytest
```
