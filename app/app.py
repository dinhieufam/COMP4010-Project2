from __future__ import annotations

import sys
from pathlib import Path

import json as _json
import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio

PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP_ROOT = Path(__file__).resolve().parent
for path in (PROJECT_ROOT, APP_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from shiny import App, reactive, render, req, ui
from shinywidgets import output_widget, render_widget

import numpy as np

from charts.explorer import make_paper_cards_html
from charts.geography import country_counts_by_year
from charts.institutions import make_institution_leaderboard
from charts.network import make_topic_connections_ranked, make_topic_network
from charts.overview import make_papers_per_year
from charts.story_charts import (
    make_ch2_topic_bar,
    make_ch2_dl_neuro_line,
    make_ch2_topic_compare,
    make_ch3_era_composition,
    make_ch4_country_bar,
    make_ch4_us_china_line,
    make_ch5_institution_compare,
    make_ch6_conscience_chart,
    make_ch7_rising_topics,
)
from charts.streamgraph import make_topic_growth
from charts.theme import TEAL_ROSE_SCALE, TOPIC_COLORS, apply_research_layout, empty_figure
from charts.utils import country_display, explode_tokens
from data_loader import load_data
from filters import apply_filters

_CORAL = "#cc785c"
_GREY_BAR = "rgba(140, 135, 128, 0.45)"

# Shared dashboard color palette
_RACE_PALETTE = [
    "#cc785c",  # coral (primary)
    "#5db8a6",  # accent teal
    "#e8a55a",  # accent amber
    "#a9583e",  # coral-dark
    "#5db872",  # success green
    "#c9945a",  # deep amber
    "#7aac8e",  # sage green
    "#9b8db8",  # muted lavender
    "#6b9fc0",  # muted blue
    "#b5786a",  # rose
    "#d4a017",  # warm gold
    "#8b6c5c",  # warm brown
]


def _make_race_html(
    year_values: dict,
    categories: list,
    chart_id: str,
    btn_id: str,
    x_title: str,
    height: int = 500,
    x_fmt: str = ",.0f",
    x_suffix: str = "",
    top_n: int = None,
) -> str:
    """Animated bar-chart race driven entirely by race_controls.js.

    Builds a STATIC Plotly figure (first frame only, no Plotly frames/sliders)
    and serialises all frame data to window._RACE_FRAMES[chart_id].
    race_controls.js drives play/pause/seek via setInterval + Plotly.animate,
    avoiding Plotly's native animation system auto-playing in Shiny.

    top_n: if set, only the top-N categories per year are visible; others are
    placed at y=-2 (off-screen) so they animate in/out as ranks change.
    Colors are assigned from `categories` so they stay consistent across years.
    """
    years = sorted(year_values.keys())
    if not years or not categories:
        return '<p class="profile-prompt">Not enough data to animate.</p>'

    n = len(categories)
    n_visible = top_n if (top_n is not None and top_n < n) else n
    color_map = {
        cat: _RACE_PALETTE[i % len(_RACE_PALETTE)]
        for i, cat in enumerate(categories)
    }

    def _label(cat: str, val: float) -> str:
        short = cat if len(cat) <= 30 else cat[:28] + "…"
        return f"  {short}  {val:{x_fmt}}{x_suffix}"

    # Global x max across all years for a fixed, consistent axis
    global_max = max(
        (v for yd in year_values.values() for v in yd.values()),
        default=1.0,
    )
    max_x = global_max * 1.38

    # Pre-compute which cats are visible (top-N) in each year and their values.
    # Off-screen bars must use the x-value from their NEXT visible frame so that
    # only y changes on entry (pure vertical slide, no "grow from left").
    _visible_x: dict = {}   # {year: {cat: x_val}} — only top-N entries
    for y in years:
        yd = year_values.get(y, {})
        filled = {cat: float(yd.get(cat, 0.0)) for cat in categories}
        sc = sorted(filled.items(), key=lambda kv: kv[1])
        top = sc[-top_n:] if (top_n is not None and len(sc) > top_n) else sc
        _visible_x[y] = {cat: val for cat, val in top}

    def _offscreen_x(cat: str, year_idx: int) -> float:
        """Return the x-value cat will have in its nearest visible frame."""
        for i in range(year_idx + 1, len(years)):
            if cat in _visible_x[years[i]]:
                return _visible_x[years[i]][cat]
        for i in range(year_idx - 1, -1, -1):
            if cat in _visible_x[years[i]]:
                return _visible_x[years[i]][cat]
        return 0.0

    def _rank_dict(year_idx: int, year: int) -> dict:
        yd = year_values.get(year, {})
        filled = {cat: float(yd.get(cat, 0.0)) for cat in categories}
        sorted_cats = sorted(filled.items(), key=lambda kv: kv[1])
        if top_n is not None and len(sorted_cats) > top_n:
            off_cats = {cat for cat, _ in sorted_cats[:-top_n]}
            visible  = sorted_cats[-top_n:]
            result   = {cat: (val, rank) for rank, (cat, val) in enumerate(visible)}
            for cat in off_cats:
                result[cat] = (_offscreen_x(cat, year_idx), -1)
            return result
        return {cat: (val, rank) for rank, (cat, val) in enumerate(sorted_cats)}

    # Pre-compute all frames
    all_frames = []
    for yi, y in enumerate(years):
        rd = _rank_dict(yi, y)
        all_frames.append({
            "year": y,
            "maxX": max_x,
            "x":    [rd[cat][0] for cat in categories],
            "y":    [rd[cat][1] for cat in categories],
            "text": [
                _label(cat, rd[cat][0]) if rd[cat][1] >= 0 else ""
                for cat in categories
            ],
        })

    # Static first-frame figure -- no frames, no sliders, no auto-play
    rd0    = _rank_dict(0, years[0])
    max_x0 = max_x

    initial_data = [
        go.Bar(
            x=[rd0[cat][0]], y=[rd0[cat][1]],
            orientation="h", width=0.72, name=cat,
            marker_color=color_map[cat],
            text=[_label(cat, rd0[cat][0]) if rd0[cat][1] >= 0 else ""],
            textposition="outside", cliponaxis=False, showlegend=False,
            hovertemplate=f"{cat}: %{{x:{x_fmt}}}{x_suffix}<extra></extra>",
        )
        for cat in categories
    ]

    fig = go.Figure(data=initial_data)
    fig.update_layout(
        barmode="overlay",
        xaxis=dict(range=[0, max_x0], title=x_title, fixedrange=True, autorange=False),
        yaxis=dict(range=[-0.5, n_visible - 0.5], showticklabels=False,
                   showgrid=False, zeroline=False, fixedrange=True),
    )
    apply_research_layout(fig, height=height, legend=False)
    fig.update_layout(margin=dict(b=20, t=40))

    chart_html = pio.to_html(
        fig, full_html=False, include_plotlyjs="cdn",
        div_id=chart_id, config={"responsive": True},
    )

    year_id   = f"{chart_id}-year"
    slider_id = f"{chart_id}-slider"

    frames_json = _json.dumps(all_frames)
    init_script = (
        f'<script>window._RACE_FRAMES=window._RACE_FRAMES||{{}};'
        f'window._RACE_FRAMES["{chart_id}"]={frames_json};</script>'
    )
    controls_html = (
        f'<div class="race-controls">'
        f'<button class="race-play-btn" id="{btn_id}" '
        f'data-chart="{chart_id}" onclick="raceToggle(this)">'
        f'&#9654;&#xFE0E;  Play</button>'
        f'<span class="race-year-badge" id="{year_id}">{years[0]}</span>'
        f'</div>'
        f'<input type="range" class="race-slider" id="{slider_id}" '
        f'min="0" max="{len(years) - 1}" value="0" '
        f'oninput="raceSeek(\'{chart_id}\', parseInt(this.value))">'
    )
    return init_script + controls_html + chart_html


DATA = load_data()
PAPERS = DATA["papers"]
YEAR_MIN = int(PAPERS["year"].min())
YEAR_MAX = int(PAPERS["year"].max())
TOPIC_CHOICES = ["All"] + sorted(PAPERS["topic_label"].dropna().unique().tolist())
TOPIC_ONLY_CHOICES = sorted(PAPERS["topic_label"].dropna().unique().tolist())
_DEFAULT_TOPIC = "Natural Language Processing & LLMs" if "Natural Language Processing & LLMs" in TOPIC_ONLY_CHOICES else TOPIC_ONLY_CHOICES[0]
import re as _re
_COUNTRY_CODES = sorted(
    {
        part.strip()
        for value in PAPERS["countries_text"].dropna()
        for part in str(value).split(",")
        if _re.match(r"^[A-Z]{2}$", part.strip())
    }
)
COUNTRY_CHOICES = {"All": "All", **{code: country_display(code) for code in _COUNTRY_CODES}}
INSTITUTION_CHOICES = ["All"] + sorted(
    DATA["institution_year"]
    .loc[DATA["institution_year"]["institution"].ne("Unknown"), "institution"]
    .unique()
    .tolist()
)
_INST_ONLY_CHOICES = [i for i in INSTITUTION_CHOICES if i != "All"]
_TOP_INST = (
    DATA["institution_year"]
    .loc[DATA["institution_year"]["institution"].ne("Unknown")]
    .groupby("institution")["paper_count"].sum()
    .sort_values(ascending=False)
    .head(2)
    .index.tolist()
)
_COMPARE_A_DEFAULT = _TOP_INST[0] if _TOP_INST else (_INST_ONLY_CHOICES[0] if _INST_ONLY_CHOICES else "")
_COMPARE_B_DEFAULT = _TOP_INST[1] if len(_TOP_INST) > 1 else (_INST_ONLY_CHOICES[1] if len(_INST_ONLY_CHOICES) > 1 else "")


# ── UI helper functions ───────────────────────────────────────────────────────

def kpi_card(title: str, output_id: str, note: str):
    return ui.div(
        ui.div(title, class_="kpi-label"),
        ui.output_text(output_id),
        ui.div(note, class_="kpi-note"),
        class_="kpi-card",
    )


def panel(title: str, subtitle: str, output_id: str, *classes: str):
    return ui.div(
        ui.div(ui.h3(title), ui.p(subtitle), class_="panel-header"),
        output_widget(output_id),
        class_=" ".join(["panel", *classes]),
    )


# ── Story UI building blocks ──────────────────────────────────────────────────

def make_landing_hero():
    return ui.div(
        ui.div("1987 → 2025", class_="landing-tagline"),
        ui.div("90 → 5,823", class_="landing-counter"),
        ui.p(
            "From 1987 to 2025, NeurIPS changed from a small learning-and-neuroscience meeting "
            "into a global engine of modern AI. Its papers show how the field moved from studying "
            "learning to building systems that see, speak, generate, and decide.",
            class_="landing-thesis",
        ),
        ui.p("↓  scroll to begin", class_="scroll-cue"),
        class_="landing-hero",
    )


def story_chapter(
    num: int | str,
    eyebrow: str,
    claim: str,
    body: str,
    output_id: str,
    takeaway: str,
):
    return ui.div(
        ui.div(
            ui.div(str(num), class_="chapter-number"),
            ui.div(eyebrow, class_="eyebrow"),
            ui.h2(claim, class_="chapter-claim"),
            ui.p(body, class_="chapter-body"),
            ui.div(takeaway, class_="takeaway"),
            ui.p("↓", class_="scroll-cue"),
            class_="chapter-prose",
        ),
        ui.div(output_widget(output_id), class_="chapter-visual"),
        class_="chapter",
    )


def scrolly_chapter_multi(
    chapter_id: str,
    chapter_num: int | str,
    eyebrow: str,
    claim: str,
    steps: list[dict],
    output_ids: list[str],
    takeaway: str | None = None,
):
    """Scrollytelling chapter with one pre-rendered chart per prose step.

    The sticky pane stacks all charts with CSS opacity; JS toggles is-active.
    """
    chart_divs = [
        ui.div(
            output_widget(oid),
            class_="scrolly-chart" + (" is-active" if i == 0 else ""),
            **{"data-chapter": chapter_id, "data-step": str(i)},
        )
        for i, oid in enumerate(output_ids)
    ]
    last_i = len(steps) - 1
    step_divs = [
        ui.div(
            ui.div(f"0{i + 1}", class_="scrolly-step-number"),
            ui.h3(s["heading"]),
            ui.p(s["body"]),
            class_="scrolly-step" + (" scrolly-step-last" if i == last_i else ""),
            **{"data-chapter": chapter_id, "data-step": str(i)},
        )
        for i, s in enumerate(steps)
    ]
    trailer = [ui.div(takeaway, class_="takeaway")] if takeaway else []
    return ui.div(
        ui.div(
            ui.div(*chart_divs, class_="scrolly-charts-container"),
            class_="scrolly-sticky",
        ),
        ui.div(
            ui.div(
                ui.div(str(chapter_num), class_="chapter-number"),
                ui.div(eyebrow, class_="eyebrow"),
                ui.h2(claim, class_="chapter-claim"),
                class_="scrolly-chapter-header",
            ),
            *step_divs,
            *trailer,
            class_="scrolly-steps",
        ),
        class_="scrolly-chapter",
    )


def act_break(stat: str, caption: str, bridge: str | None = None):
    items: list = [
        ui.div(stat, class_="act-break-stat"),
        ui.p(caption, class_="act-break-caption"),
    ]
    if bridge:
        items.append(ui.p(bridge, class_="act-break-bridge"))
    return ui.div(*items, class_="act-break")


def make_finale():
    return ui.div(
        ui.h2("What did we learn?", class_="finale-claim"),
        ui.p(
            "NeurIPS began as a small community trying to understand learning. "
            "Four decades later, it is a global record of systems that speak, see, generate, "
            "decide, and reshape society. The history of NeurIPS is the history of AI moving "
            "from foundations to capabilities, from US campuses to global labs, "
            "and from technical ambition to questions of safety and responsibility.",
            class_="finale-sub",
        ),
        ui.p(
            "Now interrogate the evidence yourself.",
            class_="finale-sub finale-sub-small",
        ),
        ui.input_action_button(
            "go_to_explore",
            "② Open the Explorer →",
            class_="cta-button",
        ),
        class_="finale-section",
    )


# ── App UI ────────────────────────────────────────────────────────────────────

app_ui = ui.page_fluid(
    ui.include_css(APP_ROOT / "www" / "styles.css"),
    ui.include_js(APP_ROOT / "www" / "scrollytelling.js"),
    ui.include_js(APP_ROOT / "www" / "race_controls.js"),

    ui.div(
        ui.navset_pill(

            # ══════════════════════════════════════════
            # ①  STORY — guided documentary
            # ══════════════════════════════════════════
            ui.nav_panel(
                "① Story",
                ui.div(
                    # ── Landing ──────────────────────────
                    make_landing_hero(),

                    # ── Chapter 1 · The Explosion ────────
                    story_chapter(
                        num=1,
                        eyebrow="The Explosion",
                        claim="How does a 90-paper workshop become a 5,823-paper conference?",
                        body=(
                            "The answer is breakthroughs. NeurIPS grew 65× in 38 years, "
                            "but the growth wasn't steady — each surge follows a specific moment: "
                            "AlexNet in 2012, Transformers in 2017, ChatGPT in 2022. "
                            "The conference's size is a seismograph of the field's biggest leaps."
                        ),
                        output_id="story_ch1",
                        takeaway=(
                            "30,602 total papers across 38 years. "
                            "More than half were accepted after 2019 — "
                            "the Generative era is the conference's largest chapter by far."
                        ),
                    ),

                    # ── Chapter 2 · It Changed Its Mind ──
                    scrolly_chapter_multi(
                        chapter_id="ch2",
                        chapter_num=2,
                        eyebrow="It Changed Its Mind",
                        claim="From building foundations of learning to systems that see, speak, and act",
                        steps=[
                            {
                                "heading": "In 1987, the question was: how do machines learn?",
                                "body": (
                                    "Deep Learning dominated at 52%, Neuroscience at 20%, Optimization at 8%. "
                                    "The field was a collaboration between engineers and biologists — "
                                    "everyone focused on studying the mechanism of learning itself."
                                ),
                            },
                            {
                                "heading": "Both Deep Learning and Neuroscience faded in share.",
                                "body": (
                                    "Deep Learning fell from 52% to just 2–5% by the early 2000s as the field diversified, "
                                    "then resurged with AlexNet before settling at 8.6% by 2025. "
                                    "Neuroscience declined steadily from 20% to 1.4% — "
                                    "as building systems replaced studying brains."
                                ),
                            },
                            {
                                "heading": "By 2025, the question became: what can intelligent systems do?",
                                "body": (
                                    "NLP & LLMs 20.5%, Computer Vision 14.5%, Reinforcement Learning 10%, "
                                    "Generative Models 9%. The conference shifted from how machines learn "
                                    "to what they can see, say, and decide."
                                ),
                            },
                            {
                                "heading": "AI evolved from studying learning to building systems.",
                                "body": (
                                    "Same conference, 38 years apart. "
                                    "1987: foundations — deep learning, neuroscience, optimization. "
                                    "2025: applications — language, vision, action, generation."
                                ),
                            },
                        ],
                        output_ids=["story_ch2_s0", "story_ch2_s1", "story_ch2_s2", "story_ch2_s3"],
                        takeaway=(
                            "AI evolved from studying learning itself "
                            "to building systems that see, speak, and act."
                        ),
                    ),

                    # ── Chapter 3 · The Big Shift ─────────
                    story_chapter(
                        num=3,
                        eyebrow="The Big Shift",
                        claim="Which topics dominated each era?",
                        body=(
                            "Each bar is one research era; each colour is a topic. "
                            "Early NeurIPS was dominated by a few foundations — "
                            "deep learning, neuroscience, optimization. "
                            "By the Generative era, NLP, vision, generative models, and safety "
                            "all competed for a slice of a much larger conference. "
                            "NeurIPS diversified from a few dominant foundations "
                            "into many specialised application areas."
                        ),
                        output_id="story_ch3",
                        takeaway=(
                            "Deep learning's share fell from 52% to ~9% across eras — "
                            "not decline, but diversification. "
                            "The field fragmented into specialisations."
                        ),
                    ),

                    # ── Chapter 4 · Where the Momentum Is ─
                    story_chapter(
                        num=4,
                        eyebrow="Where the Momentum Is",
                        claim="NLP and Generative AI are accelerating — Safety is catching up",
                        body=(
                            "These lines show the 5 fastest-growing topics since 2015. "
                            "The field's next chapter is visible in its recent past."
                        ),
                        output_id="story_ch7",
                        takeaway=(
                            "NLP & LLMs grew from 4% in 2015 to 20.5% in 2025. "
                            "Safety & Alignment is accelerating from near-zero — "
                            "the field has started studying its own consequences."
                        ),
                    ),

                    # ── Act break ─────────────────────────
                    act_break(
                        "US 57% → 32%",
                        "From dominant to duopoly — in just a decade.",
                        bridge="The ideas changed first. Then the people and places producing those ideas changed too.",
                    ),

                    # ── Chapter 5 · AI Went Global ────────
                    scrolly_chapter_multi(
                        chapter_id="ch4",
                        chapter_num=5,
                        eyebrow="AI Went Global",
                        claim="How did geographic leadership change?",
                        steps=[
                            {
                                "heading": "As recently as 2015, the US held ~57% of author affiliations.",
                                "body": (
                                    "The Scaling era (2016–2021) was still dominated by US institutions. "
                                    "France, the UK, and Canada were the main international voices. "
                                    "These figures count paper-participations: one paper with authors "
                                    "from two countries counts for both."
                                ),
                            },
                            {
                                "heading": "By 2021, China had entered at 14% — and accelerating.",
                                "body": (
                                    "The Generative era opened the floodgates. "
                                    "Chinese universities and labs scaled their NeurIPS output faster "
                                    "than any other country in the dataset."
                                ),
                            },
                            {
                                "heading": "China closed 14 percentage points in four years.",
                                "body": (
                                    "US: ~44% → ~32%.  China: ~14% → ~28%. "
                                    "No other country has moved this fast in the dataset."
                                ),
                            },
                            {
                                "heading": "In 2025, the US and China nearly tied.",
                                "body": (
                                    "US ~32%, China ~28%. Hong Kong, UK, and Singapore follow. "
                                    "A field that felt American now has a genuinely global leaderboard."
                                ),
                            },
                        ],
                        output_ids=["story_ch4_s0", "story_ch4_s1", "story_ch4_s2", "story_ch4_s3"],
                        takeaway=(
                            "US ~57% → ~32%, China ~14% → ~28% in four years. "
                            "Shares count paper-participations — international co-authored papers "
                            "count toward each country. The convergence is still ongoing."
                        ),
                    ),

                    # ── Chapter 6 · Power Moved ────────────
                    story_chapter(
                        num=6,
                        eyebrow="Power Moved",
                        claim="Which institutions shaped the field, then and now?",
                        body=(
                            "Once modern AI scaled, the institutions shaping NeurIPS also changed: "
                            "not only universities, but global labs and industry teams. "
                            "Modern AI research requires scale — data, compute, infrastructure, large teams — "
                            "so industry labs and large global universities became more visible. "
                            "Coral bars = new entrants in the generative era; grey = US incumbents."
                        ),
                        output_id="story_ch5",
                        takeaway=(
                            "1990s: MIT, CMU, Caltech, Stanford, Berkeley. "
                            "2022–25: HKU, Google, Tsinghua, MIT, Peking — "
                            "a complete power shift from US campuses to a global mix of "
                            "universities and industry labs."
                        ),
                    ),

                    # ── Chapter 7 · The Field Grew a Conscience ──
                    story_chapter(
                        num=7,
                        eyebrow="The Field Grew a Conscience",
                        claim="As AI became more capable, NeurIPS started studying its consequences",
                        body=(
                            "Topics around safety, fairness, robustness, and rigorous evaluation "
                            "barely existed before 2015. After the scaling era, they became permanent. "
                            "The field that built powerful systems began asking: "
                            "are they reliable, fair, and safe?"
                        ),
                        output_id="story_ch6",
                        takeaway=(
                            "Safety & Alignment, Fairness & Privacy, and Data & Evaluation "
                            "were near-zero before 2015 — now they are among the fastest-growing areas. "
                            "Modern AI research increasingly studies its own risks "
                            "and measurement problems."
                        ),
                    ),

                    # ── Finale ────────────────────────────
                    make_finale(),

                    class_="story-scroll",
                ),
            ),

            # ══════════════════════════════════════════
            # ②  EXPLORE — investigative dashboard
            # ══════════════════════════════════════════
            ui.nav_panel(
                "② Explore",
                ui.div(
                    # ── Sticky filter bar ──────────────────
                    ui.div(
                        ui.div(
                            ui.input_slider("year_range", "Years", min=YEAR_MIN, max=YEAR_MAX, value=(YEAR_MIN, YEAR_MAX), sep=""),
                            class_="filter-item filter-item-slider",
                        ),
                        ui.div(
                            ui.input_selectize("topic", "Topic", choices=TOPIC_CHOICES, selected="All"),
                            class_="filter-item filter-item-select",
                        ),
                        ui.div(
                            ui.input_selectize("country", "Country", choices=COUNTRY_CHOICES, selected="All"),
                            class_="filter-item filter-item-select",
                        ),
                        ui.div(
                            ui.input_selectize("institution", "Institution", choices=INSTITUTION_CHOICES, selected="All"),
                            class_="filter-item filter-item-select",
                        ),
                        ui.div(
                            ui.input_action_button("reset_filters", "↺ Reset", class_="reset-button"),
                            class_="filter-item filter-item-reset",
                        ),
                        ui.div(
                            ui.output_text("status_papers"),
                            class_="filter-status-text",
                        ),
                        class_="explore-filter-bar",
                    ),
                    # ── Tab content ────────────────────────
                    ui.div(
                        ui.navset_underline(

                            # ── Tab 1: Overview ───────────
                            ui.nav_panel(
                                "Overview",
                                ui.div(
                                    # KPI Section
                                    ui.div(
                                        kpi_card("Papers", "kpi_papers", "After active filters"),
                                        kpi_card("Authors", "kpi_authors", "Unique contributors"),
                                        kpi_card("Institutions", "kpi_institutions_n", "Distinct affiliations"),
                                        kpi_card("Countries", "kpi_countries_n", "Represented"),
                                        class_="kpi-grid-4",
                                    ),
                                    # Growth Timeline
                                    panel("Growth Timeline", "How did publication volume evolve?", "explore_growth"),
                                    # Topic Race
                                    ui.div(
                                        ui.div(ui.h3("Topic Race"), ui.p("Topic share % per year — bars slide to new rank. Press Play to animate."), class_="panel-header"),
                                        ui.output_ui("explore_topic_race"),
                                        class_="panel",
                                    ),
                                    # Country Race
                                    ui.div(
                                        ui.div(ui.h3("Country Race"), ui.p("Top 8 countries by paper-participations per year. Press Play to animate."), class_="panel-header"),
                                        ui.output_ui("explore_country_race"),
                                        class_="panel",
                                    ),
                                    # Institution Race
                                    ui.div(
                                        ui.div(ui.h3("Institution Race"), ui.p("Top 10 institutions by papers per year. Press Play to animate."), class_="panel-header"),
                                        ui.output_ui("explore_institution_race"),
                                        class_="panel",
                                    ),
                                    # Insight Card
                                    ui.output_ui("explore_insight"),
                                    class_="explore-section",
                                ),
                            ),

                            # ── Tab 2: Topics ─────────────
                            ui.nav_panel(
                                "Topics",
                                ui.div(
                                    # Topic Selector
                                    ui.div(
                                        ui.input_selectize(
                                            "explore_topic_select",
                                            "Select topic",
                                            choices=TOPIC_ONLY_CHOICES,
                                            selected=_DEFAULT_TOPIC,
                                        ),
                                        class_="topic-selector-bar",
                                    ),
                                    # Topic Profile Header
                                    ui.div(
                                        ui.div(
                                            ui.output_text("topic_profile_name"),
                                            class_="topic-profile-name",
                                        ),
                                        ui.div(
                                            ui.div(
                                                ui.output_text("topic_current_share"),
                                                ui.div("Current Share", class_="topic-stat-label"),
                                                class_="topic-stat",
                                            ),
                                            ui.div(
                                                ui.output_text("topic_peak_year"),
                                                ui.div("Peak Year", class_="topic-stat-label"),
                                                class_="topic-stat",
                                            ),
                                            ui.div(
                                                ui.output_text("topic_growth_rate"),
                                                ui.div("Growth Rate", class_="topic-stat-label"),
                                                class_="topic-stat",
                                            ),
                                            ui.div(
                                                ui.output_text("topic_first_year"),
                                                ui.div("First Appeared", class_="topic-stat-label"),
                                                class_="topic-stat",
                                            ),
                                            class_="topic-stats-row",
                                        ),
                                        class_="topic-profile-header",
                                    ),
                                    # Topic Timeline
                                    panel("Topic Timeline", "How did this topic evolve over time?", "explore_topic_timeline"),
                                    # Top Countries
                                    panel("Top Countries", "Who researches this topic?", "explore_topic_countries"),
                                    # Top Institutions
                                    panel("Top Institutions", "Who leads this topic?", "explore_topic_institutions"),
                                    # Topic Connections
                                    panel("Topic Connections", "Co-occurrence weight between topics — which topics appear together most?", "topic_network"),
                                    class_="explore-section",
                                ),
                            ),

                            # ── Tab 3: Geography ──────────
                            ui.nav_panel(
                                "Geography",
                                ui.div(
                                    # Momentum View
                                    panel("Momentum View", "Who is growing fastest? Growth rate 2020–2025 vs 2015–2019.", "explore_country_momentum"),
                                    # Local country selector
                                    ui.div(
                                        ui.div("Country Profile", class_="profile-section-label"),
                                        ui.input_selectize(
                                            "geo_country_select",
                                            "Select a country to explore",
                                            choices=COUNTRY_CHOICES,
                                            selected="All",
                                        ),
                                        class_="geo-country-selector",
                                    ),
                                    # Country Profile (conditional on local selector)
                                    ui.div(
                                        ui.output_ui("country_profile_header"),
                                        panel("Paper Trend", "How has output from this country changed over time?", "country_paper_trend"),
                                        panel("Topic Distribution", "What does this country research?", "country_topic_dist"),
                                        panel("Top Institutions", "Which institutions in this country lead?", "country_top_institutions"),
                                        class_="profile-section",
                                    ),
                                    class_="explore-section",
                                ),
                            ),

                            # ── Tab 4: Institutions ───────
                            ui.nav_panel(
                                "Institutions",
                                ui.div(
                                    # Institution Ranking
                                    panel("Institution Ranking", "Top institutions by paper-participations. Click a bar to load its profile below.", "institution_leaderboard"),
                                    # Local institution selector
                                    ui.div(
                                        ui.div("Institution Profile", class_="profile-section-label"),
                                        ui.input_selectize(
                                            "inst_profile_select",
                                            "Select an institution to explore",
                                            choices=INSTITUTION_CHOICES,
                                            selected="All",
                                        ),
                                        class_="geo-country-selector",
                                    ),
                                    # Institution Profile
                                    ui.div(
                                        ui.output_ui("inst_profile_header"),
                                        panel("Publication Trend", "Papers per year for this institution.", "inst_paper_trend"),
                                        panel("Topic Mix", "Which topics does this institution research?", "inst_topic_mix"),
                                        class_="profile-section",
                                    ),
                                    # Institutional Comparison
                                    ui.div(
                                        ui.div("Institutional Comparison", class_="profile-section-label"),
                                        ui.div(
                                            ui.input_selectize("inst_compare_a", "Institution A", choices=_INST_ONLY_CHOICES, selected=_COMPARE_A_DEFAULT),
                                            ui.input_selectize("inst_compare_b", "Institution B", choices=_INST_ONLY_CHOICES, selected=_COMPARE_B_DEFAULT),
                                            class_="comparison-selectors",
                                        ),
                                        panel("Publications Comparison", "Papers per year for both institutions. Compare growth trajectories.", "inst_compare_chart"),
                                        class_="comparison-section",
                                    ),
                                    class_="explore-section",
                                ),
                            ),

                            # ── Tab 5: Papers ─────────────
                            ui.nav_panel(
                                "Papers",
                                ui.div(
                                    ui.div(
                                        ui.input_text(
                                            "explorer_search",
                                            None,
                                            placeholder="Search paper title or author name…",
                                        ),
                                        class_="papers-search-bar",
                                    ),
                                    ui.output_ui("papers_html"),
                                    class_="papers-section",
                                ),
                            ),

                            id="main_tabs",
                        ),
                        class_="explore-content",
                    ),
                    class_="explore-shell",
                ),
            ),

            id="mode_tabs",
            selected="① Story",
        ),
        class_="mode-switcher-wrap",
    ),
)


# ── Server ────────────────────────────────────────────────────────────────────

def server(input, output, session):
    _clicked_institution = reactive.Value(None)
    _clicked_topic = reactive.Value(None)

    # ── Explore: filter state ─────────────────────────────

    @reactive.Effect
    @reactive.event(input.reset_filters)
    def _reset_filters():
        ui.update_slider("year_range", value=(YEAR_MIN, YEAR_MAX))
        ui.update_selectize("topic", selected="All")
        ui.update_selectize("country", selected="All")
        ui.update_selectize("institution", selected="All")
        _clicked_institution.set(None)
        _clicked_topic.set(None)

    @reactive.Calc
    def filtered_papers():
        return apply_filters(
            PAPERS,
            input.year_range(),
            input.topic(),
            input.country(),
            input.institution(),
        )

    # ── Explore: KPI outputs ──────────────────────────────

    @output
    @render.text
    def kpi_papers():
        return f"{len(filtered_papers()):,}"

    @output
    @render.text
    def kpi_authors():
        data = filtered_papers()
        if data.empty:
            return "0"
        authors: set[str] = set()
        for txt in data["authors_text"].dropna():
            for a in str(txt).split(","):
                a = a.strip()
                if a:
                    authors.add(a)
        return f"{len(authors):,}"

    @output
    @render.text
    def kpi_institutions_n():
        data = filtered_papers()
        if data.empty:
            return "0"
        insts: set[str] = set()
        for txt in data["institutions_text"].dropna():
            for i in str(txt).split(","):
                i = i.strip()
                if i and i.lower() not in ("", "unknown"):
                    insts.add(i)
        return f"{len(insts):,}"

    @output
    @render.text
    def kpi_countries_n():
        data = filtered_papers()
        if data.empty:
            return "0"
        countries: set[str] = set()
        for txt in data["countries_text"].dropna():
            for c in str(txt).split(","):
                c = c.strip()
                if c:
                    countries.add(c)
        return f"{len(countries):,}"

    @output
    @render.text
    def status_papers():
        data = filtered_papers()
        n = len(data)
        yr = f"{int(data['year'].min())}–{int(data['year'].max())}" if not data.empty else "—"
        return f"{n:,} papers · {yr}"

    # ── Explore: Overview charts ──────────────────────────

    @output
    @render_widget
    def explore_growth():
        return make_papers_per_year(filtered_papers())

    # explore_topic_comp removed (replaced by topic race)
    # explore_geo_comp removed (replaced by country race)

    @output
    @render.ui
    def explore_topic_race():
        data = filtered_papers()
        if data.empty:
            return ui.p("No data with current filters.", class_="profile-prompt")
        topic_year = (
            data.dropna(subset=["topic_label"])
            .groupby(["year", "topic_label"]).size()
            .reset_index(name="count")
        )
        total_year = data.groupby("year").size().reset_index(name="total")
        merged = topic_year.merge(total_year, on="year")
        merged["pct"] = merged["count"] / merged["total"] * 100
        top_topics = (
            data["topic_label"].dropna().value_counts().head(12).index.tolist()
        )
        merged = merged[merged["topic_label"].isin(top_topics)]
        year_values: dict = {}
        for y in sorted(merged["year"].unique()):
            ydf = merged[merged["year"] == y]
            year_values[int(y)] = dict(zip(ydf["topic_label"], ydf["pct"]))
        return ui.HTML(_make_race_html(
            year_values=year_values,
            categories=top_topics,
            chart_id="topic-race-chart",
            btn_id="topic-race-btn",
            x_title="% of papers that year",
            height=560,
            x_fmt=".1f",
            x_suffix="%",
        ))

    @output
    @render.ui
    def explore_country_race():
        data = filtered_papers()
        if data.empty:
            return ui.p("No data with current filters.", class_="profile-prompt")
        counts = country_counts_by_year(data)
        if counts.empty:
            return ui.p("No country data.", class_="profile-prompt")
        N = 8
        # Per-year top-N; union of all ever-top countries becomes the category list
        val_map_by_year: dict = {}
        ever_top: list = []
        for y in sorted(counts["year"].unique()):
            ydf = counts[counts["year"] == y]
            vm = dict(zip(ydf["country"], ydf["participations"].astype(float)))
            val_map_by_year[int(y)] = vm
            top_n = ydf.nlargest(N, "participations")["country"].tolist()
            for c in top_n:
                if c not in ever_top:
                    ever_top.append(c)
        year_values: dict = {
            y: {cat: vm.get(cat, 0.0) for cat in ever_top}
            for y, vm in val_map_by_year.items()
        }
        return ui.HTML(_make_race_html(
            year_values=year_values,
            categories=ever_top,
            chart_id="country-race-chart",
            btn_id="country-race-btn",
            x_title="Paper-participations",
            height=400,
            top_n=8,
        ))

    @output
    @render.ui
    def explore_institution_race():
        data = filtered_papers()
        if data.empty:
            return ui.p("No data with current filters.", class_="profile-prompt")
        idata = explode_tokens(data, "institutions_text", "institution")
        if idata.empty:
            return ui.p("No institution data.", class_="profile-prompt")
        idata["institution"] = idata["institution"].str.replace(
            r"^arnegie ", "Carnegie ", regex=True
        )
        N = 10
        # Per-year top-N; union of all ever-top institutions becomes the category list
        val_map_by_year: dict = {}
        ever_top: list = []
        for y in sorted(idata["year"].unique()):
            ydf = (
                idata[idata["year"] == y]
                .groupby("institution")["paper_id"].count()
                .reset_index(name="papers")
            )
            vm = dict(zip(ydf["institution"], ydf["papers"].astype(float)))
            val_map_by_year[int(y)] = vm
            top_n = ydf.nlargest(N, "papers")["institution"].tolist()
            for inst in top_n:
                if inst not in ever_top:
                    ever_top.append(inst)
        year_values: dict = {
            y: {cat: vm.get(cat, 0.0) for cat in ever_top}
            for y, vm in val_map_by_year.items()
        }
        return ui.HTML(_make_race_html(
            year_values=year_values,
            categories=ever_top,
            chart_id="institution-race-chart",
            btn_id="institution-race-btn",
            x_title="Papers",
            height=480,
            top_n=10,
        ))

    @output
    @render.ui
    def explore_insight():
        data = filtered_papers()
        if data.empty:
            return ui.div()

        earliest = int(data["year"].min())
        latest   = int(data["year"].max())
        window   = min(5, (latest - earliest) // 2 + 1)

        early_data  = data[data["year"] <= earliest + window - 1]
        recent_data = data[data["year"] >= latest  - window + 1]

        early_count  = len(early_data)
        recent_count = len(recent_data)
        growth_x = recent_count / max(early_count, 1)

        def _pct(df: pd.DataFrame, topic: str) -> float:
            total = max(len(df), 1)
            return len(df[df["topic_label"] == topic]) / total * 100

        DL  = "Deep Learning Architectures"
        NLP = "Natural Language Processing & LLMs"
        CV  = "Computer Vision & Multimodal Learning"

        dl_e  = _pct(early_data,  DL);  dl_r  = _pct(recent_data, DL)
        nlp_e = _pct(early_data,  NLP); nlp_r = _pct(recent_data, NLP)
        cv_e  = _pct(early_data,  CV);  cv_r  = _pct(recent_data, CV)

        counts = country_counts_by_year(data)
        def _country_pct(yr_min: int, yr_max: int, country: str) -> float:
            c = counts[(counts["year"] >= yr_min) & (counts["year"] <= yr_max)]
            total = max(float(c["participations"].sum()), 1.0)
            share = float(c[c["country"] == country]["participations"].sum())
            return share / total * 100

        us_e  = _country_pct(earliest, earliest + window - 1, "United States")
        us_r  = _country_pct(latest  - window + 1, latest,   "United States")
        cn_e  = _country_pct(earliest, earliest + window - 1, "China")
        cn_r  = _country_pct(latest  - window + 1, latest,   "China")

        gap = abs(us_r - cn_r)
        geo_tail = (
            f"In {latest - window + 1}–{latest}, US {us_r:.0f}% vs China {cn_r:.0f}% — "
            + ("nearly tied." if gap < 5 else f"a gap of only {gap:.0f} pp.")
        )

        return ui.div(
            ui.div("Key Insights", class_="insight-card-title"),
            ui.div(
                ui.p(
                    f"Paper count grew {growth_x:.1f}× from {earliest}–{earliest + window - 1} "
                    f"({early_count:,} papers) to {latest - window + 1}–{latest} "
                    f"({recent_count:,} papers).",
                    class_="insight-line",
                ),
                class_="insight-bullet",
            ),
            ui.div(
                ui.p(
                    f"The field shifted from Deep Learning ({dl_e:.0f}% → {dl_r:.0f}%) "
                    f"to NLP & LLMs ({nlp_e:.0f}% → {nlp_r:.0f}%) "
                    f"and Computer Vision ({cv_e:.0f}% → {cv_r:.0f}%). "
                    f"NeurIPS moved from studying learning itself to building systems that see, speak, and act.",
                    class_="insight-line",
                ),
                class_="insight-bullet",
            ),
            ui.div(
                ui.p(
                    f"US participation fell from {us_e:.0f}% to {us_r:.0f}%; "
                    f"China rose from {cn_e:.0f}% to {cn_r:.0f}%. "
                    + geo_tail,
                    class_="insight-line",
                ),
                class_="insight-bullet",
            ),
            class_="insight-card",
        )

    # ── Explore: Topic profile ────────────────────────────

    @reactive.Calc
    def _selected_topic_data():
        topic = input.explore_topic_select()
        return filtered_papers()[filtered_papers()["topic_label"] == topic]

    @reactive.Calc
    def _selected_topic_yearly():
        """Returns (topic_by_year, total_by_year, share_by_year) DataFrames."""
        topic = input.explore_topic_select()
        data = filtered_papers()
        total = data.groupby("year")["paper_id"].count().rename("total")
        tdf = data[data["topic_label"] == topic].groupby("year")["paper_id"].count().rename("count")
        combined = pd.concat([total, tdf], axis=1).fillna(0)
        combined["share"] = combined["count"] / combined["total"].replace(0, np.nan) * 100
        return combined.reset_index()

    @output
    @render.text
    def topic_profile_name():
        return input.explore_topic_select()

    @output
    @render.text
    def topic_current_share():
        yearly = _selected_topic_yearly()
        if yearly.empty:
            return "—"
        latest = yearly[yearly["year"] == yearly["year"].max()]
        share = float(latest["share"].iloc[0]) if not latest.empty else 0.0
        return f"{share:.1f}%"

    @output
    @render.text
    def topic_peak_year():
        yearly = _selected_topic_yearly()
        if yearly.empty or yearly["share"].isna().all():
            return "—"
        return str(int(yearly.loc[yearly["share"].idxmax(), "year"]))

    @output
    @render.text
    def topic_growth_rate():
        yearly = _selected_topic_yearly()
        if yearly.empty:
            return "—"
        early = yearly[yearly["year"] <= yearly["year"].min() + 4]["share"].mean()
        recent = yearly[yearly["year"] >= yearly["year"].max() - 4]["share"].mean()
        if early and early > 0:
            rate = (recent - early) / early * 100
            sign = "+" if rate >= 0 else ""
            return f"{sign}{rate:.0f}%"
        return "—"

    @output
    @render.text
    def topic_first_year():
        tdata = _selected_topic_data()
        if tdata.empty:
            return "—"
        return str(int(tdata["year"].min()))

    @output
    @render_widget
    def explore_topic_timeline():
        topic = input.explore_topic_select()
        yearly = _selected_topic_yearly()
        if yearly.empty:
            return empty_figure("Topic Timeline")
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=yearly["year"].tolist(),
            y=yearly["share"].fillna(0).tolist(),
            mode="lines+markers",
            name=topic,
            line=dict(color=_CORAL, width=2.5),
            fill="tozeroy",
            fillcolor="rgba(204,120,92,0.10)",
            hovertemplate="%{x}: %{y:.1f}%<extra></extra>",
        ))
        fig.update_layout(
            title=f"{topic} · % share of NeurIPS papers",
            xaxis_title="Year",
            yaxis_title="Share (%)",
        )
        apply_research_layout(fig, height=320, legend=False)
        return fig

    @output
    @render_widget
    def explore_topic_countries():
        topic = input.explore_topic_select()
        tdata = _selected_topic_data()
        if tdata.empty:
            return empty_figure("Top Countries")
        cdata = explode_tokens(tdata, "countries_text", "country")
        if cdata.empty:
            return empty_figure("Top Countries", "No country metadata.")
        cdata["country"] = cdata["country"].apply(country_display)
        grouped = (
            cdata.groupby("country", as_index=False)
            .agg(papers=("paper_id", "count"))
            .sort_values("papers", ascending=True)
            .tail(12)
        )
        fig = go.Figure(go.Bar(
            x=grouped["papers"].tolist(),
            y=grouped["country"].tolist(),
            orientation="h",
            marker_color=_CORAL,
            hovertemplate="%{y}: %{x:,}<extra></extra>",
        ))
        fig.update_layout(title=f"Top countries · {topic}", xaxis_title="Papers")
        apply_research_layout(fig, height=340, legend=False)
        return fig

    @output
    @render_widget
    def explore_topic_institutions():
        topic = input.explore_topic_select()
        tdata = _selected_topic_data()
        if tdata.empty:
            return empty_figure("Top Institutions")
        idata = explode_tokens(tdata, "institutions_text", "institution")
        if idata.empty:
            return empty_figure("Top Institutions", "No institution metadata.")
        grouped = (
            idata.groupby("institution", as_index=False)
            .agg(papers=("paper_id", "count"))
            .sort_values("papers", ascending=True)
            .tail(12)
        )
        fig = go.Figure(go.Bar(
            x=grouped["papers"].tolist(),
            y=grouped["institution"].tolist(),
            orientation="h",
            marker_color=_CORAL,
            hovertemplate="%{y}: %{x:,}<extra></extra>",
        ))
        fig.update_layout(title=f"Top institutions · {topic}", xaxis_title="Papers")
        apply_research_layout(fig, height=340, legend=False)
        return fig

    # ── Explore: Geography extras ─────────────────────────

    @output
    @render_widget
    def explore_country_momentum():
        data = filtered_papers()
        counts = country_counts_by_year(data)
        if counts.empty:
            return empty_figure("Country Momentum")
        recent = counts[counts["year"] >= 2020].groupby("country")["participations"].sum()
        earlier = counts[(counts["year"] >= 2015) & (counts["year"] < 2020)].groupby("country")["participations"].sum()
        rows = []
        for country in recent.index:
            r = float(recent[country])
            e = float(earlier.get(country, 0))
            if r >= 20 and e > 0:
                rows.append({"country": country, "growth": (r - e) / e * 100})
        if not rows:
            return empty_figure("Country Momentum", "Not enough data in both periods.")
        df = pd.DataFrame(rows).sort_values("growth", ascending=True).tail(16)
        colors = [_CORAL if g > 0 else _GREY_BAR for g in df["growth"].tolist()]
        fig = go.Figure(go.Bar(
            x=df["growth"].tolist(),
            y=df["country"].tolist(),
            orientation="h",
            marker_color=colors,
            hovertemplate="%{y}: %{x:+.0f}%<extra></extra>",
        ))
        fig.update_layout(
            title="Country growth rate · 2020–2025 vs 2015–2019",
            xaxis_title="Growth (%)",
        )
        apply_research_layout(fig, height=440, legend=False)
        return fig


    # ── Explore: Topics tab — Topic Connections ───────────

    @output
    @render_widget
    def topic_network():
        topic = input.explore_topic_select()
        fw = go.FigureWidget(
            make_topic_connections_ranked(filtered_papers(), DATA["topic_edges"], topic)
        )

        def _on_click(trace, points, selector):
            ys = list(points.ys) if points.ys else []
            if ys:
                _clicked_topic.set(str(ys[0]))

        for trace in fw.data:
            trace.on_click(_on_click)
        return fw

    # ── Explore: Geography tab ────────────────────────────

    @output
    @render_widget
    def explore_country_ranking():
        data = filtered_papers()
        counts = country_counts_by_year(data)
        if counts.empty:
            return empty_figure("Country Ranking")
        totals = (
            counts.groupby("country", as_index=False)["participations"].sum()
            .sort_values("participations", ascending=True)
            .tail(15)
        )
        fig = go.Figure(go.Bar(
            x=totals["participations"].tolist(),
            y=totals["country"].tolist(),
            orientation="h",
            marker_color=_CORAL,
            hovertemplate="%{y}: %{x:,} participations<extra></extra>",
        ))
        fig.update_layout(title="Country Ranking · total paper-participations", xaxis_title="Paper-participations")
        apply_research_layout(fig, height=440, legend=False)
        return fig

    @output
    @render.ui
    def country_profile_header():
        country = input.geo_country_select()
        if country == "All":
            return ui.p("→ Select a country above to view its profile.", class_="profile-prompt")
        return ui.div(f"Country Profile · {country_display(country)}", class_="profile-section-label")

    @output
    @render_widget
    def country_paper_trend():
        country = input.geo_country_select()
        if country == "All":
            return empty_figure("Paper Trend", "Select a country above to see the trend.")
        country_name = country_display(country)
        data = filtered_papers()
        counts = country_counts_by_year(data)
        cdata = counts[counts["country"] == country_name].sort_values("year")
        if cdata.empty:
            return empty_figure("Paper Trend", f"No data for {country_name}.")
        fig = go.Figure(go.Scatter(
            x=cdata["year"].tolist(), y=cdata["participations"].tolist(),
            mode="lines+markers", line=dict(color=_CORAL, width=2.5),
            fill="tozeroy", fillcolor="rgba(204,120,92,0.10)",
            hovertemplate="%{x}: %{y:,}<extra></extra>",
        ))
        fig.update_layout(title=f"Paper-participations per year · {country_name}", xaxis_title="Year", yaxis_title="Papers")
        apply_research_layout(fig, height=340, legend=False)
        return fig

    @output
    @render_widget
    def country_topic_dist():
        country = input.geo_country_select()
        if country == "All":
            return empty_figure("Topic Distribution", "Select a country above to see topic breakdown.")
        country_name = country_display(country)
        data = filtered_papers()
        col = "countries_text"
        mask = data[col].fillna("").str.contains(country, case=False, regex=False)
        cdata = data[mask]
        if cdata.empty:
            return empty_figure("Topic Distribution", f"No data for {country_name}.")
        topic_counts = (
            cdata.groupby("topic_label", as_index=False)["paper_id"].count()
            .rename(columns={"paper_id": "papers"})
            .sort_values("papers", ascending=True)
        )
        fig = go.Figure(go.Bar(
            x=topic_counts["papers"].tolist(), y=topic_counts["topic_label"].tolist(),
            orientation="h", marker_color=_CORAL,
            hovertemplate="%{y}: %{x:,}<extra></extra>",
        ))
        fig.update_layout(title=f"Topic distribution · {country_name}", xaxis_title="Papers")
        apply_research_layout(fig, height=400, legend=False)
        return fig

    @output
    @render_widget
    def country_top_institutions():
        country = input.geo_country_select()
        if country == "All":
            return empty_figure("Top Institutions", "Select a country above to see top institutions.")
        country_name = country_display(country)
        data = filtered_papers()
        col = "countries_text"
        mask = data[col].fillna("").str.contains(country, case=False, regex=False)
        cdata = data[mask]
        if cdata.empty:
            return empty_figure("Top Institutions", f"No data for {country_name}.")
        idata = explode_tokens(cdata, "institutions_text", "institution")
        if idata.empty:
            return empty_figure("Top Institutions", "No institution metadata.")
        grouped = (
            idata.groupby("institution", as_index=False)["paper_id"].count()
            .rename(columns={"paper_id": "papers"})
            .sort_values("papers", ascending=True)
            .tail(12)
        )
        fig = go.Figure(go.Bar(
            x=grouped["papers"].tolist(), y=grouped["institution"].tolist(),
            orientation="h", marker_color=_CORAL,
            hovertemplate="%{y}: %{x:,}<extra></extra>",
        ))
        fig.update_layout(title=f"Top institutions · {country_name}", xaxis_title="Papers")
        apply_research_layout(fig, height=380, legend=False)
        return fig

    # ── Explore: Institutions tab ─────────────────────────

    @output
    @render_widget
    def institution_leaderboard():
        fw = go.FigureWidget(make_institution_leaderboard(filtered_papers()))

        def _on_click(trace, points, selector):
            if points.point_inds:
                idx = points.point_inds[0]
                y_data = list(trace.y) if trace.y is not None else []
                if idx < len(y_data):
                    _clicked_institution.set(str(y_data[idx]))

        for trace in fw.data:
            trace.on_click(_on_click)
        return fw

    @output
    @render.ui
    def inst_profile_header():
        name = input.inst_profile_select()
        if not name or name == "All":
            return ui.p("→ Select an institution above or click a bar in the ranking to view its profile.", class_="profile-prompt")
        return ui.div(f"Institution Profile · {name}", class_="profile-section-label")

    @output
    @render_widget
    def inst_paper_trend():
        name = input.inst_profile_select()
        if not name or name == "All":
            return empty_figure("Publication Trend", "Select an institution above to load.")
        data = filtered_papers()
        idata = explode_tokens(data, "institutions_text", "institution")
        idata = idata[idata["institution"] == name]
        if idata.empty:
            return empty_figure("Publication Trend", f"No data for {name}.")
        yearly = idata.groupby("year")["paper_id"].count().reset_index(name="papers")
        fig = go.Figure(go.Scatter(
            x=yearly["year"].tolist(), y=yearly["papers"].tolist(),
            mode="lines+markers", line=dict(color=_CORAL, width=2.5),
            fill="tozeroy", fillcolor="rgba(204,120,92,0.10)",
            hovertemplate="%{x}: %{y:,}<extra></extra>",
        ))
        fig.update_layout(title=f"Papers per year · {name}", xaxis_title="Year", yaxis_title="Papers")
        apply_research_layout(fig, height=320, legend=False)
        return fig

    @output
    @render_widget
    def inst_topic_mix():
        name = input.inst_profile_select()
        if not name or name == "All":
            return empty_figure("Topic Mix", "Select an institution above to load.")
        data = filtered_papers()
        idata = explode_tokens(data, "institutions_text", "institution")
        idata = idata[idata["institution"] == name]
        if idata.empty:
            return empty_figure("Topic Mix", f"No data for {name}.")
        topics = (
            idata.groupby("topic_label")["paper_id"].count()
            .sort_values(ascending=True)
            .reset_index(name="papers")
        )
        fig = go.Figure(go.Bar(
            x=topics["papers"].tolist(), y=topics["topic_label"].tolist(),
            orientation="h", marker_color=_CORAL,
            hovertemplate="%{y}: %{x:,}<extra></extra>",
        ))
        fig.update_layout(title=f"Topic mix · {name}", xaxis_title="Papers")
        apply_research_layout(fig, height=380, legend=False)
        return fig

    @output
    @render_widget
    def inst_compare_chart():
        a = input.inst_compare_a()
        b = input.inst_compare_b()
        data = filtered_papers()
        if not a or not b or data.empty:
            return empty_figure("Publications Comparison", "Select two institutions above.")
        idata = explode_tokens(data, "institutions_text", "institution")
        all_years = sorted(data["year"].unique())

        def _yearly(inst: str) -> dict:
            s = idata[idata["institution"] == inst].groupby("year")["paper_id"].count()
            return {y: int(s.get(y, 0)) for y in all_years}

        ya, yb = _yearly(a), _yearly(b)
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=all_years, y=[ya[y] for y in all_years],
            mode="lines+markers", name=a[:40],
            line=dict(color=_CORAL, width=2.5),
            hovertemplate=f"{a[:30]}<br>%{{x}}: %{{y:,}}<extra></extra>",
        ))
        fig.add_trace(go.Scatter(
            x=all_years, y=[yb[y] for y in all_years],
            mode="lines+markers", name=b[:40],
            line=dict(color=_GREY_BAR.replace("0.45", "1"), width=2.5),
            hovertemplate=f"{b[:30]}<br>%{{x}}: %{{y:,}}<extra></extra>",
        ))
        fig.update_layout(title=f"Publications · {a[:25]} vs {b[:25]}", xaxis_title="Year", yaxis_title="Papers")
        apply_research_layout(fig, height=360, legend=True)
        return fig

    # ── Explore: Papers tab ───────────────────────────────

    @reactive.Calc
    def explorer_papers():
        data = filtered_papers()
        search = input.explorer_search().strip().lower()
        if search:
            mask = (
                data["title"].fillna("").str.lower().str.contains(search, regex=False)
                | data["authors_text"].fillna("").str.lower().str.contains(search, regex=False)
            )
            data = data[mask]
        return data

    @output
    @render.ui
    def papers_html():
        return ui.HTML(make_paper_cards_html(explorer_papers()))

    # ── Explore: Cross-filter effects ─────────────────────

    @reactive.Effect
    def _institution_cross_filter():
        name = _clicked_institution.get()
        if name and name in INSTITUTION_CHOICES:
            ui.update_selectize("institution", selected=name)
            ui.update_selectize("inst_profile_select", selected=name)

    @reactive.Effect
    def _topic_cross_filter():
        name = _clicked_topic.get()
        if name and name in TOPIC_CHOICES:
            ui.update_selectize("topic", selected=name)

    # ── Story: chapter chart renders (use full PAPERS, not filtered) ──────────

    @output
    @render_widget
    def story_ch1():
        return make_papers_per_year(PAPERS)

    # Ch2 — one pre-rendered chart per step (CSS toggles visibility)
    @output
    @render_widget
    def story_ch2_s0():
        return make_ch2_topic_bar(PAPERS, year=1987, highlight="Deep Learning Architectures")

    @output
    @render_widget
    def story_ch2_s1():
        return make_ch2_dl_neuro_line(PAPERS)

    @output
    @render_widget
    def story_ch2_s2():
        return make_ch2_topic_bar(PAPERS, year=2025, highlight="Natural Language Processing & LLMs")

    @output
    @render_widget
    def story_ch2_s3():
        return make_ch2_topic_compare(PAPERS)

    @output
    @render_widget
    def story_ch3():
        return make_ch3_era_composition(PAPERS)

    # Ch4 — one pre-rendered chart per step (CSS toggles visibility)
    @output
    @render_widget
    def story_ch4_s0():
        return make_ch4_country_bar(PAPERS, year=2015, highlight="United States")

    @output
    @render_widget
    def story_ch4_s1():
        return make_ch4_country_bar(PAPERS, year=2021, highlight="China")

    @output
    @render_widget
    def story_ch4_s2():
        return make_ch4_us_china_line(PAPERS)

    @output
    @render_widget
    def story_ch4_s3():
        return make_ch4_country_bar(PAPERS, year=2025, highlight="China")

    @output
    @render_widget
    def story_ch5():
        return make_ch5_institution_compare(DATA["institution_year"])

    @output
    @render_widget
    def story_ch6():
        return make_ch6_conscience_chart(PAPERS)

    @output
    @render_widget
    def story_ch7():
        return make_ch7_rising_topics(PAPERS)

    # ── Story: CTA → switch to Explore ───────────────────

    @reactive.Effect
    @reactive.event(input.go_to_explore)
    def _go_to_explore():
        ui.update_navs("mode_tabs", selected="② Explore")


app = App(app_ui, server)
