# IMPROVEMENT.md — Making the **code & dashboard** excellent on every rubric criterion

> Scope: **only the Application block** of [RUBRIC.md](RUBRIC.md) — criteria **2.6–2.14**
> (the code and the dashboard itself). Deployment, report, slides, proposal, and
> presentation/demo criteria are deliberately **out of scope** here.
> Written 2026-06-05 from a live inspection of the code, data, tests, and git history.
> Companion: [DATA_IMPROVEMENT.md](DATA_IMPROVEMENT.md) (data coverage).

---

## 0. TL;DR

The dashboard is already **Good across the board** and **Excellent on chart count**. The
code is clean, the topic model is solid (review-flag rate down to **4.7%**), and affiliation
coverage is ~90%+ with honest provenance. To reach **Excellent on every code/dashboard
criterion**, close five concrete gaps — ranked by weight × distance-to-excellent:

| # | Gap | Rubric | Weight | Effort |
| --- | --- | --- | :--: | --- |
| 1 | **No cross-filtering / brushing / linked views** (only dropdown filters) | 2.8 | **6%** | 0.5–1 day |
| 2 | **Shallow ML** — forecast is a single linear `polyfit`, no validation | 2.10 | **6%** | 0.5 day |
| 3 | **Single-author commit history** (all 3 commits, one person) | 2.14 (+2.13) | **4%** | ongoing |
| 4 | **Unpinned dependencies** + minor code-quality nits | 2.12 | **3%** | 0.25 day |
| 5 | **No Shiny modules; possible hidden-tab recompute; filter substring bug** | 2.11 | **4%** | 0.5 day |
| 6 | **8 "creative" panels risk clutter over insight** | 2.6 | 6% | 0.5 day |

**Application-block standing ≈ 29.4 / 37 (~79%, "Good").** The work below lifts it toward 37/37.

---

## 1. Scorecard — Application block (2.6–2.14)

Levels: **E**xcellent (100%) · **G**ood (80%) · **S**atisfactory (60%) · **N**eeds-improvement (≤40%).

| # | Criterion | W | Current | Evidence | Target |
| --- | --- | :--: | :--: | --- | :--: |
| 2.6 | Visualization quality & design | 6% | **G** | Clean Plotly, consistent rose theme, hovertemplates, CI bands, empty-state guards — but 8 experimental panels risk clutter | E |
| 2.7 | Chart requirements met | 3% | **E** | 20+ panels, 7+ chart types — far exceeds ≥5/≥3 | E |
| 2.8 | Interactivity | 6% | **G** | Filters + tooltips + topic chips + reset, **but zero chart-click/cross-filter/brush/linked-view code** | E |
| 2.9 | Technical complexity | 5% | **G→E** | Two-stage pipeline, multi-source affiliation waterfall, completeness tests, network/forecast | E |
| 2.10 | ML / analytics | 6% | **G** | Topic model good (TF-IDF cosine + keyword + softmax); forecast is bare linear fit, no back-test | E |
| 2.11 | Proper use of Python Shiny | 4% | **G** | `reactive.Calc` cached correctly; **no modules**, repetitive boilerplate, filter substring quirk | E |
| 2.12 | Reproducibility & code quality | 3% | **G** | 22 tests pass, clear docs; **dependencies unpinned** | E |
| 2.13 | Repository organization & docs | 2% | **G** | Logical structure, good README; **3-commit history** ("meaningful" not met) | E |
| 2.14 | Teamwork & collaboration | 2% | **N** | `git shortlog` → **all commits one author** | E |

---

## 2. What's already excellent (protect these)

- **Chart richness (2.7 = E).** [app/app.py](app/app.py) wires ~20 panels: KPI + research-pulse
  cards, 8 creative views, topic growth/heatmap/momentum, choropleth, Sankey, network,
  institution leaderboard, coverage strip, provenance, forecast focus, and a filterable Paper Explorer.
- **Clean chart code.** Every chart module guards empty input (`empty_figure(...)`), uses a
  shared theme (`apply_research_layout`), and sets `hovertemplate`/`hovertext` — e.g.
  [app/charts/forecast.py](app/charts/forecast.py), [app/charts/network.py](app/charts/network.py).
- **Idiomatic reactive core.** A single cached `filtered_papers()` `reactive.Calc`
  ([app/app.py](app/app.py#L239-L247)) fans out to every output — the right Shiny pattern.
- **Solid topic model.** [pipeline/04_topic_modeling.py](pipeline/04_topic_modeling.py) blends
  TF-IDF cosine to topic prototypes with curated keyword scores + softmax confidence; only
  **4.7%** of papers are review-flagged and just 10 land in "General / Other ML".
- **Honest data layer.** `papers.parquet` ships `affiliation_source` / `affiliation_confidence`
  / `*_known` and already **drops `abstract`** (6.3 MB, lean). 22 tests green in CI.

Do not regress these while fixing the gaps below.

---

## 3. Detailed fixes

### 3.1 — Cross-filtering, brushing & linked views  ·  **2.8 (6%)**, the biggest code gap

A grep of `app/` finds **no** `on_click` / `click_data` / `selected_data` / `register_widget`
handlers. Interactivity today = global dropdowns + 5 topic chips + reset. The "Excellent"
wording names exactly what's missing: *"filtering, brushing, cross-filtering, linked views, tooltips."*

The fix is cheap because the reactive backbone already fans out: clicks just need to **write
into the existing filter inputs**, and every panel updates through `filtered_papers()`.

**Do:**
1. Register Plotly selection callbacks via `shinywidgets`. Pattern:
   ```python
   from shinywidgets import render_widget, reactive_read
   @reactive.Effect
   def _country_click():
       pts = reactive_read(country_map.widget, "click_data")
       if pts:
           ui.update_selectize("country", selected=pts["points"][0]["location"])
   ```
2. **Cross-filter targets** (each click sets a global filter input):
   - choropleth country → `country`
   - institution bar → `institution`
   - topic network node / heatmap cell / streamgraph band → `topic`
3. **Brushing:** box-select on the topic-growth or heatmap x-axis → update the `year_range` slider.
4. **Linked views:** selecting a point in "Paper Universe" highlights the matching Paper Explorer
   row (and vice-versa) — true linked selection.
5. Make `reset_filters` also clear any click-driven selections.

**Acceptance:** clicking a country/topic/institution/cell narrows every panel + the table; a
year brush updates the slider; scatter↔table selection is linked; reset clears all.

---

### 3.2 — Deepen the ML / analytics  ·  **2.10 (6%)**

The topic model is already strong. The weak link is the forecast:
[pipeline/06_forecast.py](pipeline/06_forecast.py#L22) is a single `np.polyfit` degree-1 line
with a residual-std CI. "Excellent" rewards a model that *goes beyond basic* and is
*meaningfully embedded in the analytical workflow*. Pick at least one upgrade:

1. **Real time-series forecast (½ day).** Swap the linear fit for `statsmodels` Holt/ETS
   exponential smoothing or `SARIMAX` (already a pipeline dep), keep the 95% CI you plot, and
   **back-test on held-out recent years** to report a MAPE. One validation number turns "trend
   line" into "validated forecast," and it's defensible in Q&A.
2. **Topic-emergence / inflection detection.** Auto-flag breakout topics (LLMs, diffusion,
   agents) from second-derivative / changepoint of their growth curves and surface the flag in
   the momentum panel — makes the analytics *interactive*, not a static overlay.
3. **Semantic topics (stretch, ½–1 day).** [DATA_IMPROVEMENT.md §5](DATA_IMPROVEMENT.md) specs
   replacing TF-IDF with `sentence-transformers` (MiniLM/SPECTER2) embeddings → better labels
   *and* a real UMAP "research landscape" scatter (upgrades the current TruncatedSVD
   `paper_universe`, which threw a divide-by-zero in tests).

**Acceptance:** at least one substantive upgrade shipped; a validation metric computed and
shown/logged; the choice is reflected in `reports/` so it's auditable.

---

### 3.3 — Tighten Shiny usage  ·  **2.11 (4%)**

`reactive.Calc` caching is correct (Good). Three steps toward Excellent ("idiomatic… modules…
efficient reactivity with no redundant recomputation"):

1. **Add Shiny modules.** [app/app.py](app/app.py#L424-L462) repeats ~20 near-identical
   `@output / @render_widget` blocks. Extract a `chart_panel` / `creative_panel` module so each
   panel is declared once — the rubric explicitly mentions "modules."
2. **Stop hidden-tab recompute.** The 8 creative widgets each call their `make_*` on every
   filter change. Confirm inactive `navset_tab` panels are suspended when hidden (or gate them
   behind the active tab / `@reactive.event`) so you don't recompute 8 heavy figures the user
   can't see.
3. **Fix the filter substring quirk.** [app/filters.py](app/filters.py#L6-L9) matches
   country/institution with `str.contains(token, regex=False)` — selecting "Microsoft" also
   returns "Microsoft Research", and short tokens can over-match unrelated names. Match against
   the comma-split token set (exact membership) instead of a raw substring. (Also consider an
   "include secondary topics" option, since the topic filter currently keys on primary only.)

**Acceptance:** ≥1 module in use; no recompute of hidden panels; filters match exact tokens; tests still green.

---

### 3.4 — Reproducibility & code quality  ·  **2.12 (3%)**

22 tests pass and the app runs from clear README steps (Good). The one explicit miss is
*"pinned dependencies."*

**Do:**
1. Pin exact versions in **both** `requirements-app.txt` and `requirements-pipeline.txt`
   (`pip freeze` in the working venv → `shiny==x.y.z`, `plotly==…`, `pandas==…`, `pyarrow==…`,
   `networkx==…`, plus the pipeline set). Keep the app/pipeline split so the app env stays small.
2. Pin Python (CI already targets 3.11 — note it in README, optionally `.python-version`).
3. Re-run CI to confirm the pinned set passes all 22 tests.
4. *(Minor code-quality)* the app silently falls back to **sample** data when processed files
   are missing ([app/data_loader.py](app/data_loader.py#L28-L31)) — keep it for dev, but log a
   visible warning so a broken data dir can't masquerade as real results.

**Acceptance:** both requirements files fully pinned; CI green; README states the Python version.

---

### 3.5 — Repository history & teamwork  ·  **2.13 (2%) + 2.14 (2%)**

`git log` = **3 commits, all one author** (`Pham Dinh Hieu`). 2.14 "Excellent" needs *"balanced
contribution evident in commit history"*; 2.13 wants *"meaningful commit history."* As-is this
is the clearest Needs-Improvement in the block. History can't be honestly back-dated — build it
forward, starting now:

1. Each of the four members commits their own real work under their **own name/email**.
2. Small, descriptive commits (`feat: cross-filter on country map`, `fix: exact-match filters`)
   instead of "Initial Commit" / "Done scrawl data".
3. Use `Co-authored-by:` trailers for pairing so both names appear.
4. Add a short **task-allocation / CONTRIBUTORS** section to the README (the mapping in
   [PLAN.md](PLAN.md#L320-L329) already exists — surface it).
5. Verify with `git shortlog -sne` that all four appear with non-trivial counts.

**Acceptance:** `git shortlog -sne` shows all four members; descriptive messages; README documents ownership.

---

### 3.6 — Curate the visual lab for insight  ·  **2.6 (6%)**

Visual quality is already Good, but eight experimental panels (galaxy, river, race, bloom,
orbit, weather, universe, DNA) risk reading as *clever over clear* — the opposite of "effective
charts; strong visual storytelling."

**Do:**
1. Give every visible chart a one-line **"what to read here" caption + the takeaway** (some
   panel subtitles already do this — make it universal).
2. Demote the weakest 2–3 creative views into a collapsed "experimental" area so the default
   view stays focused; keep the strong ones (e.g. race, river) front-and-center.
3. Sanity-check readability at small sizes (legends, label overlap, color contrast on the rose
   theme) and the `paper_universe` divide-by-zero edge case.

**Acceptance:** every visible chart has a clear takeaway; no panel is cluttered by default; no runtime warnings.

---

### 3.7 — Push technical complexity to Excellent  ·  **2.9 (5%)**

Already strong (Good→E). To lock Excellent, make the depth *visible in the app*, not just the
pipeline: surface the completeness/coverage story and the affiliation-source mix as a first-class
panel (the data exists in `coverage.parquet` / `affiliation_source_year.parquet`), and ensure the
cross-filtering from §3.1 demonstrates the "robust data pipeline → linked interactive analytics"
end-to-end. No new pipeline work required — it's about exposing what's already built.

---

## 4. Prioritized roadmap (by weight × gap)

| Pri | Task (§) | Fixes | ~Weight | Effort |
| :--: | --- | --- | :--: | --- |
| **1** | Cross-filtering / brushing / linked views (§3.1) | 2.8 | ~1.2% | 0.5–1 day |
| **2** | Deepen ML: real forecast + back-test (§3.2) | 2.10 | ~1.2% | 0.5 day |
| **3** | Shiny modules + no hidden recompute + exact-match filters (§3.3) | 2.11 | ~0.8% | 0.5 day |
| **4** | Balanced commit history + CONTRIBUTORS (§3.5) | 2.13 + 2.14 | ~1.2% | ongoing |
| **5** | Pin dependencies + data-fallback warning (§3.4) | 2.12 | ~0.6% | 0.25 day |
| **6** | Curate visual lab; per-chart takeaways (§3.6) | 2.6 | ~1.2% | 0.5 day |
| **7** | Surface coverage/provenance panel (§3.7) | 2.9 | ~1.0% | 0.25 day |

---

## 5. "Excellent everywhere" — code & dashboard checklist

- [ ] **2.6** Every visible chart has a clear takeaway; no clutter; no runtime warnings.
- [ ] **2.7** ≥5 charts / ≥3 types, all purposeful — *already met; keep it.*
- [ ] **2.8** Click-to-cross-filter (country/topic/institution/cell), year-brush → slider, linked scatter↔table, reset clears all.
- [ ] **2.9** Pipeline depth visible in-app (coverage/provenance panel) + end-to-end linked interaction.
- [ ] **2.10** Validated time-series forecast (CI + back-test metric); ML auditable in `reports/`.
- [ ] **2.11** ≥1 Shiny module; no hidden-tab recompute; exact-token filters; tests green.
- [ ] **2.12** Both requirements files fully pinned; Python pinned; CI green; data-fallback logs a warning.
- [ ] **2.13** Meaningful, descriptive commit history; README documents structure + task allocation.
- [ ] **2.14** `git shortlog -sne` shows all four members contributing.
- [ ] Protected: completeness test + 22 tests stay green; coverage strip & provenance intact.
```
