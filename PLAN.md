# PLAN.md - AI Conference Research Observatory

Detailed implementation plan for building the complete COMP4010 Project 2 dashboard from the project idea in `IDEA.md`.

## 1. Project Goal

Build an interactive Python Shiny dashboard that lets users explore how accepted research at top AI conferences has evolved over time, beginning with the full history of NeurIPS and expanding to ICML and ICLR if time allows.

The project should answer:

> How has accepted research at top-tier AI conferences changed across topics, venues, geography, institutions, and impact from each venue's beginning to the present?

The final product must include:

- A reproducible offline data pipeline.
- A deployed Shiny for Python dashboard.
- At least 5 charts and at least 3 chart types.
- Interactive filtering and cross-filtering.
- A visible machine learning or analytics component.
- A completeness and data-quality validation layer.
- A report and demo story that clearly explains scope, findings, limitations, and reproducibility.

## 2. Scope Strategy

The project uses a tiered scope so the team can deliver a complete project even if some stretch goals are not finished.

### Tier 1 - Required MVP

Venue:

- NeurIPS, from 1987 to the latest available proceedings year.

Must include:

- Complete NeurIPS scraper.
- Completeness test for every NeurIPS year.
- OpenAlex enrichment where possible.
- Topic modeling or keyword/topic analytics.
- At least 5 dashboard charts.
- Deployed Shiny app.
- Report and presentation.

This tier alone is enough for a complete and defensible project.

### Tier 2 - Target

Venues:

- ICML, using PMLR.
- ICLR, using OpenReview.

Adds:

- Cross-venue comparison.
- Venue filter becomes meaningful.
- Venue x topic heatmap becomes a major chart.

Tier 2 should only start after NeurIPS scraping and completeness tests are working.

### Tier 3 - Stretch

Possible venues:

- CVPR, using CVF Open Access.
- ACL or EMNLP, using ACL Anthology data.

Adds:

- Subfield comparison across ML, vision, and NLP.

Tier 3 is optional and should not be attempted if it threatens the quality of Tier 1 or Tier 2.

## 3. Architecture

The project has two stages.

### Stage A - Offline Pipeline

Runs locally. It performs all heavy work:

- Scraping.
- API enrichment.
- Data cleaning.
- Topic modeling.
- Embedding and dimensionality reduction.
- Forecasting.
- Aggregation.
- Completeness reporting.

Outputs small processed parquet files for the app.

### Stage B - Shiny Dashboard

Runs on shinyapps.io. It performs only light work:

- Load processed parquet files.
- Apply filters.
- Render charts.
- Display paper table.

Hard rule:

- Do not run BERTopic, UMAP, embedding models, network generation, large API calls, or scraping inside the deployed app.

## 4. Repository Structure

Target structure:

```text
COMP4010-Project2/
|-- README.md
|-- IDEA.md
|-- PLAN.md
|-- requirements-app.txt
|-- requirements-pipeline.txt
|-- .gitignore
|-- data/
|   |-- raw/
|   |-- interim/
|   `-- processed/
|-- reports/
|   `-- coverage.csv
|-- pipeline/
|   |-- __init__.py
|   |-- config.py
|   |-- models.py
|   |-- sources/
|   |   |-- __init__.py
|   |   |-- base.py
|   |   |-- neurips.py
|   |   |-- icml_pmlr.py
|   |   `-- iclr_openreview.py
|   |-- 01_scrape.py
|   |-- 02_enrich_openalex.py
|   |-- 03_clean_normalize.py
|   |-- 04_topic_modeling.py
|   |-- 05_network_and_embedding.py
|   |-- 06_forecast.py
|   `-- 07_aggregate_for_app.py
|-- app/
|   |-- app.py
|   |-- data_loader.py
|   |-- filters.py
|   |-- charts/
|   |   |-- __init__.py
|   |   |-- streamgraph.py
|   |   |-- impact.py
|   |   |-- geography.py
|   |   |-- institutions.py
|   |   |-- heatmap.py
|   |   |-- network.py
|   |   `-- explorer.py
|   `-- www/
|       `-- styles.css
|-- tests/
|   |-- test_crawl_completeness.py
|   |-- test_data_quality.py
|   |-- test_aggregations.py
|   `-- test_app_smoke.py
|-- report/
|   `-- main.tex
|-- slides/
`-- .github/
    `-- workflows/
        `-- ci.yml
```

## 5. Data Contracts

Use stable data contracts so pipeline and app work independently.

### Raw Paper Record

Each venue adapter should output one JSON object per paper:

```json
{
  "venue": "neurips",
  "year": 2024,
  "paper_id": "neurips_2024_...",
  "title": "Paper title",
  "authors": ["Author One", "Author Two"],
  "abstract": "Abstract text or null",
  "url": "https://...",
  "pdf_url": "https://...pdf",
  "doi": null,
  "source": "proceedings.neurips.cc"
}
```

Required fields:

- `venue`
- `year`
- `paper_id`
- `title`
- `authors`
- at least one of `url`, `pdf_url`, or `doi`

### Enriched Paper Record

The enrichment step should add:

- `openalex_id`
- `doi`
- `citation_count`
- `institutions`
- `countries`
- `concepts`
- `openalex_match_method`
- `openalex_match_score`
- `has_abstract`
- `metadata_quality_flag`

### Topic Record

Topic modeling should produce:

- `paper_id`
- `topic_id`
- `topic_label`
- `topic_probability`
- `topic_keywords`

### Processed App Files

The app should load only compact processed files:

```text
data/processed/papers.parquet
data/processed/topic_year.parquet
data/processed/venue_topic.parquet
data/processed/country_year.parquet
data/processed/institution_year.parquet
data/processed/citation_impact.parquet
data/processed/topic_edges.parquet
data/processed/forecast.parquet
data/processed/coverage.parquet
```

Drop long abstracts from app data unless needed for paper detail view.

## 6. Build Phases

### Phase 0 - Project Setup

Goal:

- Prepare the repo for parallel work.

Tasks:

- Create the folder structure.
- Add `requirements-app.txt`.
- Add `requirements-pipeline.txt`.
- Add `.gitignore` rules for caches, large data, virtual environments, and temporary files.
- Add minimal `README.md` setup instructions.
- Add GitHub Actions skeleton.
- Create mock processed parquet files so app development can begin before the real pipeline is done.

Acceptance criteria:

- `python -m pytest` can run.
- `shiny run app/app.py` can start with mock data.
- Team members can install dependencies from requirements files.

### Phase 1 - NeurIPS Scraper

Goal:

- Build the full-history NeurIPS data source.

Tasks:

- Implement `pipeline/sources/base.py` with a shared adapter interface.
- Implement `pipeline/sources/neurips.py`.
- Discover year pages dynamically from NeurIPS proceedings.
- Parse paper detail pages for title, authors, abstract, and PDF URL.
- Save raw paper records to `data/raw/neurips_<year>.jsonl`.
- Cache HTTP responses to avoid repeated downloads.
- Add retries and polite throttling.

Acceptance criteria:

- All NeurIPS years from 1987 to latest available are scraped.
- Every output record follows the raw paper schema.
- No duplicate `(venue, paper_id)` pairs.
- Scraper can resume without re-scraping completed years.

### Phase 2 - Completeness and Data Quality

Goal:

- Prove the crawl is complete and reproducible.

Tasks:

- Implement index count per year.
- Compare index count to parsed detail count.
- Add external count table or script using DBLP/OpenAlex/official counts where feasible.
- Produce `reports/coverage.csv`.
- Add tests for duplicate IDs, missing titles, invalid years, empty authors, and missing locators.

Acceptance criteria:

- `tests/test_crawl_completeness.py` passes for all NeurIPS years.
- Known differences are documented with reason and tolerance.
- `reports/coverage.csv` includes:
  - `venue`
  - `year`
  - `scraped_count`
  - `index_count`
  - `external_count`
  - `count_status`
  - `abstract_coverage`
  - `openalex_match_rate`

### Phase 3 - OpenAlex Enrichment

Goal:

- Add citations, countries, institutions, concepts, and metadata coverage.

Tasks:

- Implement bulk OpenAlex source/year pulls.
- Match crawled papers to OpenAlex works.
- Match priority:
  1. DOI.
  2. Normalized title plus year.
  3. Normalized title plus first author plus year.
- Store match method and confidence.
- Keep unmatched papers in the dataset.
- Mark unknown country and institution explicitly.

Acceptance criteria:

- `data/interim/enriched.parquet` exists.
- Match rate is reported per venue/year.
- Unmatched papers are not dropped.
- Citation counts are non-negative.
- Country and institution fields use consistent list/string formats.

### Phase 4 - Topic Modeling and Analytics

Goal:

- Create the core analytical features for the dashboard.

Tasks:

- Prepare text field:
  - Use `title + abstract` when abstract exists.
  - Use title-only fallback when abstract is missing.
- Run topic modeling.
- Create human-readable topic labels.
- Aggregate topic counts by year and venue.
- Compute normalized citation impact by year.
- Build topic similarity or co-occurrence network.
- Optionally compute UMAP coordinates for paper landscape.
- Forecast topic volume for 1-2 future years with confidence intervals.

Recommended MVP approach:

- Start with TF-IDF plus KMeans or BERTopic depending on setup time.
- Use a small, stable number of topics for dashboard clarity.
- Manually clean top topic labels for presentation quality.

Acceptance criteria:

- Every paper has a topic assignment or an explicit unknown topic.
- `topic_year.parquet` can feed the streamgraph.
- `citation_impact.parquet` can feed the impact chart.
- `topic_edges.parquet` can feed the network chart.
- `forecast.parquet` includes lower and upper intervals.

### Phase 5 - Aggregation for App

Goal:

- Convert heavy intermediate data into small app-ready files.

Tasks:

- Create `pipeline/07_aggregate_for_app.py`.
- Pre-compute all chart inputs.
- Remove unnecessary columns from shipped app files.
- Validate totals across files.
- Add tests for aggregation consistency.

Acceptance criteria:

- `data/processed/*.parquet` files exist.
- Processed data size is small enough for shinyapps.io.
- Aggregation tests pass.
- App can load processed data in under a few seconds locally.

### Phase 6 - Shiny App MVP

Goal:

- Build a usable dashboard with real data.

Layout:

- Header with project title and short subtitle.
- Global filter bar:
  - venue
  - year range
  - topic
  - country
  - institution
- KPI row:
  - total papers
  - year range
  - top topic
  - OpenAlex match rate
  - abstract coverage
- Main chart grid.
- Paper explorer table at bottom.

Required charts:

1. Topic growth streamgraph or stacked area chart.
2. Citation impact line chart.
3. Country choropleth.
4. Institution leaderboard bar chart.
5. Topic x year heatmap.
6. Topic network graph.
7. Paper explorer table.

Tier 2 additions:

- Venue x topic heatmap.
- Venue comparison filter.
- Venue-level KPI cards.

Acceptance criteria:

- At least 5 charts render from real processed data.
- At least 3 chart types are present.
- All global filters update all relevant charts.
- Hover tooltips are informative.
- Paper table reflects current filters.
- App starts locally without pipeline-only dependencies.

### Phase 7 - Interactivity and Polish

Goal:

- Make the dashboard feel coherent and presentation-ready.

Tasks:

- Add cross-filtering:
  - click topic to filter topic.
  - click country to filter country.
  - click institution to filter institution.
  - click heatmap cell to filter topic/year or topic/venue.
- Add reset filters button.
- Add loading states where needed.
- Add coverage-by-year strip or compact table.
- Style with clean, readable CSS.
- Ensure chart labels are human-readable.
- Ensure early-year metadata limitations are visible.

Acceptance criteria:

- The dashboard supports a clear demo path.
- Viewers can understand missing metadata instead of mistaking it for zero activity.
- No chart is overcrowded by default.
- The app remains responsive on shinyapps.io constraints.

### Phase 8 - Tier 2 Venue Expansion

Goal:

- Add ICML and ICLR if Tier 1 is stable.

Tasks:

- Implement `icml_pmlr.py`.
- Implement `iclr_openreview.py`.
- Add venue config entries.
- Add completeness tests for each venue/year.
- Re-run enrichment and analytics with multi-venue data.
- Update dashboard venue filter and cross-venue charts.

Acceptance criteria:

- ICML and ICLR records follow the same schema as NeurIPS.
- Completeness tests pass or known exceptions are documented.
- Dashboard can compare venues without special-case code.

### Phase 9 - Deployment

Goal:

- Deploy the app to shinyapps.io with a local fallback.

Tasks:

- Create minimal app requirements.
- Ensure app imports only app dependencies.
- Ship only `app/`, `data/processed/`, and needed config/assets.
- Deploy using `rsconnect-python`.
- Test cold start and memory.
- Add live URL to `README.md`.
- Prepare local run command for demo fallback.

Acceptance criteria:

- Live app URL works.
- App cold-starts successfully.
- App does not exceed memory or bundle limits.
- README includes:
  - setup instructions.
  - local app command.
  - pipeline command order.
  - live deployment URL.
  - known limitations.

### Phase 10 - Report, Slides, and Demo

Goal:

- Package the technical work into a strong data story.

Report sections:

1. Motivation and research questions.
2. Scope change and why complete conference proceedings are defensible.
3. Data sources and pipeline.
4. Completeness and metadata coverage.
5. Visualization design and interaction.
6. Findings.
7. Machine learning and forecasting method.
8. Limitations.
9. Reproducibility.

Demo story:

1. Start with the full timeline of AI conference research.
2. Show topic waves across eras.
3. Show impact normalized by paper age.
4. Show geographic and institutional concentration.
5. Show topic network or heatmap.
6. Open paper explorer to prove the dashboard connects back to real papers.
7. Mention completeness tests and coverage indicator.
8. Close with limitations and future venue expansion.

Acceptance criteria:

- Slides fit the demo time.
- Report references the app and repository.
- The team has rehearsed the demo end to end.
- A local fallback app is ready.

## 7. Dashboard Chart Specification

### Chart 1 - Topic Growth

Type:

- Stacked area chart or streamgraph.

Purpose:

- Shows which research topics rise and fall over time.

Inputs:

- `topic_year.parquet`
- `forecast.parquet`

Interactions:

- Topic click updates global topic filter.
- Year brush updates year range.

### Chart 2 - Citation Impact

Type:

- Line chart.

Purpose:

- Shows citation impact while correcting for paper age.

Inputs:

- `citation_impact.parquet`

Interactions:

- Year selection updates global year range.
- Topic filter changes the line.

### Chart 3 - Country Map

Type:

- Choropleth.

Purpose:

- Shows geographic distribution of accepted research.

Inputs:

- `country_year.parquet`

Interactions:

- Country click updates global country filter.

### Chart 4 - Institution Leaderboard

Type:

- Horizontal bar chart.

Purpose:

- Shows institutions by output or normalized impact.

Inputs:

- `institution_year.parquet`

Interactions:

- Toggle between output and impact.
- Institution click updates global institution filter.

### Chart 5 - Topic Heatmap

Type:

- Heatmap.

Purpose:

- Shows topic intensity over time.

Inputs:

- `topic_year.parquet`

Interactions:

- Cell click filters topic and year.

Tier 2 mode:

- Toggle to venue x topic heatmap.

### Chart 6 - Topic Network

Type:

- Network graph.

Purpose:

- Shows relationships between topics based on co-occurrence or embedding similarity.

Inputs:

- `topic_edges.parquet`

Interactions:

- Node click updates topic filter.

### Chart 7 - Paper Explorer

Type:

- Interactive table.

Purpose:

- Lets users inspect the actual papers behind selections.

Inputs:

- `papers.parquet`

Fields:

- year
- venue
- title
- authors
- topic
- citations
- countries
- institutions
- URL/PDF

Interactions:

- Reflects all filters.
- Supports search and sorting.

## 8. Testing Plan

### Unit Tests

Test:

- Venue adapters parse expected fields.
- Normalization functions clean titles consistently.
- Aggregation totals match source totals.
- Forecast output has expected columns.
- App chart functions return Plotly figures.

### Data Quality Tests

Test:

- No duplicate `(venue, paper_id)`.
- Titles are non-empty.
- Years are valid.
- Citation counts are non-negative.
- Country codes are valid or unknown.
- Topics are assigned or explicitly unknown.

### Completeness Tests

Test:

- Index count equals scraped detail count.
- Scraped count matches external count within documented tolerance.
- Any exceptions are listed in coverage report.

### App Smoke Test

Test:

- App imports successfully.
- Processed parquet files load.
- Each chart can render from a small sample.

## 9. Command Workflow

Suggested local workflow:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-pipeline.txt
pip install -r requirements-app.txt
```

Run pipeline:

```bash
python pipeline/01_scrape.py --venue neurips
python pipeline/02_enrich_openalex.py
python pipeline/03_clean_normalize.py
python pipeline/04_topic_modeling.py
python pipeline/05_network_and_embedding.py
python pipeline/06_forecast.py
python pipeline/07_aggregate_for_app.py
```

Run tests:

```bash
python -m pytest
```

Run app locally:

```bash
shiny run app/app.py --reload
```

Deploy:

```bash
rsconnect deploy shiny app/ --title ai-conference-research-observatory
```

## 10. Team Responsibilities

Suggested ownership:

| Member | Role | Main responsibilities |
| --- | --- | --- |
| Pham Dinh Hieu | Integration and deployment | repo structure, CI, app deployment, README, final integration |
| Tran Ho Chi Thanh | Data engineering | NeurIPS scraper, venue adapters, caching, completeness tests |
| Nguyen Tuan Minh | Enrichment and ML | OpenAlex matching, topic modeling, forecasting, network, coverage metrics |
| Cao Pham Minh Dang | Dashboard | Shiny layout, charts, cross-filtering, CSS polish |

Everyone should contribute to the report, slides, and demo rehearsal.

## 11. Timeline

Current working date: 2026-06-01.

Final submission target from `IDEA.md`: 2026-06-07.

### June 1

- Finalize `PLAN.md`.
- Create repo structure.
- Create requirements files.
- Implement app scaffold with mock data.
- Start NeurIPS scraper.

### June 2

- Finish NeurIPS scraper.
- Save raw JSONL by year.
- Add completeness tests.
- Start OpenAlex enrichment.

### June 3

- Finish OpenAlex enrichment.
- Generate coverage report.
- Start topic modeling and basic analytics.
- App team builds charts against processed mock or partial data.

### June 4

- Finish topic/year, country/year, institution/year, citation, and heatmap aggregates.
- Wire real processed data into app.
- Ensure at least 5 charts work.

### June 5

- Add polish, cross-filtering, and coverage indicator.
- Deploy to shinyapps.io.
- Freeze Tier 1 MVP.
- Attempt Tier 2 only if Tier 1 is stable.

### June 6

- Finish report.
- Finish slides.
- Rehearse demo.
- Fix only high-impact bugs.

### June 7

- Final verification.
- Wake deployed app before presentation.
- Use local fallback if needed.

## 12. MVP Definition

The MVP is complete when:

- NeurIPS full-history data is scraped.
- Completeness tests pass or documented exceptions are explained.
- Processed app data is generated.
- Dashboard has at least 5 working charts.
- Dashboard has at least 3 chart types.
- Filters affect charts and paper table.
- One ML or analytics component is visible.
- App is deployed.
- README explains how to reproduce the work.
- Report and slides are ready.

## 13. Stretch Goals

Only attempt after MVP is stable:

- Add ICML and ICLR.
- Add venue comparison heatmap.
- Add UMAP research landscape.
- Improve topic labels manually.
- Add topic emergence detection.
- Add CVPR or ACL/EMNLP.
- Add more advanced cross-filtering and linked selection.

## 14. Risk Management

| Risk | Impact | Mitigation |
| --- | --- | --- |
| Scraping takes too long | High | Commit to NeurIPS first; cache responses; resume by year |
| Venue HTML changes | Medium | Keep one adapter per venue; tests catch failures |
| OpenAlex match rate is low | Medium | Keep unmatched papers; report match rate; use title/year fallback |
| Early metadata is sparse | High | Use title-only topic fallback; add coverage indicator |
| Topic modeling is too heavy | Medium | Fall back to TF-IDF plus KMeans |
| App exceeds shinyapps.io limits | High | Ship processed parquet only; remove abstracts; pre-aggregate |
| Dashboard becomes cluttered | Medium | Use default top-N topics and institutions |
| Tier 2 threatens deadline | High | Freeze Tier 1 first; Tier 2 is optional |
| Live demo fails | Medium | Prepare local fallback and wake deployed app early |

## 15. Final Deliverables

Required files and artifacts:

- `README.md`
- `IDEA.md`
- `PLAN.md`
- `requirements-app.txt`
- `requirements-pipeline.txt`
- `pipeline/`
- `app/`
- `tests/`
- `data/processed/*.parquet`
- `reports/coverage.csv`
- deployed Shiny app URL
- report PDF
- presentation slides

## 16. Definition of Done

- [ ] Repo structure is complete.
- [ ] NeurIPS scraper works from 1987 to latest available year.
- [ ] Raw data is saved reproducibly.
- [ ] Completeness tests pass for NeurIPS.
- [ ] OpenAlex enrichment is complete or clearly documented.
- [ ] Coverage report is generated.
- [ ] Topic modeling or topic analytics is complete.
- [ ] Forecast or normalized impact analytics is complete.
- [ ] Processed parquet files are generated.
- [ ] Dashboard loads processed data.
- [ ] At least 5 charts render.
- [ ] At least 3 chart types are used.
- [ ] Global filters work.
- [ ] Paper explorer works.
- [ ] App is deployed to shinyapps.io.
- [ ] README includes live URL and local run instructions.
- [ ] Report is complete.
- [ ] Slides are complete.
- [ ] Demo has been rehearsed.
