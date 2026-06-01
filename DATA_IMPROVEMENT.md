# DATA_IMPROVEMENT.md — Getting full, trustworthy Institution / Country / Topic for **every** paper

> Companion to [IMPROVEMENT.md](IMPROVEMENT.md). That doc covers the dashboard fixes; **this doc is only about the data**: how to fill institution, country, and topic for all 30,602 NeurIPS papers (1987→2025) **automatically and reasonably**, with honest provenance.
> Written 2026-06-01, grounded in a live audit of `data/interim/*.parquet`, `reports/coverage.csv`, and the pipeline scripts — not assumptions.

---

## 0. TL;DR

| Field | Now | Target | How (one line) |
| --- | --- | --- | --- |
| **Institution** | 8.4% known | **>97%** | Multi-source *waterfall*: OpenAlex (fixed) → OpenReview → Semantic Scholar → **GROBID on the PDF** (every paper has one) → ROR normalization |
| **Country** | 8.4% known | **>97%** | Falls out of the same waterfall (institution → ROR → ISO-2 country) |
| **Topic** | 16 curated topics, **~32% flagged "review"** | **<8% review** | Keep the curated list, but **map papers with embeddings (cosine) instead of keyword counting** — exactly the "decide topics, then map with math" idea, done properly |

**The single most important realization:** institution/country are not 8% because the data is missing — they're 8% because the *one* enrichment source (OpenAlex fuzzy title search) is both **metered/throttled** and **fragile**. Every paper already ships with a `pdf_url`, and the affiliation is literally printed on page 1 of every PDF. So 100% coverage is physically available; we just need a layered extractor instead of a single brittle one.

---

## 1. Where the data actually stands (measured)

Audited `data/interim/enriched.parquet` (30,602 rows):

```
openalex_match_method:  unmatched 27,955  |  title_year 2,647
institution_coverage True = 8.38%   (2,647 papers, all from OpenAlex)
```

Coverage by year (`reports/coverage.csv`) tells the real story — it is **not** a smooth decline:

| Era | Institution coverage | What it means |
| --- | --- | --- |
| 1987–2000 | 6–27% | OpenAlex genuinely thin for old papers + fuzzy title match misses |
| 2001–2010 | peaks ~40% (2009) | OpenAlex best here, but still <half |
| **2006** | **0.5%** ⚠️ | Anomaly — a whole year almost entirely missed |
| 2011–2020 | 40% → 13% | Degrades as volume explodes |
| 2021 | 4.4% | Falling off a cliff |
| **2022–2025** | **0.0%** ⚠️ | Complete blackout — 16,690 papers (55% of the corpus!) with zero affiliation |

Two giant red flags — a single dead year (2006) and the four most recent, highest-volume years all at **exactly zero** — are not what "thin coverage" looks like. They are what a **truncated data pull** looks like.

---

## 2. Root-cause diagnosis

### 2.1 Institution / Country — three compounding causes

**Cause A — OpenAlex is now a *metered* API, and the pull dies silently.**
Live check today against `api.openalex.org`:
```json
{"error":"Rate limit exceeded","message":"Insufficient budget. This request costs $0.0001
 but you only have $0 remaining. Resets at midnight UTC..."}
```
OpenAlex moved to a credit/budget model. Now look at `fetch_bulk_source_works()` in [pipeline/02_enrich_openalex.py](pipeline/02_enrich_openalex.py#L198-L225): on HTTP 429 it retries 6 times then **`break`s and returns whatever it collected so far**. If the budget runs out mid-pagination, the function returns a *partial* set of works and reports success. Cursor pagination returns works in a fixed order, so the years that happen to paginate last (or that share a budget-exhaustion boundary) get **zero candidates** → 0% match. This is the mechanism behind the 2022–2025 blackout and the 2006 hole.

**Cause B — matching is fuzzy-title-only, so even fetched works are missed.**
`best_bulk_match()` needs `SequenceMatcher` title ratio ≥ 0.90 (or ≥ 0.80 **and** ≥34% author-surname overlap). Punctuation, LaTeX, and Unicode in titles routinely drop the ratio below 0.90, so real matches are discarded. There is **no exact key** in use even though one exists (see §3.1).

**Cause C — the PDF fallback is a 15-name toy.**
[pipeline/02c_affiliations_pdf.py](pipeline/02c_affiliations_pdf.py) only substring-matches 15 hardcoded institutions (MIT, Stanford, Google…) and 15 countries, defaults `--limit 100`, and is biased to famous US labs. It cannot give *full* coverage and skews the geography.

### 2.2 Topic — one compounding cause

`assign_topic()` in [pipeline/04_topic_modeling.py](pipeline/04_topic_modeling.py#L99-L145) scores each paper by **counting keyword/seed-phrase hits** in `title + title + abstract`. Problems:
- A paper that says "we train a large model on visual data" but never uses the exact taxonomy keywords scores ~0 → dumped into *General / Other ML* and **flagged for review**. That's most of the 32%.
- Doubling the title (`f"{title} {title} {abstract}"`) makes a single title word swing the result.
- Thresholds (`PRIMARY_THRESHOLD = 3.0`, review if margin `< 1.5`) are hand-tuned magic numbers with no semantic notion of similarity.

The taxonomy itself is good. The **matching mechanism** is the weak link — and the user's instinct ("decide topics, then map with math") is exactly the right fix.

---

## 3. Design principles (apply to all three fields)

1. **Every paper gets a value.** Never leave a raw `["Unknown"]` if any source can fill it. Unknown is a *last resort*, recorded honestly, not a default.
2. **Every value carries provenance + confidence.** Add `*_source` (which extractor) and `*_confidence` (0–1) columns. This is what lets the dashboard show an honest coverage strip instead of pretending.
3. **Waterfall, cheapest-and-most-precise first.** Exact keys before fuzzy; free APIs before paid; structured sources before PDF parsing. Each tier only runs on what the previous tier left `Unknown`.
4. **Normalize to canonical IDs**, not free text. Institutions → **ROR id**; countries → **ISO-2**; topics → taxonomy id. So "MIT", "M.I.T.", "Massachusetts Inst. of Technology" collapse to one node, and three different sources can agree.
5. **Idempotent + cached + resumable.** Each stage writes a per-paper sidecar keyed by `paper_id`; re-runs only touch missing rows. (The HTTP caches already exist under `data/interim/*.sqlite`.)

---

## 4. Institution & Country — the multi-source waterfall

Pipeline: for each paper, walk the tiers until institution is known; stop early on a confident hit.

```
paper ──▶ [T0 exact OpenAlex URL-hash] ──▶ [T1 OpenAlex robust] ──▶ [T2 OpenReview]
       ──▶ [T3 Semantic Scholar] ──▶ [T4 GROBID PDF header] ──▶ ROR/ISO normalize ──▶ reconcile
```

### 3.1 T0 — Exact OpenAlex match via the **paper-URL hash** (precision fix, do first)

The crawl already gives us a **globally unique, exact join key** that is currently unused. Every record's `url`/`pdf_url`/`paper_id` contains the NeurIPS content hash:

```
paper_id : neurips_2015_01f78be6f7cad02658508fe4616098a9
url      : .../paper/2015/hash/01f78be6f7cad02658508fe4616098a9-Abstract.html
pdf_url  : .../paper/2015/file/01f78be6f7cad02658508fe4616098a9-Paper.pdf
```

OpenAlex stores each work's `locations[].landing_page_url` and `locations[].pdf_url`. When we do the bulk source pull, **index the returned works by that hash** (regex the 32-hex token out of every location URL) and join on it. This is an **exact, zero-false-positive** match that ignores title noise entirely — strictly better than the current ≥0.90 `SequenceMatcher`. Fall back to title+year+author only for works whose URLs don't carry the hash (older `papers.nips.cc/paper/<id>-slug` format → verify and add that pattern too).

> Action: in `02_enrich_openalex.py`, add `landing_hash` extraction to `build_bulk_index()` and make `best_bulk_match()` try the hash join **before** title similarity.

### 3.2 T1 — Make the OpenAlex bulk pull actually complete

Fix the silent truncation (Cause A) and verify completeness:

- **Fail loudly on budget/429 exhaustion.** If pagination stops before `meta.count` works are retrieved, raise — don't return partial. Persist the cursor so the run resumes next UTC day when budget resets (OpenAlex budget "resets at midnight UTC").
- **Register a real `mailto`/API key.** `config.py` uses `research-observatory@example.com`. Use the team's real email (polite pool) or a funded key so the daily budget is non-zero.
- **Don't trust one source id.** Recent NeurIPS may be indexed under more than one OpenAlex `source` (the proceedings vs. the "Advances in NeurIPS" series vs. DataCite DOIs). Query each candidate source id, **merge**, and sanity-check the per-year counts against our scraped counts in `reports/coverage.csv` before matching. If 2022–2025 are genuinely absent from OpenAlex, that's fine — T2 covers them.
- Keep the author-overlap tie-breaker, but **lower the title threshold to ~0.82 when author overlap ≥ 0.5** (confident).

Expected after T0+T1: roughly **35% → ~75%** for ~2004–2021, *if* OpenAlex's budget allows a full pull. The recent-year hole is handled next.

### 3.3 T2 — OpenReview API (authoritative for the 2022–2025 blackout)

NeurIPS runs review and camera-ready on **OpenReview** for recent years — exactly the years OpenAlex is missing. OpenReview's API is **free, unmetered, and carries affiliations directly**:

- Get the venue's notes: `GET https://api2.openreview.net/notes?content.venueid=NeurIPS.cc/2023/Conference` (paginate by `offset`). Each note → `content.authorids` = list of profile ids (`~First_Last1`).
- Batch-fetch profiles: `GET https://api2.openreview.net/profiles?ids=~A,~B,...`. Each profile's `content.history[]` has `institution.name` + `institution.domain` (and the domain → country via a simple TLD/ROR lookup). Pick the position whose date range covers the paper's year.
- Match OpenReview notes to our papers by **normalized title + year** (titles are clean here) or by the arXiv/DOI link in the note if present.

> Verify the exact `venueid` per year (format changed: `NeurIPS.cc/2022/Conference`, Datasets&Benchmarks track has its own id). This single tier should take **2022–2025 from 0% → ~90%+** — the biggest coverage win in the whole plan, on a free API.

### 3.4 T3 — Semantic Scholar (independent cross-source, gap filler)

The repo already started this (`data/interim/semantic_scholar_http_cache.sqlite`). S2's bulk/graph API returns `authors[].affiliations` and is independent of OpenAlex:
- `POST /graph/v1/paper/batch` with `fields=externalIds,authors.affiliations` and match by title/year or DOI.
- Use it (a) to fill papers still Unknown after T0–T2, and (b) as a **second vote** to validate institution where two sources should agree.

### 3.5 T4 — GROBID PDF-header parsing (the universal backstop → near-100%)

This is what guarantees *full* coverage, including 1987–2004 where no API has good data. **Every paper has a `pdf_url`, and the affiliation block is on page 1.** Replace the toy `02c` with real structured extraction:

- Run a **GROBID** server (one `docker run lfoppiano/grobid`), call `processHeaderDocument` on the first page → TEI XML with `<author><affiliation><orgName>` and `<address><country>` per author. GROBID is the standard, well-tested tool for exactly this.
- Lighter fallback if GROBID is too heavy before the deadline: `pdftotext -f 1 -l 1` (already used in `02c`) → feed the header block to a NER model (`spaCy`/`scispaCy` `ORG`+`GPE`) instead of the 15-string allowlist. Lower quality but unbiased and complete.
- Only run on the residual `Unknown` set after T0–T3 (a few thousand PDFs, page-1 only ≈ overnight; cache results by `paper_id`).

### 3.6 Normalization + reconciliation (turn strings into agreeing IDs)

- **ROR**: resolve every institution string through the ROR affiliation matcher `GET https://api.ror.org/organizations?affiliation=<string>` → canonical `ror_id`, `display_name`, and `country.country_code`. This collapses spelling variants **and** gives country for free (so country coverage = institution coverage).
- **Country**: prefer ROR's country; else OpenAlex `country_code`; else OpenReview domain-TLD; else GROBID `<country>` → all mapped to ISO-2.
- **Reconcile** multiple sources per paper: dedupe ROR ids; when sources disagree on an author's institution, **majority vote**, tie-break by source priority (OpenReview/OpenAlex > S2 > GROBID-NER). Keep the union of institutions across a paper's authors.

### 3.7 Schema additions (carry provenance through to the app)

Add to `enriched.parquet` (and surface in `papers.parquet`):

| Column | Meaning |
| --- | --- |
| `institution_rors` | list of canonical ROR ids (already half-wired in `extract_enrichment`) |
| `countries_iso2` | list of ISO-2 codes |
| `affiliation_source` | `openalex_hash` / `openalex_title` / `openreview` / `s2` / `grobid` / `none` |
| `affiliation_confidence` | 0–1 (1.0 exact hash/DOI, ~0.9 OpenReview, ~0.6 GROBID-NER) |
| `institution_coverage`, `country_coverage` | bool (already exist — keep) |

`03_clean_normalize.py` and `07_aggregate_for_app.py` already pass `institutions`/`countries` through and compute `*_known` — just extend them to carry the new columns and roll `affiliation_source` into `reports/coverage.csv`.

### 3.8 Expected coverage after the waterfall

| Tier | Adds | Cumulative institution coverage |
| --- | --- | --- |
| T0 hash + T1 OpenAlex (fixed) | exact + full 2004–2021 | ~55% |
| T2 OpenReview | 2018–2025 (kills the blackout) | ~80% |
| T3 Semantic Scholar | scattered gaps | ~85% |
| T4 GROBID PDF | everything else (incl. pre-2004) | **>97%** |

The remaining ~3% are papers whose PDFs genuinely omit affiliations — report them honestly as Unknown.

---

## 5. Topic — keep the list, map with math (embeddings)

Your instinct is right and is the standard modern approach: **fix the taxonomy of topics, then assign each paper by *semantic similarity* rather than keyword counting.**

### 5.1 Keep the curated 16-topic taxonomy
Don't switch to raw KMeans/HDBSCAN clusters — they'd need re-labeling every run and aren't stable across years. The curated list in [pipeline/topic_taxonomy.json](pipeline/topic_taxonomy.json) is an asset. We change *how papers map to it*, not the list.

### 5.2 Build a vector prototype per topic
For each topic, create one (or a few) prototype embedding:
- **Description embedding**: embed a rich string = `label + ". " + seed_phrases + keywords` → one vector per topic.
- **Exemplar embedding (better)**: take the current high-confidence keyword matches (e.g. `topic_score ≥ 8`, the unambiguous ones) as labeled exemplars, embed them, and use the **mean (centroid)** as the prototype. This is light semi-supervision — the strong keyword hits *anchor* each topic, embeddings generalize the rest.

### 5.3 Embed every paper
Use a scientific-paper embedding model, offline, no API cost:
- **SPECTER2** (`allenai/specter2`) — purpose-built for title+abstract of papers; or
- `sentence-transformers/all-MiniLM-L6-v2` — lighter, general, fast on CPU.

Embed `title + abstract` once (30k papers ≈ minutes on GPU, <1h CPU), cache to `data/interim/paper_embeddings.parquet`.

### 5.4 Assign by cosine + hybrid with keywords
```
cos[t]      = cosine(paper_vec, prototype_vec[t])         # semantic recall
kw[t]       = normalized current keyword score (0..1)     # lexical precision
final[t]    = 0.7 * cos[t] + 0.3 * kw[t]                  # tunable blend
primary     = argmax_t final[t]
probability = softmax(final / τ)[primary]                 # calibrated confidence
secondary   = topics with prob ≥ 0.15 and ≥ 0.5 * primary_prob
review_flag = (primary_prob < 0.40) OR (top-2 margin < 0.08)
```
This keeps the **precision** of seed phrases (when they fire, they boost the right topic) while adding the **recall** of embeddings (papers with no exact keyword still land correctly). It directly attacks the ~32% review pile: most of those are vocabulary mismatches that embeddings resolve.

### 5.5 Audit the taxonomy *with* the embeddings (the math-checks-the-humans loop)
Run **UMAP → HDBSCAN** on the paper embeddings (offline, for analysis only, not for the live labels):
- For each discovered cluster, look at the dominant assigned topic. A clean cluster ↔ one topic = the taxonomy is healthy.
- A cluster that splits across many topics, or two clusters collapsing into one topic, flags a **missing split or merge** → propose a taxonomy edit (e.g. peel "Diffusion/Generative" or "LLM agents" out if a dense cluster has no home). This is how you justify the topic list quantitatively in the report.
- Bonus: the UMAP 2-D/3-D coordinates double as the "research landscape" visual in IMPROVEMENT.md §WS-4.

### 5.6 Optional accuracy ceiling — LLM zero-shot for the hard cases
For the residual low-confidence papers only (keeps it cheap), classify with **Claude Haiku 4.5** via the Batch API: prompt = the 16 labels + descriptions + the paper's title/abstract → JSON `{primary, secondary[], confidence, rationale}`. Run it on the `review_flag` subset (~a few thousand, not 30k) to resolve the ambiguous tail with human-level judgment, then fold results back in as another override source. "Automatic but reasonable," and the rationale text is great for the topic-audit report. Keep embeddings as the no-cost default; treat the LLM as a quality booster.

### 5.7 Keep the manual override hatch
`data/manual/topic_overrides.csv` already wins over automatic assignment ([04_topic_modeling.py](pipeline/04_topic_modeling.py#L198-L212)) — keep it for the handful of papers no method gets right.

**Expected:** review-flag rate **~32% → <8%**, and topic assignment becomes robust to wording instead of hostage to it.

---

## 6. Honesty layer (turn coverage into a feature, not a liability)

- Keep the per-`(venue, year)` coverage already computed in `07_aggregate_for_app.py`, and **add `affiliation_source` breakdown** so the dashboard can show *how* each year was filled (OpenAlex vs OpenReview vs GROBID).
- In country/institution panels, keep an **"Unknown" bucket visible** (or filtered with a visible note), never silently dropped — except on the map, which has no geometry for Unknown.
- A small **coverage-by-year strip** (already specced in IDEA.md §5) showing the climb from 8% → 97% is itself a strong result to present.

---

## 7. Concrete change list

**Institution / Country**
- `pipeline/02_enrich_openalex.py`
  - `fetch_bulk_source_works`: **raise on incomplete pagination** (don't return partial); persist/resume cursor; accept multiple source ids; verify `meta.count`.
  - `build_bulk_index` + `best_bulk_match`: add **URL-hash exact match** (T0) before title similarity; lower title threshold when author overlap is high.
  - real `mailto`/API key in `config.py`.
- `pipeline/02d_openreview.py` *(new)* — venue notes → profiles → affiliations for 2018–2025 (T2).
- `pipeline/02e_semantic_scholar.py` *(new or extend existing cache)* — batch affiliations (T3).
- `pipeline/02c_affiliations_pdf.py` — **replace the 15-name allowlist with GROBID** (or pdftotext+scispaCy NER); raise `--limit`; run only on residual Unknown (T4).
- `pipeline/02f_normalize_affiliations.py` *(new)* — ROR + ISO-2 resolution and cross-source reconciliation (§3.6).
- `pipeline/03_clean_normalize.py` & `07_aggregate_for_app.py` — carry `institution_rors`, `countries_iso2`, `affiliation_source`, `affiliation_confidence`; add source breakdown to `coverage`.

**Topic**
- `pipeline/04b_embed_papers.py` *(new)* — SPECTER2/MiniLM embeddings → `data/interim/paper_embeddings.parquet` (cached).
- `pipeline/04_topic_modeling.py` — build topic prototypes; replace pure keyword scoring in `assign_topic` with the **hybrid cosine+keyword** formula (§5.4); softmax confidence; tighter review flag.
- `pipeline/04c_taxonomy_audit.py` *(new, analysis)* — UMAP+HDBSCAN cluster-vs-topic report → `reports/topic_audit.csv` (extend the existing one) + UMAP coords for the landscape viz.
- *(optional)* `pipeline/04d_llm_resolve.py` — Claude Haiku batch on the review subset.

---

## 8. Runbook & rough effort (6 days, 2026-06-01 → 06-07)

| Order | Stage | Effort | Cost | Unblocks |
| --- | --- | --- | --- | --- |
| 1 | T0 URL-hash + T1 OpenAlex fix (raise-on-truncation, real key) | 0.5 day | free* | ~55% inst. coverage, kills the 2006/2022+ silent-fail bug |
| 2 | T2 OpenReview | 0.5 day | free | **2022–2025 0%→90%** (biggest win) |
| 3 | Topic embeddings + hybrid assign | 0.5 day | free | review-flag 32%→<8% |
| 4 | T4 GROBID on residual (overnight run) | 0.5 day + run | free | →97% incl. pre-2004 |
| 5 | ROR/ISO normalize + reconcile + provenance cols | 0.5 day | free | clean nodes, country=institution coverage |
| 6 | T3 Semantic Scholar + taxonomy audit + (opt) LLM tail | stretch | ~$ small | robustness + report credibility |

\* OpenAlex budget resets at midnight UTC; a funded key or polite-pool email removes the throttle.

**Gate:** Stages 1–4 deliver the headline numbers (>90% affiliation, <8% topic-review) on free tooling. Everything in Stage 6 is polish.

---

## 9. Acceptance criteria

- [ ] Institution coverage **>95%** overall, reported per year; the 2022–2025 blackout and 2006 hole are gone.
- [ ] Country coverage tracks institution coverage (ROR-derived), reported per year.
- [ ] Every paper has `affiliation_source` + `affiliation_confidence`; coverage strip shows the source mix per year.
- [ ] Institutions normalized to ROR ids (no "MIT" vs "M.I.T." duplicates in the leaderboard).
- [ ] Topic **review-flag rate <8%**; assignment uses embedding similarity, not keyword counts; confidences are calibrated softmax values.
- [ ] `reports/topic_audit.csv` includes the embedding-cluster-vs-taxonomy check (math justification for the 16 topics).
- [ ] Pipeline is resumable/cached end-to-end; a re-run doesn't re-hit completed papers.

---

## 10. Risks & mitigations

| Risk | Mitigation |
| --- | --- |
| OpenAlex budget stays $0 / metered | OpenReview (free) covers the critical recent years; GROBID (free, local) covers everything; OpenAlex becomes a *nice-to-have*, not a dependency. |
| OpenReview `venueid` differs per year | Verify each year's id from the API before the run; fall back to title+year match. |
| GROBID too heavy to stand up in time | Ship `pdftotext + scispaCy NER` fallback first; swap in GROBID if time allows. |
| Embedding model download / GPU | MiniLM runs on CPU in <1h for 30k papers; embeddings cached so it's a one-time cost. |
| ROR mismatches a niche org | Keep raw extracted string alongside `ror_id`; unresolved → keep string + `country=Unknown`, still better than dropping. |
| LLM topic cost | Run only on the <8% review subset via Batch API (50% off); embeddings carry the other 92% for free. |
