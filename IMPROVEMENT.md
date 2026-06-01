# IMPROVEMENT PLAN — AI Conference Research Observatory

> Action plan responding to advisor/reviewer feedback (written 2026-06-01, final submission 2026-06-07 → **~6 days**).
> This document is grounded in an audit of the live repo and `data/processed/*.parquet`, not assumptions.

---

## 0. Feedback received

1. **Citations are incomplete** → *remove the citation metric from the dataset and the dashboard.*
2. **Institutions are mostly "Unknown"** → *propose a way to recover the full institution list for every paper.*
3. **Some panels are not interpretable** → the *Topic intensity by year* heatmap is almost all white; the *Topic similarity network* is a grey screen (nothing shown).
4. **Make the visuals more exciting** and show the deep + practical technical side — e.g. turn the geographic distribution into a **3D Earth**. (Brainstorm more options.)

---

## 1. Diagnosis — what the data actually shows (evidence)

Audited `data/processed/papers.parquet` (30,602 papers, NeurIPS 1987→2025, 16 curated topics):

| Symptom | Measured value | Root cause |
| --- | --- | --- |
| Citation metric thin | **8.7%** of papers have `citation_count > 0` (2,648 rows; `citation_source='none'` for 27,952) | OpenAlex matched only 2,650 papers, and Crossref/DOI is empty (`doi` non-null = **0.1%**). Every citation-based view is computed on <9% of the data. |
| Institution "Unknown" | **91.6%** of `institutions_text` = `"Unknown"` (28,034 / 30,602); same for `countries_text` | Enrichment used **per-paper OpenAlex title search** (`search_openalex`, `per-page=1`, similarity ≥ 0.86). Only 2,650 matched (`openalex_match_method='title_year'`); the rest fell back to `["Unknown"]` in `extract_enrichment`. |
| Heatmap mostly white | Topic×Year cell counts span **1 → 1,245** (median 16) | `make_topic_heatmap` plots **raw counts on a linear scale**. Recent high-volume cells saturate the scale; the other ~95% of cells map to near-white (`PINK_SCALE` is white-ish below ~24% of max). |
| Network "grey screen" | Top topic = 4,464 papers | In `make_topic_network`, `sizes.append(16 + count * 2)` → a single node becomes **~8,944 px**. All 16 nodes are enormous overlapping blobs; the canvas reads as one solid mass = "nothing shown". Edges (75 rows in `topic_edges.parquet`) are fine; the **node sizing** is the bug. |

**Key insight:** items 1 and 2 share a single upstream cause — the **OpenAlex enrichment match rate is only ~8.6%**. Fixing enrichment simultaneously (a) restores institutions/countries and (b) *would* restore citations if we chose to keep them. Per the feedback we will **remove citations regardless**, but the enrichment fix is the backbone of this plan.

---

## 2. Workstreams

Priority tags: **P0** = required before submission · **P1** = high value, do if P0 lands early · **P2** = stretch/polish.

---

### WS-1 (P0) — Remove the citation metric from dataset and dashboard

**Why:** 8.7% coverage makes every citation view misleading (91% of papers plot as ~0). Removing it is the honest, defensible call and is exactly what the advisor asked for.

> ⚠️ **Confirm interpretation with the team.** We read "citation" as the **scholarly citation-count metric** (the `citation_count` field + the impact chart + the coverage KPI). If the feedback instead meant *data-source attribution text* ("citation" as in references to OpenAlex/NeurIPS), the action is the opposite — complete the attributions, don't delete them. This plan assumes the former.

**Dashboard changes (`app/`):**
- Delete the **"Age-normalized citation impact"** panel: remove `output_widget("citation_impact")` from `app.py` and the `citation_impact()` renderer; delete/retire `app/charts/impact.py`.
- Remove the **"Citation Coverage"** KPI card (`kpi_citations`) from the KPI grid in `app.py`.
- Remove the **citation toggle** on the institution leaderboard: drop the `input_radio_buttons("institution_metric", …)` ("Output" vs "Citations") and make `make_institution_leaderboard` output-only (papers count). Edit `app/charts/institutions.py` to drop the `citation_count` aggregation and the `metric` branch.
- Drop `citation_impact` from `data_loader.REQUIRED_FILES` so the app stops loading `citation_impact.parquet`.
- Remove the `subtle` status pill "30,602 papers" hard-coded string if it implies a frozen number; make it reactive or delete it.

**Pipeline / dataset changes (`pipeline/`):**
- Stop shipping citation columns in `07_aggregate_for_app.py`: remove `citation_count`, `citation_source`, `doi`, `doi_source` from `papers.parquet`, and stop writing `citation_impact.parquet`.
- Drop `02b_enrich_doi_citations.py` from the documented pipeline run order (README) — keep the file but mark it deprecated, or delete it.
- Remove `citation` references from `pipeline/sample_data.py` so the auto-generated sample matches the new schema (otherwise the fallback sample re-introduces the column).
- Update `tests/` that assert on `citation_count` (e.g. `test_data_quality`, `test_aggregations`).

**Replace the freed panel** (don't leave a hole) — slot in one of the WS-3/WS-4 visuals (recommended: the **topic-share heatmap** moves into the hero row, and the **3D globe** or **topic Sankey** takes the vacated impact slot).

**Acceptance:** no string "citation" appears in any rendered panel/KPI; `papers.parquet` has no citation columns; tests pass; the layout has no empty cell.

---

### WS-2 (P0/P1) — Recover full institution (and country) coverage for every paper

**Goal:** raise institution coverage from **8.4%** toward **>90%**, with an honest per-year coverage indicator for whatever remains unknown.

We propose a **three-tier strategy**, cheapest/highest-yield first. Do Tier A now (P0); Tier B if time (P1); Tier C is the "deep technical" showcase (P1/P2).

#### Tier A — OpenAlex **bulk source pull** + robust matching (P0, biggest single win)
The current code does *per-paper* title search (slow, fragile, `per-page=1`). The repo **already has** the right tool unused: `enrich_from_bulk()` / `--bulk-source-id` in `02_enrich_openalex.py`.

- Pull **all** NeurIPS works once via `works?filter=primary_location.source.id:<Sxxx>` (paginate with `cursor`, `per-page=200`). NeurIPS OpenAlex source id ≈ `S4306420609` — **verify** against the API before running.
- Match crawled papers to OpenAlex works by, in order: **(1) DOI**, **(2) normalized title + exact year**, **(3) title + year + author-surname overlap** to break ties. Lower the title threshold slightly (0.80) *only when* author overlap confirms.
- Each OpenAlex work already carries `authorships[].institutions[].display_name`, `…institutions[].ror`, and `…country_code` — write these into `institutions_text` / `countries_text`, plus a normalized **ROR id** and a clean **country ISO-2**.
- **Record match method + score per paper** and roll up a per-(venue, year) match rate into `reports/coverage.csv` (already wired to the coverage strip).

> OpenAlex coverage of NeurIPS is strong for recent years and thins pre-~2000. Expect this tier alone to take coverage from ~8% to ~70–85% concentrated in 2005→2025.

#### Tier B — Affiliation extraction from the paper PDFs (P1, fills the gap OpenAlex misses)
For papers still "Unknown" after Tier A (older years, OpenAlex misses), parse affiliations from the source itself. Every NeurIPS paper has a `pdf_url` (already in the raw records).
- Use **GROBID** (`processHeaderDocument`) to extract `author → affiliation → organization/country` from the PDF header. GROBID is the standard, reliable tool for this; run it in the offline pipeline (Stage A), never in the app.
- Lightweight fallback if GROBID is too heavy in the timeline: download the PDF first page, extract text (`pdfminus.six`/`pypdf`), and regex/NER the affiliation block. Lower quality but better than "Unknown".
- Normalize extracted strings to canonical institutions via the **ROR API** (`api.ror.org/organizations?affiliation=…`) so "MIT", "Massachusetts Inst. of Technology", "M.I.T." collapse to one ROR id with a country.

#### Tier C — Cross-source reconciliation (P2, robustness + report credibility)
- **Semantic Scholar** (`/graph/v1/paper` with `authors.affiliations`) and **Crossref** affiliations as a third signal; take majority vote across sources.
- **DBLP** for author disambiguation (stable author keys) to merge affiliation history per author.

#### Cross-cutting: honesty about what's left
- Keep an explicit `institution_coverage` flag per paper and a **coverage-by-year strip** (already specified in IDEA.md §5). Showing *where* data thins out is a rubric win, not a weakness.
- In the country/institution panels, keep an **"Unknown" bucket visible but separated** (or filtered with a clear note), never silently dropped — except on the map where it has no geometry.

**Recommended path for the deadline:** **Tier A now** (one script run, already coded), then **Tier B (GROBID) on the residual** if Tier A lands by ~06/03. Report the final coverage % prominently — it directly answers the advisor.

**Acceptance:** institution coverage reported per year; overall known-institution share documented in README; `make_institution_leaderboard` shows real institutions for the filtered range, not a giant "Unknown" bar.

---

### WS-3 (P0) — Make the broken panels interpretable

#### 3a. Topic intensity heatmap — fix the "all white" (`app/charts/heatmap.py`)
The chart conflates "topic intensity" with "raw volume", and raw volume is dominated by 2023–2025. Two complementary fixes; ship at least the first:

1. **Show topic share per year (column-normalized), not raw counts.** For each year, plot each topic's **% of that year's papers**. Values land in ~0–35%, evenly spread, and the panel finally tells its intended story: *the topic mix shifting across eras* (SVM era → 2012 vision surge → 2018+ NLP/LLM rise). This is the single most important fix.
2. **Offer a raw-count mode on a log color scale** (`z = log1p(count)`) via a small toggle, for users who want absolute volume.
3. Swap `PINK_SCALE` for a perceptually uniform scale with contrast at the low end (e.g. `Viridis`/`Magma`, or a custom scale whose 0–0.2 band is clearly non-white). Add per-cell text labels for small matrices.
4. Sort rows by recent-era prevalence (or let the topic filter reorder) so the eye lands on what's growing.

#### 3b. Topic similarity network — fix the "grey screen" (`app/charts/network.py`)
**Root cause: node size = `16 + count*2`** → up to ~8,944px. Fixes:
1. **Scale node area sub-linearly and cap it:** `size = 12 + 34 * sqrt(count / max_count)` (range ~12–46px). This alone makes the network appear.
2. **Make edges legible:** width ∝ `weight`, darker color, and only draw edges above a weight threshold / top-N per node so the layout isn't a hairball.
3. Use a deterministic, readable layout (`spring_layout` with tuned `k`, fixed `seed`) and label only nodes above a size threshold to avoid overlap.
4. **Consider replacing the force graph with a chord diagram / co-occurrence matrix** for 16 topics — with so few nodes a chord diagram (or the topic-share heatmap's cousin) is clearer than a force layout and looks more polished.
5. Verify the panel actually has non-zero height in CSS; render an explicit "no co-occurrence above threshold" message instead of an empty canvas when a filter yields nothing.

**Acceptance:** at the default unfiltered view the heatmap shows graded color across all eras (not white), and the network shows distinct, sized, labeled nodes with visible weighted edges.

---

### WS-4 (P1) — "Exciting" visuals showing the deep + practical technical side

The brief rewards technical complexity + storytelling. Below, the headline 3D Earth plus a brainstormed menu — **pick 1 headline + 1–2 supporting**, don't build all.

#### 4a. 3D rotating globe for geography (headline — replaces flat choropleth)
Three implementation tiers, ranked by effort:
- **Easiest, ships today — Plotly orthographic globe.** Change `make_country_map` from `px.choropleth` to `go.Scattergeo`/`go.Choropleth` with `projection_type="orthographic"`. It's draggable/rotatable, reads as a 3D Earth, and needs no new dependency. Add `frames` + a play button to **rotate/auto-spin and animate by year** ("watch NeurIPS go global").
- **More impressive — deck.gl globe via `pydeck`.** A true 3D globe with **extruded columns per country** (height ∝ paper count) and **great-circle arcs for cross-country co-authorship**. Embed in Shiny via an HTML/iframe widget. Higher wow factor; budget time for the Shiny embedding.
- **Showcase — `globe.gl`/Three.js** custom component: spinning Earth with arcs and glowing nodes. Highest effort; only if WS-1/2/3 are done.

Recommendation: **ship the Plotly orthographic globe now**, upgrade to pydeck columns+arcs if time allows. The arcs (institution/country collaboration) are the "deep + practical" signal — they visualize the collaboration network on the planet.

#### 4b. Brainstorm menu (other high-impact, low-cliché options)
| Idea | What it shows | Tech | Effort |
| --- | --- | --- | --- |
| **Topic-evolution Sankey / alluvial** | How research "flows" between eras (e.g. Kernel→Deep Learning→Transformers) | Plotly `go.Sankey` | Low–Med |
| **Animated streamgraph "race"** | Topic volumes growing year by year with a play head | Plotly frames | Low |
| **3D research landscape (UMAP)** | Papers as points in 3D embedding space, color by topic, z = year → a literal "mountain range of ideas" | precompute UMAP offline → `go.Scatter3d` | Med |
| **Collaboration arc globe** (= 4a deck.gl) | Country↔country co-authorship as arcs on the Earth | pydeck/deck.gl | Med–High |
| **Topic co-occurrence chord** | Cleaner alternative to the force network | Plotly/holoviews | Low |
| **Scrollytelling era timeline** | Annotated narrative ("2012: deep learning takeoff") synced to charts | Shiny + scroll events | Med |
| **Calendar/era heat-strip** | Decade-banded small multiples of topic intensity | Plotly | Low |

#### 4c. Make every panel "deep + practical"
- **Cross-filtering** (already in IDEA.md): click a topic/country/node → all panels narrow. This is the biggest perceived-sophistication lever and is mostly wiring in Shiny reactives.
- Rich hover tooltips, smooth transitions, and a coherent dark "observatory" theme so the 3D globe pops.

**Acceptance:** at least one genuinely 3D/animated panel; geography is a rotatable globe; one cross-filter interaction works end-to-end.

---

## 3. Suggested order of work (6 days, 2026-06-01 → 06-07)

| Day | Focus | Deliverable |
| --- | --- | --- |
| **06-01 (Mon)** | WS-1 remove citations end-to-end; WS-3a heatmap → topic-share; WS-3b network node-size fix | Dashboard has no misleading citation views; both broken panels readable. **Lowest-effort, highest-credibility wins land first.** |
| **06-02 (Tue)** | WS-2 Tier A: run OpenAlex **bulk** enrichment + robust DOI/title/author matching; rebuild parquet | Institution/country coverage jumps; coverage-by-year reported |
| **06-03 (Wed)** | WS-4a Plotly orthographic globe + year animation; re-slot the freed citation panel | Geography is a 3D rotating Earth |
| **06-04 (Thu)** | WS-2 Tier B (GROBID on residual) *or* WS-4 second visual (Sankey / UMAP 3D); cross-filtering | Coverage >90% *or* a second exciting panel |
| **06-05 (Fri)** | Polish: theme, tooltips, coverage strip, README + limitations; deck.gl globe upgrade if ahead | Cohesive, deployable app |
| **06-06–07** | Report + slides + rehearse; freeze | Submission |

**Gate rule:** WS-1 and WS-3 (Day 1) are non-negotiable and cheap — do them before any new feature. WS-2 Tier A is the backbone. Everything in WS-4 beyond the Plotly globe is upgrade, not requirement.

---

## 4. Concrete change list (file-by-file)

**Remove citations**
- `app/app.py` — delete `citation_impact` widget + renderer; delete `kpi_citations` card + renderer; delete `institution_metric` radio; un-hardcode the papers-count pill.
- `app/charts/impact.py` — delete (or stub) the module.
- `app/charts/institutions.py` — drop `citation_count` agg and `metric` branch; output-only leaderboard.
- `app/data_loader.py` — remove `"citation_impact"` from `REQUIRED_FILES`.
- `pipeline/07_aggregate_for_app.py` — drop citation columns from `papers.parquet`; stop writing `citation_impact.parquet`.
- `pipeline/sample_data.py` — remove citation fields from the sample schema.
- `README.md` — remove `02b_enrich_doi_citations.py` from the run order; note citations intentionally excluded.
- `tests/` — update assertions referencing `citation_count`.

**Institutions**
- `pipeline/02_enrich_openalex.py` — make **bulk source pull the default**; add DOI→title+year→author-overlap matching; verify NeurIPS source id; emit `ror`, ISO-2 country, `institution_coverage` flag, per-year match rate.
- `pipeline/03_clean_normalize.py` / `07_aggregate_for_app.py` — carry the new institution/country/coverage fields through.
- *(Tier B)* new `pipeline/02c_affiliations_grobid.py` — PDF-header affiliation extraction + ROR normalization for residual "Unknown".
- `reports/coverage.csv` + coverage strip — surface the new coverage numbers.

**Interpretable panels**
- `app/charts/heatmap.py` — column-normalized topic share (+ optional log raw-count mode); higher-contrast colorscale; cell labels.
- `app/charts/network.py` — `size = 12 + 34*sqrt(count/max)`; weighted/thresholded edges; readable layout; empty-state message. *(Optional: swap to chord diagram.)*

**Exciting visuals**
- `app/charts/geography.py` — orthographic `Scattergeo`/`Choropleth` globe + year-frame animation; *(stretch)* pydeck columns + collaboration arcs.
- *(optional)* `app/charts/sankey.py` / `landscape3d.py` — new panels per WS-4b.
- `app/charts/theme.py` — dark "observatory" theme so 3D panels pop.

---

## 5. Acceptance criteria (definition of done for this round)

- [ ] No citation-based metric, KPI, chart, or column remains in the app or `papers.parquet`; tests green.
- [ ] Documented institution-coverage % per year, materially improved from 8.4% (target >90% via Tier A+B, or honestly reported if lower).
- [ ] Heatmap shows graded color across all eras (topic share); network shows distinct sized/labeled nodes with weighted edges.
- [ ] Geography renders as a rotatable 3D globe; at least one animated/3D panel and one working cross-filter.
- [ ] Coverage-by-year indicator visible; README updated with new sources, coverage numbers, and limitations.
- [ ] No empty/placeholder panels; cohesive theme.

---

## 6. Open questions for the team / advisor
1. **Citation interpretation** — confirm we should remove the scholarly citation-count metric (our reading), not data-source attributions. (§WS-1)
2. **Institution effort ceiling** — is Tier A (OpenAlex bulk, ~85% modern coverage) enough, or do we invest in GROBID (Tier B) for near-100% including pre-2000?
3. **3D globe fidelity** — Plotly orthographic (ships today) vs deck.gl/pydeck (more wow, more risk)?
4. **Scope** — stay Tier-1 NeurIPS and polish, or still attempt ICML/ICLR? (Recommend: polish NeurIPS; the fixes above raise quality more than a second venue.)
