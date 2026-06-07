# Presentation Storytelling & User Flow Design

This document explains how the AI Conference Research Observatory is structured as a
guided story, the design decisions behind each chapter, and how users move through the
two modes — Story and Explore.

---

## The Core Idea: Two Modes, One Argument

The dashboard is built on a single editorial question:

> *How did a 90-paper workshop about brain-inspired machines become a 5,823-paper
> global engine of modern AI?*

Rather than dropping users into a blank dashboard with filters, the experience is split
into two distinct modes:

| Mode | Purpose | Entry point |
|---|---|---|
| **① Story** | A guided documentary — one argument, told in chapters | Default on load |
| **② Explore** | A fully filterable investigative dashboard | Via navbar or "Open Explorer" CTA |

Story comes first. It does the analytical work so that Explore is meaningful — users
arrive at the interactive dashboard with a mental model already formed.

---

## Narrative Architecture

### Landing Hero

Before any chapter begins, a full-screen hero block states the core fact:

```
1987 → 2025
90 → 5,823
```

The numbers are intentionally provocative. The prose explains *why* — it wasn't steady
growth, it was breakthroughs: AlexNet 2012, Transformers 2017, ChatGPT 2022. Each
growth surge follows a specific moment.

A `↓ scroll to begin` cue sets the reading contract: this is a vertical scroll experience.

---

### Chapter Structure

Each chapter follows the same rhythm:

1. **Eyebrow** — two or three words of category label ("The Explosion", "AI Went Global")
2. **Claim** — a single question or declarative sentence that the chart will answer
3. **Body** — 2–3 sentences of context, framing what to look for
4. **Chart** — the evidence
5. **Takeaway** — the answer, stated plainly

This structure mirrors journalism's "inverted pyramid" but inverted again for story:
claim first, evidence second, conclusion last. The reader knows what to look for before
they see the data.

---

## The Seven Chapters

### Chapter 1 — The Explosion

**Claim:** How does a 90-paper workshop become a 5,823-paper conference?

**Chart:** Annual paper count (bar + line), with dotted event markers at AlexNet (2012),
GANs (2014), Transformers (2017), GPT-3 (2020), and ChatGPT (2022).

**Design decision:** The event markers make the story legible without annotation. The
reader can see that the three big acceleration phases each follow a specific moment.
The chart uses the full 1987–2025 span to show the scale of the transformation.

**Takeaway:** More than half of all 30,602 NeurIPS papers were accepted after 2019.

---

### Chapter 2 — It Changed Its Mind *(scrollytelling)*

**Claim:** From building foundations of learning to systems that see, speak, and act.

This chapter uses a **4-step scrollytelling sequence** — the most technically complex
chapter in the story. Each scroll step swaps the visible chart while prose progresses
in the left column.

| Step | Prose | Chart |
|---|---|---|
| 01 | In 1987, the question was: how do machines learn? | Horizontal bar of 1987 topic shares — Deep Learning highlighted at 52% |
| 02 | Both Deep Learning and Neuroscience faded in share | Dual line chart: DL share vs Neuroscience share over 38 years, with era bands |
| 03 | By 2025, the question became: what can systems do? | Horizontal bar of 2025 topic shares — NLP & LLMs highlighted at 20.5% |
| 04 | AI evolved from studying learning to building systems | Grouped bar: 1987 vs 2025 side-by-side for 8 key topics |

**Design decision:** The sticky-pane pattern lets the chart stay on screen while the user
reads. The chart doesn't move — only the prose scrolls. This keeps the comparison always
visible. Each step gets its own pre-rendered Plotly figure (not a dynamic update); CSS
opacity switches which chart is active. This avoids re-rendering lag during scroll.

**Era bands** divide the timeline into five named periods. The same eras appear across
all multi-year charts:

| Period | Years | Label |
|---|---|---|
| Foundations | 1987–1997 | foundations era |
| Probabilistic | 1998–2007 | probabilistic era |
| Deep Learning Rise | 2008–2015 | deep learning rise |
| Scaling | 2016–2021 | scaling era |
| Generative | 2022–2025 | generative era |

---

### Chapter 3 — The Big Shift

**Claim:** Which topics dominated each era?

**Chart:** 100%-stacked horizontal bar — one bar per era, each segment a research topic.
Top 7 topics by total paper count are named; everything else collapses to "Other".

**Design decision:** The 100% stacking makes share changes legible across eras of very
different sizes. A raw count chart would make the small early eras nearly invisible.
The colours come from a fixed 16-colour topic palette so each topic has a consistent
visual identity across all charts in the dashboard.

**Takeaway:** Deep Learning's share fell from 52% to ~9% — not because the field
declined, but because NeurIPS diversified from a few dominant foundations into many
specialised application areas.

---

### Chapter 4 — Where the Momentum Is

**Claim:** NLP and Generative AI are accelerating — Safety is catching up.

**Chart:** Multi-line chart showing the 5 fastest-growing topics since 2015.
"Fastest-growing" is defined as the largest gain in percentage-point share between
the average of the first two years (2015–2016) and the average of the last two years
(2024–2025). GPT-3 and ChatGPT event markers are added.

**Design decision:** The algorithm is data-driven — the top 5 lines are computed
automatically from the dataset. Labelling them in the legend rather than as inline
annotations keeps the chart clean even when lines cross.

**Takeaway:** NLP & LLMs grew from 4% to 20.5%. Safety & Alignment is accelerating
from near-zero — the field has started studying its own consequences.

---

### Act Break

Between the "ideas" act (Chapters 1–4) and the "geography" act (Chapters 5–7), a
full-bleed interstitial states the bridge:

```
US 57% → 32%
From dominant to duopoly — in just a decade.
"The ideas changed first. Then the people and places producing those ideas changed too."
```

**Design decision:** The act break gives the reader a moment to absorb the topic story
before pivoting to geography. It also states the next chapter's claim before the reader
arrives at it, priming the charts.

---

### Chapter 5 — AI Went Global *(scrollytelling)*

**Claim:** How did geographic leadership change?

A second 4-step scrollytelling sequence, this time about country participation.

| Step | Prose | Chart |
|---|---|---|
| 01 | As recently as 2015, the US held ~57% of affiliations | Bar chart of top 10 countries in 2015 — United States highlighted |
| 02 | By 2021, China had entered at 14% — and accelerating | Bar chart of top 10 countries in 2021 — China highlighted |
| 03 | China closed 14 percentage points in four years | Line chart: US vs China share, 2021–2025 |
| 04 | In 2025, the US and China nearly tied | Bar chart of top 10 countries in 2025 — China highlighted |

**Design decision:** The scrollytelling sequence lets the reader experience the shift
progressively rather than seeing the end-state first. The bar chart freezes at a
specific year; the line chart shows the trajectory. Together they make the "convergence"
legible without requiring the reader to hold two charts in mind simultaneously.

**Country participation counting:** Shares count paper-participations — one paper with
authors from two countries contributes to both. This is disclosed in the takeaway to
prevent misinterpretation.

---

### Chapter 6 — Power Moved

**Claim:** Which institutions shaped the field, then and now?

**Chart:** Two stacked horizontal bar charts in one panel (subplot):
- Top 10 institutions · 1990–1999 (all grey bars — US incumbents)
- Top 10 institutions · 2022–2025 (coral = new entrants; grey = US incumbents)

**Design decision:** The dual-period comparison is the most direct way to show power
shift without forcing the reader to flip between panels. The colour encoding does the
analytical work: coral bars are institutions that weren't in the 1990s list. The reader
can count them without being told.

**Takeaway:** 1990s: MIT, CMU, Caltech, Stanford, Berkeley. 2022–25: HKU, Google,
Tsinghua, MIT, Peking — a complete power shift from US campuses to a global mix of
universities and industry labs.

---

### Chapter 7 — The Field Grew a Conscience

**Claim:** As AI became more capable, NeurIPS started studying its consequences.

**Chart:** Line chart: Safety & Alignment, Fairness & Privacy, and Data & Evaluation
share of papers from 2010 onward. GPT-3 and ChatGPT event markers.

**Design decision:** Starting at 2010 rather than 1987 removes the long flat baseline
and makes the post-2015 growth legible. The three "conscience" topics are fixed (not
auto-computed) because this is an editorial claim, not a discovery.

**Takeaway:** These topics were near-zero before 2015 — now they are among the
fastest-growing. Modern AI research increasingly studies its own risks.

---

### Finale

The story closes with a two-paragraph summary:

> NeurIPS began as a small community trying to understand learning. Four decades later,
> it is a global record of systems that speak, see, generate, decide, and reshape society.

And a call-to-action button: **② Open the Explorer →**

**Design decision:** The CTA is the only interactive element in the story. Clicking it
programmatically switches the navset tab to Explore mode
(`ui.update_navs("mode_tabs", selected="② Explore")`), so the user lands in the
dashboard with the story's argument fresh in mind.

---

## Technical: Scrollytelling Implementation

### Layout pattern

Each scrollytelling chapter uses a two-column sticky layout:

```
┌─────────────────────┬─────────────────────────────┐
│  .scrolly-sticky    │  .scrolly-steps              │
│  (position: sticky) │                              │
│                     │  01 Step heading             │
│  [Charts stacked,   │     Step body text           │
│   CSS opacity       │                              │
│   controls which    │  02 Step heading             │
│   is visible]       │     Step body text           │
│                     │                              │
│                     │  03 ...                      │
└─────────────────────┴─────────────────────────────┘
```

The sticky pane holds all charts for that chapter stacked at `opacity: 0`. Only the
`.is-active` chart has `opacity: 1` (with a CSS transition). This avoids Shiny's
reactive re-render on every scroll event — all charts are rendered once at load.

### JavaScript: IntersectionObserver

`app/www/scrollytelling.js` uses the browser's `IntersectionObserver` API to watch
each `.scrolly-step` element:

```js
const obs = new IntersectionObserver(
  (entries) => {
    entries.forEach((entry) => {
      if (!entry.isIntersecting) return;
      const stepIndex = parseInt(entry.target.dataset.step, 10);
      // Activate the matching chart
      charts.forEach((el) => el.classList.remove("is-active"));
      document.querySelector(`.scrolly-chart[data-step="${stepIndex}"]`)
              .classList.add("is-active");
    });
  },
  { threshold: 0.55, rootMargin: "0px 0px -12% 0px" }
);
```

- **threshold: 0.55** — a step must be 55% visible before it activates. This prevents
  accidental triggers when the user scrolls quickly.
- **rootMargin: "0px 0px -12% 0px"** — shrinks the bottom of the viewport by 12%,
  so activation happens slightly before the element is fully centred.

### Section fade

All chapters, act-breaks, and the finale use a second observer (`initSectionFade`) that
adds/removes `.in-view` as sections enter the viewport at `threshold: 0.08`. CSS
translates this to a fade-in from slightly below (`translateY(28px)` → `translateY(0)`)
with a 0.55s ease-out transition.

---

## Technical: Bar-Chart Race Animation

The Overview tab in Explore mode features three animated bar-chart races:
Topic Race, Country Race, and Institution Race.

### Why a custom implementation

Plotly's native animation/slider system auto-plays immediately when rendered inside
Shiny's reactive output cycle, before the user has a chance to interact. The solution
is to **not use Plotly frames or sliders at all** — instead, all frame data is
serialized to a JavaScript global (`window._RACE_FRAMES[chart_id]`) and a custom
Play/Pause/Seek control drives `Plotly.animate()` manually.

### Data flow

```python
# Server builds year_values = {year: {category: value}}
# _make_race_html() serializes it:
frames_json = json.dumps(all_frames)  # [{year, x[], y[], text[], maxX}, ...]
init_script = f'window._RACE_FRAMES["{chart_id}"] = {frames_json};'
```

The static Plotly figure shows only the first frame. `race_controls.js` calls
`Plotly.animate()` on a `setInterval` to advance frame by frame at ~800ms per year.

### Off-screen bars (top-N mode)

For races that show only the top N categories (e.g., top 8 countries), bars that
fall out of the top N are placed at `y = -1` (off-screen below the axis) rather than
removed. This allows them to animate back in as a pure vertical slide when they
re-enter the top N — the bar's x-value is pre-set to the value it will have in its
next visible frame, so only the y-position changes on entry.

---

## User Flow: Story → Explore

The intended user journey:

```
Landing hero
    ↓ scroll
Chapter 1 (explosion chart)
    ↓ scroll
Chapter 2 (scrollytelling: topic shift)
    ↓ scroll
Chapter 3 (era composition)
    ↓ scroll
Chapter 4 (rising topics)
    ↓ scroll
Act break
    ↓ scroll
Chapter 5 (scrollytelling: geography)
    ↓ scroll
Chapter 6 (institution power shift)
    ↓ scroll
Chapter 7 (conscience chart)
    ↓ scroll
Finale + CTA button
    ↓ click "Open the Explorer"
Explore mode (Overview tab, unfiltered)
    ↓ explore
Topic / Geography / Institutions / Papers tabs
    ↑ cross-filter: click a bar in Institution Leaderboard
      → updates Institution filter AND loads Institution Profile
    ↑ cross-filter: click a bar in Topic Connections chart
      → updates Topic filter
```

### Cross-filtering in Explore

The Explore mode has two reactive values that bridge chart clicks to filter inputs:

- `_clicked_institution` — set by a click handler on the institution leaderboard bar chart
- `_clicked_topic` — set by a click handler on the topic connections network chart

Both use Plotly's FigureWidget `on_click` callback (not a standard output widget),
which allows Python-side reactivity without a full page reload. Clicking a bar in the
leaderboard simultaneously:
1. Sets `input.institution` via `ui.update_selectize("institution", ...)`
2. Sets `input.inst_profile_select` so the institution profile section below loads

### Filter reset

The filter bar has a `↺ Reset` button that returns all four filters (year range, topic,
country, institution) to their defaults and clears both reactive click values. This lets
users return to the unfiltered view without manually clearing each selector.

---

## Design System

### Color palette

| Role | Hex | Usage |
|---|---|---|
| Coral (brand primary) | `#cc785c` | Highlighted bars, lines, primary accent |
| Canvas background | `#faf9f5` | Page and chart background |
| Ink | `#141413` | Body text, titles |
| Muted | `#6c6a64` | Axis labels, secondary text |
| Hairline | `rgba(230,223,216,0.85)` | Grid lines |
| Grey bar | `rgba(140,135,128,0.45)` | Non-highlighted bars |
| Teal accent | `#5db8a6` | Secondary series |
| China Blue | `#4a7fb5` | China-specific lines in geography charts |

The 16-colour topic palette assigns each topic a consistent colour across every chart
in the dashboard. The palette is warm and muted (low saturation) to remain readable
on the cream canvas.

### Typography

Inter (system-stack fallback: `-apple-system`, `BlinkMacSystemFont`, `Segoe UI`, `Roboto`)
at two weights: regular (body) and medium (headings). Chart fonts match the prose font.

### Chart layout rules (applied by `apply_research_layout`)

- `paper_bgcolor = "rgba(0,0,0,0)"` — transparent chart background (shows canvas)
- `plot_bgcolor = "#faf9f5"` — matching canvas inside the plot area
- Left-aligned chart titles at 15px
- Horizontal legend at the bottom at 11px, constant item sizing
- Hoverlabel with cream background and coral border, 12px font
- Consistent margins: `l:52, r:26, t:52, b:40` (or 88 with legend)
