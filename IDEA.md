# Build Plan — AI Conference Research Observatory (COMP4010 Project 2)

> Interactive Python Shiny dashboard mapping the evolution of top-tier AI-conference research, from each venue's first year to the latest — beginning with the **full history of NeurIPS (1987→present)** and expanding to other flagship venues.

**Team (Group 5):** Tran Ho Chi Thanh · Nguyen Tuan Minh · Pham Dinh Hieu · Cao Pham Minh Dang
**Repo:** https://github.com/dinhieufam/COMP4010-Project2
**Final submission:** 07/06 · **This plan written:** 26/05 (≈ 12 days to deliver)

---

## 0. What changed since the proposal (and why)

The advisor's feedback retires the original "crawl *all* AI research" plan, for two correct reasons:

1. **Infeasible at scale** — the full arXiv + OpenAlex AI corpus is millions of papers; we cannot collect, store, or process it within the timeline or the shinyapps.io free tier.
2. **Sampling bias** — crawling only "part" of the literature gives a non-representative, undefendable sample, which undermines every claim the dashboard makes.

**The fix: switch from a population we cannot define to a population we can crawl *exhaustively*.**

We crawl **complete venue proceedings — every accepted paper, from each venue's first edition to the latest.** A conference's proceedings are a *closed, enumerable, authoritative* set, which is exactly what makes the completeness test possible. We no longer claim to describe "all AI research"; we describe *the accepted research at flagship AI venues* — a precise, defendable sampling frame (and a strong "Limitations" section in the report).

### Scope: full history, tiered by venue

We extend each venue back to its **first year**, not just 2018–2025. This makes the story far richer — the dashboard now spans the kernel-methods/SVM era, the 2012 deep-learning takeoff, and the transformer/LLM era — and it costs us little, because old years have few papers. We add venues in **tiers**, committing to Tier 1, targeting Tier 2, and treating Tier 3 as stretch:

| Tier | Venues | Year range | Source | Status |
| --- | --- | --- | --- | --- |
| **1 — Commit** | **NeurIPS** | **1987→latest** | `proceedings.neurips.cc` (static HTML, uniform `/paper_files/paper/<year>` URLs) | Spine of the project; a complete project on its own |
| **2 — Target** | **ICML**, **ICLR** (the "big three" with NeurIPS) | ICML 2010→latest (PMLR), ICLR 2013→latest | ICML → PMLR (`proceedings.mlr.press`); ICLR → OpenReview API | Unlocks cross-venue comparison |
| **3 — Stretch** | A vision venue (**CVPR**) and/or an NLP venue (**ACL/EMNLP**) | venue history | CVPR → CVF Open Access (`openaccess.thecvf.com`); ACL/EMNLP → **ACL Anthology data dump** (no scraping) | Enables an ML-vs-CV-vs-NLP subfield story |

**Why these and why this order:** NeurIPS alone satisfies every requirement. ICML+ICLR are the natural siblings and share clean structured sources, so the marginal effort is low. CVPR/ACL broaden "AI" beyond core ML for a subfield comparison, but each adds a new code path and risk, so they stay optional. **Don't let venue count threaten the deadline — a polished Tier 1 beats a broken Tier 3.**

**The scraper reads each venue's index dynamically** (it discovers the list of years/volumes at runtime) so new editions — NeurIPS 2025, ICLR 2026, etc. — are picked up automatically as soon as they publish, with no hard-coded year list.

This pivot is the single most important thing in this plan. Everything below assumes it.

---

## 1. Refined research question & data story

**Main question:** *How has the research accepted at top-tier AI conferences evolved — from each venue's beginnings to today — across topics, geography, institutions, and scholarly impact, and where is it heading?*

**Narrative arc for the demo** (the rubric weights storytelling heavily):

> *Four decades of frontier AI in one view.* Starting from NeurIPS 1987, we walk the viewer through the eras — early neural nets, the kernel/SVM years, the 2012 deep-learning takeoff, and the transformer→LLM→diffusion→agents wave — showing which topics rose and fell, who led each wave (institutions/countries), how topics relate, how impact distributes once we correct for paper age, and a short forecast of where volume is heading. With Tier 2+, we contrast how NeurIPS, ICML, and ICLR (and optionally CV/NLP venues) emphasised different topics over the same period.

**Sub-questions, each answered by a specific chart:**

| Sub-question | Chart |
| --- | --- |
| Which topics rose/fell over the full history? | Topic streamgraph (+ forecast overlay) |
| How is impact distributed, fairly compared? | Field/year-normalised citation timeline |
| Who leads geographically? | Country choropleth |
| Which institutions dominate, by output vs impact? | Institution leaderboard (toggle) |
| How are research areas connected? | Topic co-occurrence / similarity network |
| How do venues differ in topic emphasis? *(Tier 2+)* | Venue × Topic heatmap |
| How does topic intensity shift year by year? | Topic × Year heatmap |
| What does the whole landscape look like? | UMAP "research landscape" scatter (stretch) |
| How complete is metadata across the decades? | Coverage-by-year indicator (see §5) |
| Show me the actual papers behind any selection | Paper explorer table |

---

## 2. System architecture (two-stage, dictated by the free tier)

shinyapps.io free tier = **1 GB RAM, 1 GB bundle, 25 active hrs/month, app sleeps when idle.** Therefore:

```
 ┌─────────────────────────────────────────────┐        ┌──────────────────────────────┐
 │  STAGE A — OFFLINE PIPELINE (runs on laptop) │        │  STAGE B — SHINY APP (deployed)│
 │  Heavy, slow, one-time / re-runnable          │  ───►  │  Light, fast, runtime only     │
 │                                               │ small  │                                │
 │  scrape → enrich → topic-model → embed →      │ parquet│  load parquet → filter →       │
 │  network → forecast → AGGREGATE               │ files  │  render Plotly figures         │
 └─────────────────────────────────────────────┘        └──────────────────────────────┘
```

**Hard rule:** **no BERTopic, no UMAP, no embedding, no model training inside the deployed app.** All of that runs once in Stage A and is baked into compact `.parquet` files (target: a few MB, abstracts dropped from the shipped bundle). The app only reads those files, applies pandas/polars filters, and draws charts. This keeps memory low, cold-starts fast, and the bundle tiny.

---

## 3. Data sources & their roles

Two kinds of source: **per-venue list sources** (the authoritative "who got accepted" lists we crawl), and **enrichment sources** (which add institutions, countries, citations, abstracts where missing).

### 3a. Per-venue list sources (the crawl targets)

| Venue | Source | Years | Access pattern | Gives us | Notes |
| --- | --- | --- | --- | --- | --- |
| **NeurIPS** | `proceedings.neurips.cc` | **1987→latest** | Static HTML; index at `/`, year pages at `/paper_files/paper/<year>`; detail links contain `-Abstract*.html` | title, authors, abstract, paper-id, PDF | Accepted-by-construction. 1987≈90 papers → 2024≈4000+. Datasets & Benchmarks track merged into main from 2022 (separate in 2021). |
| **ICML** | PMLR `proceedings.mlr.press` | ~2010→latest reliably | Static HTML per volume (`/v<NN>/`); each paper has title/authors/abstract/PDF/BibTeX | title, authors, abstract | Accepted-by-construction. Confirm the volume number per year (e.g. ICML 2024 = v235). |
| **ICLR** | **OpenReview API** (`api2.openreview.net`) | 2013→latest | REST API; query the venue invitation, **filter to accepted decisions** | title, authors, abstract, decision, scores | ICLR is fully on OpenReview → cleanest accept/reject signal of all venues. |
| **CVPR** *(stretch)* | CVF Open Access `openaccess.thecvf.com` | venue history | Static HTML day/year listings | title, authors, abstract, PDF | Accepted-by-construction. ICCV/ECCV/WACV available the same way if wanted. |
| **ACL / EMNLP** *(stretch)* | **ACL Anthology data dump** (GitHub, BibTeX/XML) | venue history | Download dump — **no scraping** | title, authors, abstract, venue, year | Cleanest of all. Decide whether to include the *Findings* track (recommend: exclude or flag separately). |

**Optional unifying backbone — DBLP.** DBLP (`dblp.org`, REST API + full XML dump) holds consistent structured records for *every* venue above and publishes an authoritative paper count per venue/year. We use it as an **independent ground-truth count** for the completeness test (§5) across all venues, and optionally as a fallback list source. DBLP has no abstracts, so it complements rather than replaces the sources above.

### 3b. Enrichment sources (applied to every venue uniformly)

| Source | Role | Access | Notes |
| --- | --- | --- | --- |
| **OpenAlex** | institutions, countries, venue id, citation count, topics/concepts, DOI, abstract-inverted-index | Free REST API, no key (add `mailto=` for the polite pool) | **Bulk pull by source+year** (`works?filter=primary_location.source.id:<Sxxx>,publication_year:<Y>`) is far faster than per-paper lookups. Match crawled papers by DOI → title+year+author overlap. |
| **arXiv** | abstracts/categories for papers missing them (common in older years) | Free API | Fills abstract gaps so topic modeling still works on early papers. |
| **Semantic Scholar** *(opt.)* | extra citation/influence signal | Free API, rate-limited | Only if time allows; OpenAlex already covers citations. |
| **Papers with Code** *(opt.)* | task/benchmark/code tags | Public dumps | Lowest priority. |

**Matching & enrichment strategy:** prefer OpenAlex's **bulk source+year pull** to get most fields in a few paginated calls per venue-year; reconcile against the crawled ground-truth list by DOI, then title+year+author overlap. **Record and report the match rate per (venue, year)** — it is itself a quality metric and feeds the coverage indicator in §5.

> **The metadata gradient.** Old papers (pre-~2000) often lack abstracts, affiliations, and reliable country data in OpenAlex. We handle this explicitly: title-only topic assignment where no abstract exists, "unknown" buckets for missing geography, and a **coverage-by-year indicator** so users see *where* the data thins out rather than being misled. This honesty is a report and rubric win, not a weakness.

---

## 4. Data pipeline (Stage A — `pipeline/`)

Each step is a standalone, re-runnable script that writes to disk so we never re-crawl unnecessarily.

**Key design: one adapter per venue, venue-agnostic everything else.** Each list source gets a small adapter in `pipeline/sources/` (`neurips.py`, `icml_pmlr.py`, `iclr_openreview.py`, …) exposing the same interface — `list_years()` and `fetch_papers(year) -> list[PaperRecord]` — and emitting a **normalised record** with a `venue` and `year` column. Step 02 onward never knows or cares which venue a paper came from, so adding a venue = adding one adapter + one row in the completeness table, nothing downstream changes.

```python
# normalised record every adapter yields
PaperRecord = {
    "venue": "neurips", "year": 1998, "paper_id": "...",
    "title": "...", "authors": [...], "abstract": "...|None",
    "url": "...", "doi": "...|None",
}
```

| Step | Script | Input | Output |
| --- | --- | --- | --- |
| 01 | `01_scrape.py --venue <v>` | venue adapter | `data/raw/<venue>_<year>.jsonl` |
| 02 | `02_enrich_openalex.py` | all raw papers | `data/interim/enriched.parquet` (+ institutions, countries, citations, topics, DOI, match_flag) |
| 03 | `03_enrich_semscholar.py` *(opt.)* | enriched | adds influence fields |
| 04 | `04_topic_modeling.py` | abstracts (title-only fallback) | `data/interim/topics.parquet` |
| 05 | `05_embed_and_network.py` | abstracts/topics | UMAP 2-D coords + topic co-occurrence edge list |
| 06 | `06_forecast.py` | topic-year counts | `data/interim/forecast.parquet` (fitted + projected w/ CI) |
| 07 | `07_aggregate_for_app.py` | all above | **`data/processed/*.parquet`** — the only files the app ships |

**Caching & politeness:** cache every HTTP response to disk; prefer OpenAlex bulk source+year pulls; throttle (polite pool, ≤ ~10 req/s); exponential backoff on 429. The crawl is idempotent and resumable per (venue, year).

---

## 5. The crawl completeness test (advisor's explicit requirement)

This is a graded differentiator — it lands directly in "Reproducibility & code quality." We test **two independent levels, per (venue, year)**, rather than one brittle magic number.

**Level 1 — Index ↔ detail consistency (did we fetch everything the source lists?)**
For each (venue, year), count the items the adapter's index step discovers (abstract links for NeurIPS/CVF, papers in a PMLR volume, accepted submissions from OpenReview), then assert we successfully parsed exactly that many detail records with no silent fetch failures.

**Level 2 — Source ↔ external ground truth (is the source itself complete / the right track?)**
Assert each (venue, year) count matches an independent published figure within a documented tolerance. Ground-truth sources differ by venue: **DBLP** count per venue/year (works for all), OpenAlex source+year count, OpenReview decision tallies (ICLR), or official acceptance statistics. Document the source and the reason for any tolerance (e.g. NeurIPS 2021 Datasets & Benchmarks separate proceedings; ACL *Findings* track inclusion choice).

```python
# tests/test_crawl_completeness.py  (sketch)
import pytest
from pipeline.sources import get_adapter, load_scraped

# (venue, year) pairs are generated from each adapter's list_years()
CASES = [(v, y) for v in ("neurips", "icml", "iclr")
                for y in get_adapter(v).list_years()]

@pytest.mark.parametrize("venue,year", CASES)
def test_index_equals_detail(venue, year):
    """Level 1: every paper the index lists was scraped & parsed."""
    expected = get_adapter(venue).index_count(year)
    got = len(load_scraped(venue, year))
    assert got == expected, f"{venue} {year}: parsed {got} of {expected}"

@pytest.mark.parametrize("venue,year", CASES)
def test_count_matches_ground_truth(venue, year):
    """Level 2: count agrees with an external source (e.g. DBLP)."""
    got = len(load_scraped(venue, year))
    exp = EXTERNAL_COUNTS[(venue, year)]      # documented per pair
    assert abs(got - exp) <= TOLERANCE.get((venue, year), 0)

def test_no_duplicate_ids(all_papers):
    ids = [(p["venue"], p["paper_id"]) for p in all_papers]
    assert len(ids) == len(set(ids))

def test_required_fields(all_papers):
    for p in all_papers:
        assert p["title"].strip()
        assert p["venue"] and p["year"]
        assert p["url"] or p["doi"]          # at least one locator
```

Run these in **GitHub Actions CI** so completeness is verified on every push. Known anchors to confirm against (don't trust memory — verify from the source/DBLP): NeurIPS 1987 ≈ 90 papers, NeurIPS 2021 main track ≈ 2334. A `reports/coverage.csv` artifact (per venue/year: scraped count, ground-truth count, OpenAlex match rate, abstract-coverage %) is produced by the pipeline and drives the dashboard's **coverage-by-year indicator**.

---

## 6. Machine learning & analytics (COMP 5120 — the score multiplier)

The rubric explicitly rewards "machine learning + prediction + interactive visualization + analytical storytelling." We hit four ML/analytics components:

1. **Topic modeling — BERTopic** (sentence-transformer embeddings → UMAP → HDBSCAN → c-TF-IDF labels) over abstracts. Produces data-driven topics rather than hand-coded keywords. Fallback: TF-IDF + KMeans if BERTopic is too heavy to fit in time.
2. **Time-series forecasting** of topic volume to ~2026–2027. The full venue history gives **decades of yearly points** per topic (a real advantage over the original 2018–2025 window), so a proper model is defensible — exponential smoothing / Prophet / linear-with-CI. **Always show confidence intervals** and caveat honestly. Directly satisfies "forecasting and prediction"; feeds the streamgraph's forecast overlay.
3. **Topic similarity network** — edges from topic co-occurrence within papers and/or cosine similarity of topic centroid embeddings; threshold + top-N to keep it readable.
4. **Field/age-normalised citation impact** — raw citation counts unfairly favour older papers, so normalise by publication year (and optionally topic) to compare impact fairly. Sophistication point for the report.

**Stretch:** emergence/inflection detection to auto-flag "breakout" topics (LLMs, diffusion, agents) from their growth curves.

---

## 7. Dashboard specification (Stage B — `app/`)

**Requirement check:** brief asks for **≥ 5 charts, ≥ 3 chart types.** We ship **7 chart types**, comfortably exceeding both.

**Global layout** (single page, top filter bar + responsive grid; mirrors the proposal wireframe):

```
┌──────────────────────────────────────────────────────────────┐
│ AI Conference Research Observatory · 1987→present              │
│ Filters: Venue | Year range | Topic | Country | Institution   │
└──────────────────────────────────────────────────────────────┘
┌───────────────┬──────────────────────────────────────────────┐
│ KPI cards     │ Topic Growth Streamgraph (+ forecast overlay) │
├───────────────┴──────────────────────────────────────────────┤
│ Country Choropleth        │ Institution Leaderboard (toggle)   │
├───────────────────────────┼────────────────────────────────────┤
│ Topic Similarity Network  │ Venue × Topic  /  Topic × Year     │
│                           │ Heatmap (toggle)                   │
├───────────────────────────┴────────────────────────────────────┤
│ UMAP Research Landscape (stretch)   ·  Coverage-by-year strip  │
├────────────────────────────────────────────────────────────────┤
│ Paper Explorer Table (reacts to all filters)                   │
└────────────────────────────────────────────────────────────────┘
```

The **Venue filter** is inert in Tier 1 (NeurIPS only) and becomes active in Tier 2+; the heatmap toggles between **Venue × Topic** (cross-venue comparison) and **Topic × Year** (single-venue evolution). The **coverage strip** shows metadata completeness per year so users trust thin early-era data appropriately.

**Chart inventory & types:**

| # | Component | Chart type | Reacts to | Drives (cross-filter) |
| --- | --- | --- | --- | --- |
| 1 | Topic streamgraph + forecast | stacked area / area | all filters | click topic → global topic filter |
| 2 | Citation impact (normalised) | line | all filters | brush year → global year range |
| 3 | Country choropleth | geo map | all filters | click country → global country filter |
| 4 | Institution leaderboard | bar (h.) | all filters | click bar → institution filter |
| 5 | Topic similarity network | network graph | topic/year | click node → topic filter |
| 6 | Venue × Topic / Topic × Year heatmap (toggle) | heatmap | all filters | click cell → topic (+venue/year) filter |
| 7 | UMAP landscape *(stretch)* | scatter | all filters | lasso/box select → filter |
| — | Coverage-by-year strip | small-multiple / heatstrip | venue filter | informational |
| — | KPI cards | summary | all filters | — |
| — | Paper explorer | data table | all filters | row click → detail |

Distinct types: **area, line, map, bar, network, heatmap, scatter = 7.**

**Interaction design** (technical-complexity points): one set of reactive global filters; **cross-filtering** so clicking a topic/country/cell narrows every other chart; brushing the year range updates all; hover tooltips everywhere; linked selection between the landscape scatter and the table. Shiny's reactivity makes this the natural pattern — define `reactive.Calc` for the filtered dataframe, all renderers depend on it.

---

## 8. Tech stack

- **Language:** Python 3.11+
- **App:** `shiny` (Shiny for Python) + `shinywidgets` (to embed Plotly)
- **Charts:** `plotly` / `plotly.express` — covers every type above including choropleth and network; renders reliably on shinyapps.io
- **Data:** `pandas` (or `polars`), `pyarrow` (parquet)
- **Scraping / list sources:** `requests` + `beautifulsoup4` (NeurIPS, PMLR, CVF); `openreview-py` (ICLR); ACL Anthology + DBLP via their data dumps/APIs
- **Enrichment:** OpenAlex via `pyalex` or plain `requests`; `arxiv` for abstract gap-fill
- **NLP/ML (offline):** `sentence-transformers`, `bertopic`, `umap-learn`, `hdbscan`; `statsmodels`/`prophet`/`scikit-learn` for forecasting
- **Tests:** `pytest` + GitHub Actions
- **Deploy:** `rsconnect-python` → shinyapps.io
- **Report:** LaTeX

---

## 9. Repository structure

```
COMP4010-Project2/
├── README.md                 # run instructions, live link, completeness numbers
├── plan.md                   # this file
├── requirements.txt          # split: requirements-pipeline.txt vs requirements-app.txt
├── data/
│   ├── raw/                  # scraped jsonl (cache; gitignore if large)
│   ├── interim/              # enriched + modelled
│   └── processed/            # ONLY these parquet files ship with the app
├── pipeline/                 # Stage A scripts 01–07 (see §4)
│   ├── sources/              # one adapter per venue (neurips.py, icml_pmlr.py, iclr_openreview.py, …)
│   ├── 01_scrape.py          # --venue <v>, drives the adapters
│   └── 02_…07_*.py           # venue-agnostic enrich / model / aggregate
├── app/
│   ├── app.py                # Shiny entry point
│   ├── data_loader.py        # reads processed parquet once at startup
│   ├── reactives.py          # shared filtered-data reactive
│   └── charts/               # one module per chart
├── tests/
│   ├── test_crawl_completeness.py   # §5 — the advisor's requirement
│   ├── test_data_quality.py
│   └── test_aggregations.py
├── report/main.tex
├── slides/
└── .github/workflows/ci.yml  # runs pytest on push
```

Keep `requirements-app.txt` minimal (shiny, shinywidgets, plotly, pandas, pyarrow) so the deploy bundle stays small and well under 1 GB.

---

## 10. Milestones & timeline (26/05 → 07/06)

Data and app tracks run **in parallel** — the app team scaffolds against mock parquet while the data team crawls.

| Phase | Dates | Owner(s) | Done when… |
| --- | --- | --- | --- |
| **0. Setup & scope lock** | 26–27/05 | All | Repo skeleton, envs, tiers frozen, proposal framing revised per advisor |
| **1. NeurIPS crawl (full history) + completeness test** | 27–29/05 | Data eng | `pytest` green for **all NeurIPS years 1987→latest** in CI ← *critical path* |
| **2. Enrichment** | 29–31/05 | Enrich/ML | `enriched.parquet` built via OpenAlex bulk pulls; match-rate + coverage reported |
| **2'. Tier-2 adapters (parallel, if Tier 1 green)** | 30/05–01/06 | Data eng | ICML (PMLR) + ICLR (OpenReview) adapters pass completeness test |
| **3. ML/analytics** | 31/05–02/06 | Enrich/ML | topics, network, forecast, normalised impact → processed parquet |
| **3'. App scaffold (parallel)** | 28/05–02/06 | Frontend | layout + filters + ≥3 charts on mock data |
| **4. Wire real data + remaining charts** | 02–04/06 | Frontend + All | all core charts live with cross-filtering; venue filter active if Tier 2 done |
| **5. Deploy + polish** | 04–05/06 | Integration | live on shinyapps.io, cold-start OK, styled |
| **6. Report + slides + rehearse demo** | 05–07/06 | All | 6-pg LaTeX report, slides, 8-min demo rehearsed |

**MVP (must-have by 04/06):** Tier 1 (full NeurIPS history) + 5 charts + filters + cross-filter + deployed. **Then in order:** Tier 2 (ICML+ICLR) → forecast overlay + UMAP landscape → Tier 3 (CVPR/ACL). **Gate rule:** never start a new tier until the current one's completeness test is green and committed.

---

## 11. Task allocation

| Member | Primary role | Owns |
| --- | --- | --- |
| **Pham Dinh Hieu** (repo owner) | Integration & deploy | repo hygiene, CI, shinyapps.io deploy, README, glue |
| **Tran Ho Chi Thanh** | Data engineering | venue adapters (NeurIPS first, then ICML/ICLR), **completeness test**, data-quality tests |
| **Nguyen Tuan Minh** | Enrichment & ML | OpenAlex bulk matching, BERTopic, forecasting, network/normalisation, coverage report |
| **Cao Pham Minh Dang** | Dashboard / frontend | Shiny app, charts, cross-filter, styling |

Everyone contributes to the report and rehearses one demo segment. Pair across track boundaries during Phase 4.

---

## 12. Testing strategy

- **Completeness** (§5) — index↔detail and index↔ground-truth, in CI.
- **Data quality** — non-null titles, valid years, citations ≥ 0, country codes valid, no dup ids, match-rate above a floor.
- **Aggregation** — unit tests on the functions feeding each chart (e.g. topic-year counts sum to total papers).
- **App smoke test** — app imports, loads parquet, builds each figure without error.

---

## 13. Deployment (shinyapps.io free tier)

1. `pip install rsconnect-python`; configure account token.
2. Ship only `app/` + `data/processed/*.parquet` + `requirements-app.txt`.
3. `rsconnect deploy shiny app/ --name <acct> --title ai-research-observatory`.
4. Verify cold start < ~10 s and memory < 1 GB; if tight, drop abstracts from shipped parquet and pre-aggregate harder.
5. Put the **live URL in the README and slide 1**; have a **local fallback** ready in case the demo machine has no internet or the app is asleep (apps sleep when idle — open it a few minutes before presenting).

---

## 14. Risk register

| Risk | Likelihood | Mitigation |
| --- | --- | --- |
| **Scope creep (too many venues)** | **High** | Strict tier gating: no new venue until current tier's completeness test is green; Tier 1 alone is a full project |
| Sparse metadata in early years (no abstracts/affiliations) | High | arXiv/title-only fallback for topics; "unknown" geo buckets; coverage-by-year indicator discloses it |
| OpenAlex match rate low | Med | bulk source+year pull, then DOI→title+year→arXiv fallback; report rate; unmatched papers still appear |
| Enrichment volume (tens of thousands of papers) | Med | bulk pulls over per-paper lookups; on-disk cache; resume per (venue, year) |
| Network graph too dense | High | top-N topics, edge-weight threshold, min co-occurrence; not raw paper graph |
| Forecast over-read | Med | full-history data helps; still show CIs + caveat; treat as illustrative |
| Bundle > 1 GB / RAM > 1 GB | Med | drop abstracts, ship aggregated parquet only, no models in app |
| Source HTML/API changes (varies by venue) | Low–Med | one adapter per venue isolates breakage; cache raw responses; completeness test catches it |
| API rate limits | Med | polite pool `mailto=`, batching, backoff, on-disk cache |
| Demo fails live | Low | rehearse; local fallback; wake app early |

---

## 15. How this plan maps to the grading rubric

| Rubric criterion | How we satisfy it |
| --- | --- |
| **Visualization & design / storytelling** | 7 chart types, coherent four-decade narrative (neural nets → SVM era → 2012 deep-learning → transformers/LLMs/diffusion/agents), KPI framing |
| **Technical complexity** | venue-adapter architecture, full-history multi-venue crawl, cross-filtering & linked views, two-stage pipeline, network + UMAP + forecasting |
| **ML & analytics (5120)** | BERTopic, time-series forecasting w/ CI, similarity network, normalised impact |
| **Reproducibility & code quality** | CI-run completeness test (advisor's ask), modular pipeline, parquet artifacts, README |
| **Presentation & demo** | deployed live app + local fallback, rehearsed 8-min demo, clear story per chart |

---

## 16. Definition of done

- [ ] Completeness test green for **all NeurIPS years 1987→latest** in CI (Tier 1)
- [ ] Tier 2 (ICML + ICLR) adapters pass completeness, or explicitly deferred with reason
- [ ] `data/processed/*.parquet` + `reports/coverage.csv` built end-to-end and reproducible from scripts
- [ ] ≥ 5 charts (we target 7), ≥ 3 types (we target 7), all cross-filtering; coverage-by-year indicator present
- [ ] One ML component visibly used in the dashboard (forecast overlay) + one in the report (normalised impact / topics)
- [ ] App deployed to shinyapps.io, URL in README + slide 1
- [ ] 6-page LaTeX report + slides + rehearsed demo
- [ ] README: setup, run, live link, per-venue completeness numbers, coverage gradient, known limitations