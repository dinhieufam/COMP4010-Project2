# Data Preprocessing

---

## Topic Modeling

### Overview

Every NeurIPS paper is assigned to exactly one primary topic from a fixed, hand-curated
taxonomy of 15 categories. Assignment uses a **hybrid keyword + vector** scoring method
that combines rule-based signal with TF-IDF cosine similarity.

### Taxonomy

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

Each topic in `pipeline/topic_taxonomy.json` has two lists:

- **`keywords`** — individual tokens or short phrases that signal topic membership
- **`seed_phrases`** — multi-word expressions that strongly indicate the topic

### Input text

For scoring, each paper's text is formed as:

```
"<title> <title> <abstract>"
```

The title is duplicated to double its weight relative to the abstract. This reflects the
fact that NeurIPS titles are highly informative and abstract text is often more generic.

### Step 1 — Keyword score

The keyword score is a rule-based signal computed over the input text:

| Match type | Score added |
|---|---|
| Seed phrase match (whole-word regex) | +4.0 per phrase |
| Multi-word keyword match | +2.5 per phrase |
| Single-word keyword match | +min(count, 3) × 1.0 per token |

Single-word matches are capped at 3 occurrences to prevent repetitive abstracts from
dominating. The final keyword score for each topic is the sum of all matches.

### Step 2 — Vector score

All paper texts and topic prototype texts are jointly vectorized using TF-IDF:

```python
TfidfVectorizer(
    stop_words="english",
    ngram_range=(1, 2),   # unigrams and bigrams
    min_df=2,             # ignore tokens that appear in fewer than 2 documents
    max_df=0.92,          # ignore tokens that appear in more than 92% of documents
    sublinear_tf=True,    # apply log(1+tf) term frequency scaling
)
```

Each topic's prototype text is:

```
"<label>. <label>. <seed_phrases>. <seed_phrases>. <keywords>"
```

The label and seed phrases are repeated to up-weight the most diagnostic terms.

The matrix is fit on all paper texts plus all prototype texts together. Cosine
similarity is then computed between each paper vector and each topic prototype vector,
producing a matrix of shape `(n_papers, n_topics)`.

### Step 3 — Combined score

The two scores are normalized and combined with fixed weights:

```
score = 0.62 × (vector_score / max_vector) + 0.38 × (keyword_score / max(max_keyword, 8))
```

The 0.62 / 0.38 weighting gives the vector (semantic) signal slight precedence over
the keyword (lexical) signal. The `max(max_keyword, 8)` floor prevents extremely
low-keyword-score papers from receiving an artificially inflated keyword component.

Topics are ranked by combined score. The highest-ranking topic is the primary assignment.

### Step 4 — Fallback threshold

If both the vector score and the keyword score of the top-ranked topic fall below their
respective thresholds (`VECTOR_PRIMARY_THRESHOLD = 0.28`, `PRIMARY_THRESHOLD = 3.0`),
the paper is assigned to the **General / Other ML** fallback topic instead.

### Step 5 — Secondary topics

Up to 3 secondary topics are recorded. A topic qualifies as secondary if:

- Its combined score is ≥ `VECTOR_PRIMARY_THRESHOLD`, AND
- Its combined score is ≥ 82% of the primary topic's score

Secondary topics appear in `secondary_topic_labels` and are used by the Topic
Connections network chart.

### Step 6 — Review flag

`topic_review_flag = True` is set when:

- The primary assignment is the fallback topic, OR
- The softmax probability of the top topic is below `0.34` (low confidence), OR
- The probability margin between the top and second topics is below `0.045`

Flagged papers appear in `audits/topic_audit.csv` for manual review.

### Step 7 — Manual overrides

`data/manual/topic_overrides.csv` lets reviewers pin specific papers to a topic:

| Column | Description |
|---|---|
| `paper_id` | Exact paper ID |
| `primary_topic` | Topic label to assign |
| `secondary_topics` | Optional semicolon-separated secondary labels |

Overrides set `topic_probability = 1.0` and clear the review flag. The topic label must
exactly match a label in the taxonomy; the script raises an error if it does not.

### Output fields

| Field | Type | Description |
|---|---|---|
| `topic_id` | int | Taxonomy topic identifier (0–15) |
| `topic_label` | str | Human-readable topic name |
| `topic_probability` | float | Softmax probability of the primary assignment |
| `topic_keywords` | str | Top 8 keywords from the assigned topic (comma-separated) |
| `secondary_topic_ids` | list[int] | Up to 3 secondary topic IDs |
| `secondary_topic_labels` | list[str] | Secondary topic names |
| `topic_score` | float | Raw combined score |
| `secondary_topic_score` | float | Combined score of the top secondary topic |
| `topic_review_flag` | bool | True if assignment confidence is low |

---

## Institution Extraction

Institution names are extracted from three sources in priority order:
**OpenAlex** (Stage 02), **PDF header text** (Stage 02c), and **OpenReview profiles**
(Stage 02d). Each source is tried in sequence; a later source only fills rows that the
earlier source left as `["Unknown"]`.

### Source 1 — OpenAlex authorships

OpenAlex records each paper's `authorships` list, where every entry contains an
`institutions` array:

```json
{
  "authorships": [
    {
      "author": {"display_name": "Ashish Vaswani"},
      "institutions": [
        {
          "display_name": "Google Brain",
          "ror": "https://ror.org/...",
          "country_code": "US"
        }
      ]
    }
  ]
}
```

All `display_name` values across all authorships are collected into a set and written
as the `institutions` list. If no institution is found, the field defaults to
`["Unknown"]`.

Confidence values for OpenAlex-sourced institutions:

| Match method | `affiliation_confidence` |
|---|---|
| URL hash match (`openalex_hash`) | 1.0 |
| DOI match (`openalex_doi`) | 1.0 |
| Title similarity match (`openalex_title`) | 0.86 |
| Unmatched | 0.0 |

### Source 2 — PDF header text

For papers still showing `["Unknown"]` institutions after the OpenAlex pass, the
first page of each paper's PDF is downloaded and its author header is parsed.

**Header isolation:** Text before the first occurrence of "Abstract", "Introduction",
or "Keywords" is treated as the author header. This cuts off body text that would
introduce false positive institution matches.

**Known-alias matching:** A static dictionary of ~60 major institutions maps each
canonical name to its known aliases and abbreviations:

```python
"Massachusetts Institute of Technology": ["mit", "massachusetts institute of technology"],
"Google":     ["google research", "google brain", "google deepmind", "google"],
"DeepMind":   ["deepmind"],
"ETH Zurich": ["eth zurich", "eth zürich"],
```

This dictionary is augmented at runtime with any institution name that appears ≥ 2
times in the existing enriched data. Each alias is matched as a whole word against
the normalized header text. If a match is found, the canonical display name is used
as the institution (not the raw alias), ensuring consistent naming across papers.

**Pattern mining (fallback):** If no known alias matches, the header text is scanned
for organization-like phrases using two methods:

1. **Keyword-line scan:** Lines containing organization keywords (`university`,
   `institute`, `laboratory`, `research`, `college`, `deepmind`, `openai`, `google`,
   `microsoft`, `meta`, `nvidia`, etc.) are split on `;`, ` | `, ` • `, and `, `
   followed by a capital letter. Each piece is cleaned (footnote markers, digits,
   emails removed) and accepted if it contains an organization keyword and is between
   4 and 120 characters.

2. **Regex pattern:** Captures proper-noun phrases ending in an institution-type word:
   ```
   [A-Z][A-Za-z&.\- ]{2,80}?(University|Institute|College|Laboratory|Labs|Research|Centre|...)
   ```

**Subsumed candidate removal:** If both `"MIT"` and `"Massachusetts Institute of
Technology"` are found, the shorter one is discarded because it appears as a substring
of the longer one.

**Confidence scoring:**

| Condition | Base confidence |
|---|---|
| Known-alias match | 0.68 |
| Pattern-mined (generic) | 0.54 |
| +Country also resolved | +0.07 |
| Maximum | 0.75 |

Records with confidence below `--min-confidence` (default 0.50) are discarded and
left as `["Unknown"]`.

### Source 3 — OpenReview profiles

For recent years (default 2023, 2024, 2025), the OpenReview API v2 provides author
profiles that include each author's institutional history.

Each author profile contains a `history` array:

```json
{
  "history": [
    {
      "institution": {"name": "University of Oxford", "domain": "ox.ac.uk"},
      "start": 2022,
      "end": null
    }
  ]
}
```

The history entry whose `start`/`end` range covers the paper's publication year is
selected. If no dated entry matches, the most recent entry with an institution is used
as a fallback. The institution `name` is written directly as the institution string.

OpenReview-sourced affiliations have `affiliation_confidence = 0.9`.

### Manual corrections

`data/manual/institution_feedback.csv` applies three types of post-hoc corrections:

| `approved` value | Action |
|---|---|
| `TRUE` | Replace the raw string with the canonical name (typo fix, suffix removal) |
| `FALSE` | The raw string is a merged multi-institution string — split into the `manual_split_institutions` list |
| `REMOVE` | The string is an extraction artefact — drop it entirely |

Manual corrections are applied in Stage 08 (`08_apply_institution_feedback.py`), which
patches `data/interim/topics.parquet` and `data/interim/enriched.parquet` in-place,
then re-runs Stage 07 to regenerate all processed app datasets.

### Final output

All institution lists are serialized to the `institutions_text` column in
`data/processed/papers.parquet` using ` | ` as the delimiter (pipe rather than comma,
to avoid ambiguity with institution names that contain commas):

```
"University of Toronto | Vector Institute | Microsoft Research"
```

`institution_year.parquet` is produced by exploding this list and grouping by
`(venue, year, institution)` to count paper-participations per institution per year.

---

## Country Extraction

Country codes (ISO 3166-1 alpha-2) are extracted from three sources in the same
priority order as institutions: **OpenAlex**, **PDF header text**, and **OpenReview
profiles**. A fourth source, **manual institution feedback**, can override all three.

### Source 1 — OpenAlex authorship records

Country codes are read directly from the `country_code` field in each OpenAlex
authorship's institution entries:

```json
{"country_code": "US"}
{"country_code": "CN"}
```

All distinct country codes from all authorships in a paper are collected into a set.
If no code is found, the field defaults to `["Unknown"]`.

Because OpenAlex records institutional affiliations at the time of the paper, this is
the highest-fidelity source. Confidence is 1.0 for hash/DOI-matched papers, 0.86 for
title-matched papers.

### Source 2 — PDF header text

Country codes are inferred from the paper's PDF header using two methods:

**TLD inference:** Email addresses and web domains in the header are scanned. The
domain suffix is matched against a table of country-code top-level domains:

| TLD(s) | Country |
|---|---|
| `.edu`, `.gov`, `.us` | US |
| `.ac.uk`, `.uk` | GB |
| `.cn`, `.edu.cn` | CN |
| `.de` | DE |
| `.fr` | FR |
| `.hk`, `.edu.hk` | HK |
| `.sg` | SG |
| `.ch` | CH |
| `.jp`, `.ac.jp` | JP |
| `.kr`, `.ac.kr` | KR |
| `.au`, `.edu.au` | AU |
| `.il`, `.ac.il` | IL |
| … | … |

**Country name phrases:** The normalized header text is scanned for country name
strings and common abbreviations:

| Phrase | Code |
|---|---|
| `"united states"`, `"usa"`, `"u.s.a"` | US |
| `"china"` | CN |
| `"united kingdom"`, `"uk"` | GB |
| `"germany"` | DE |
| `"france"` | FR |
| `"switzerland"` | CH |
| `"singapore"` | SG |
| `"south korea"`, `"korea"` | KR |
| `"hong kong"` | HK |
| … | … |

**Institution-to-country lookup:** After institution names are extracted from the
header, each institution is looked up in a static table of ~80 known institution →
country mappings:

```python
"Massachusetts Institute of Technology": {"US"},
"Tsinghua University":                   {"CN"},
"ETH Zurich":                            {"CH"},
"University of Hong Kong":               {"HK"},
"DeepMind":                              {"GB"},
...
```

If all extracted institutions have entries in this table, the countries derived from
the lookup **replace** the TLD/phrase-based countries (institution-level resolution
is more precise than domain-level resolution).

### Source 3 — OpenReview profiles

Country codes are inferred from each author's institution domain using the same TLD
table as the PDF stage:

```python
domain = "ox.ac.uk"
# suffix ".ac.uk" → GB
```

If the domain does not match any TLD, a supplementary institution-name lookup is
applied:

| Substring in institution name | Code |
|---|---|
| `"tsinghua"`, `"peking university"`, `"zhejiang university"` | CN |
| `"eth zurich"`, `"epfl"` | CH |
| `"university of toronto"`, `"mila"` | CA |
| `"university of oxford"`, `"imperial college"` | GB |
| `"university of tokyo"` | JP |
| `"kaist"`, `"seoul national"` | KR |
| … | … |

### Source 4 — Manual institution feedback

`data/manual/institution_feedback.csv` includes a `current_country_candidates` column
listing ISO2 codes for each institution row. When corrections are applied in Stage 08:

- If the feedback CSV supplies country codes for any institution in a paper, those
  codes **replace** all previously derived country data for that paper.
- If no feedback entry exists for any of the paper's institutions, the existing
  country data is kept unchanged.

Manual-label countries are considered the highest-trust source because they have been
reviewed by a human.

### ISO2 normalisation

Non-standard codes in manual data are normalized before use:

| Raw | Normalized |
|---|---|
| `UK` | `GB` |
| `ENG`, `SCO`, `WAL`, `NIR` | `GB` |

### Final output

Country lists are serialized to the `countries_text` column using `, ` as the delimiter:

```
"US, CN, GB"
```

`country_year.parquet` is produced by exploding this list and grouping by
`(venue, year, country)` to count paper-participations per country per year. Because
a single paper can have authors from multiple countries, one paper may contribute to
multiple rows — this is the intended "participation" counting method used throughout
the dashboard.
