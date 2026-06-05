# Institution Feedback CSV

This is the simplified manual feedback workflow for institution cleanup and country-review.

Main file:

```text
data/manual/institution_feedback.csv
```

The file is pre-populated with every current raw institution string from `data/processed/papers.parquet`. Edit the manual columns, then a later pipeline step can apply these decisions reproducibly.

## Columns

### `raw_institution`

Exact raw institution string from the current data. Do not edit this value unless you intentionally want to break matching.

### `canonical_institutions`

JSON list of canonical institution names.

Use this for normal alias/merge cleanup.

Examples:

```csv
raw_institution,canonical_institutions
University of Toronto.,["University of Toronto"]
Meta AI,["Meta"]
Co-corresponding Authors,[]
```

Rules:

- One canonical institution: `["University of Toronto"]`
- Multiple canonical institutions: `["University of Toronto", "Vector Institute", "NVIDIA"]`
- Artifact / not an institution: `[]`

### `approved`

Whether a human has approved the row.

Use:

```text
TRUE
FALSE
```

Only rows with `approved=TRUE` should be applied by the feedback pipeline.

### `manual_split_institutions`

JSON list used when the raw string should be explicitly split into multiple institutions.

Usually this should be the same as `canonical_institutions` for split cases. It exists to make split decisions easy to identify.

Example:

```csv
raw_institution,canonical_institutions,approved,manual_split_institutions
University of Toronto1 Vector Institute2 NVIDIA3,"[""University of Toronto"", ""Vector Institute"", ""NVIDIA""]",TRUE,"[""University of Toronto"", ""Vector Institute"", ""NVIDIA""]"
```

If no manual split is needed, keep:

```text
[]
```

### `country_iso2_overrides`

Optional JSON object for country corrections. This is a refinement added because some institution-to-country matches are questionable.

Examples:

```json
{}
{"University of Toronto": "CA"}
{"Meta": "US"}
{"Meta Reality Labs": "CH"}
```

Rules:

- Keys should be canonical institution names.
- Values should be ISO-2 country codes, e.g. `US`, `CN`, `GB`, `CA`, `CH`, `HK`.
- Leave `{}` if no country override is needed.

### `paper_count`

Number of unique papers containing the raw institution string. This is generated context to help prioritize review.

### `current_country_candidates`

JSON list of current countries co-occurring with this raw institution in the paper-level data. This is review context only.

### `source_mix`

Counts of affiliation sources that produced this raw institution, e.g. `pdf_text:12 | openalex_hash:3`. This is review context only.

### `reviewer`

Optional reviewer name or initials.

### `notes`

Optional explanation for the decision.

## Recommended workflow

1. Sort by `paper_count` descending.
2. For obvious aliases, edit `canonical_institutions` and set `approved=TRUE`.
3. For artifacts, set `canonical_institutions=[]` and `approved=TRUE`.
4. For compound strings, set both `canonical_institutions` and `manual_split_institutions` to the list of institutions, then set `approved=TRUE`.
5. For questionable country mappings, add `country_iso2_overrides`.
6. Leave uncertain rows as `approved=FALSE`.

## Important CSV quoting note

Because list/object fields contain JSON, spreadsheet tools may add quotes. That is okay as long as the cell still parses as JSON.

Valid cell examples:

```text
["Stanford University"]
[]
{"Stanford University": "US"}
```

Invalid examples:

```text
Stanford University
US
yes
```
