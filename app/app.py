from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP_ROOT = Path(__file__).resolve().parent
for path in (PROJECT_ROOT, APP_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from shiny import App, reactive, render, ui
from shinywidgets import output_widget, render_widget

from charts.collaboration import make_collaboration_flow
from charts.coverage import make_coverage_strip
from charts.creative import (
    make_institution_country_orbit,
    make_metadata_weather,
    make_paper_universe,
    make_research_bloom,
    make_research_river,
    make_topic_dna,
    make_topic_galaxy,
    make_topic_race,
)
from charts.explorer import paper_table
from charts.forecast import make_forecast_focus
from charts.geography import make_country_map
from charts.heatmap import make_topic_heatmap
from charts.institutions import make_institution_leaderboard
from charts.momentum import make_topic_momentum, topic_momentum_table
from charts.network import make_topic_network
from charts.provenance import SOURCE_LABELS, make_affiliation_provenance
from charts.streamgraph import make_topic_growth
from charts.utils import explode_tokens
from data_loader import load_data
from filters import apply_filters


DATA = load_data()
PAPERS = DATA["papers"]
YEAR_MIN = int(PAPERS["year"].min())
YEAR_MAX = int(PAPERS["year"].max())
TOPIC_CHOICES = ["All"] + sorted(PAPERS["topic_label"].dropna().unique().tolist())
TOPIC_CHIPS = PAPERS["topic_label"].value_counts().head(5).index.tolist()
COUNTRY_CHOICES = ["All"] + sorted(
    {part.strip() for value in PAPERS["countries_text"].dropna() for part in str(value).split(",") if part.strip()}
)
INSTITUTION_CHOICES = ["All"] + sorted(
    {part.strip() for value in PAPERS["institutions_text"].dropna() for part in str(value).split(",") if part.strip()}
)


def percent(value: float, digits: int = 0) -> str:
    if pd.isna(value):
        return "0%"
    return f"{value * 100:.{digits}f}%"


def kpi_card(title: str, output_id: str, note: str):
    return ui.div(
        ui.div(title, class_="kpi-label"),
        ui.output_text(output_id),
        ui.div(note, class_="kpi-note"),
        class_="kpi-card",
    )


def pulse_card(title: str, output_id: str, note_id: str):
    return ui.div(
        ui.div(title, class_="pulse-label"),
        ui.output_text(output_id),
        ui.div(ui.output_text(note_id), class_="pulse-note"),
        class_="pulse-card",
    )


def panel(title: str, subtitle: str, output_id: str, *classes: str):
    return ui.div(
        ui.div(ui.h3(title), ui.p(subtitle), class_="panel-header"),
        output_widget(output_id),
        class_=" ".join(["panel", *classes]),
    )


def creative_tab(title: str, subtitle: str, output_id: str):
    return ui.nav_panel(
        title,
        ui.div(
            ui.div(ui.h3(title), ui.p(subtitle), class_="panel-header"),
            output_widget(output_id),
            class_="creative-tab-panel",
        ),
    )


app_ui = ui.page_fluid(
    ui.include_css(APP_ROOT / "www" / "styles.css"),
    ui.div(
        ui.div(
            ui.div(
                ui.div("NeurIPS Observatory", class_="brand-mark"),
                ui.h1("AI Conference Research Observatory"),
                ui.p("A soft-pink analytical atlas of NeurIPS topics, geography, institutions, forecasts, and metadata confidence."),
                class_="brand-block",
            ),
            ui.div(
                ui.input_select("venue", "Venue", choices=["NeurIPS"], selected="NeurIPS"),
                ui.input_slider("year_range", "Years", min=YEAR_MIN, max=YEAR_MAX, value=(YEAR_MIN, YEAR_MAX), sep=""),
                ui.input_selectize("topic", "Topic", choices=TOPIC_CHOICES, selected="All"),
                ui.input_selectize("country", "Country", choices=COUNTRY_CHOICES, selected="All"),
                ui.input_selectize("institution", "Institution", choices=INSTITUTION_CHOICES, selected="All"),
                ui.input_action_button("reset_filters", "Reset filters", class_="reset-button"),
                class_="filter-stack",
            ),
            ui.div(
                ui.span("Curated 16-topic taxonomy"),
                ui.span("30,602 NeurIPS papers"),
                ui.span("Coverage-aware affiliations"),
                ui.span("Forecast + collaboration views"),
                class_="sidebar-meta",
            ),
            class_="sidebar",
        ),
        ui.div(
            ui.div(
                ui.div(
                    ui.div("Research dashboard", class_="eyebrow"),
                    ui.h2("NeurIPS research landscape"),
                    ui.p("Explore topic shifts, metadata quality, global participation, institutional output, and forecast signals."),
                    class_="page-title",
                ),
                ui.div(
                    ui.span("Soft rose analytical theme", class_="status-pill"),
                    ui.span(ui.output_text("status_papers"), class_="status-pill subtle"),
                    class_="status-strip",
                ),
                class_="topbar",
            ),
            ui.div(
                kpi_card("Filtered papers", "kpi_papers", "Unique proceedings papers"),
                kpi_card("Year span", "kpi_years", "Visible range after filters"),
                kpi_card("Topics represented", "kpi_topics", "Primary topic labels"),
                kpi_card("Known institutions", "kpi_institutions", "Paper-level coverage"),
                kpi_card("Known countries", "kpi_countries", "Paper-level coverage"),
                kpi_card("Review workload", "kpi_review", "Topic audit flags"),
                class_="kpi-grid",
            ),
            ui.div(
                ui.div(
                    ui.div("Research Pulse", class_="section-eyebrow"),
                    ui.h3("Live interpretation of the current selection"),
                    ui.p("These cards summarize rising topics, collaboration breadth, metadata confidence, and provenance mix."),
                    class_="section-intro",
                ),
                ui.div(
                    pulse_card("Rising topic", "pulse_rising", "pulse_rising_note"),
                    pulse_card("Collaboration breadth", "pulse_collab", "pulse_collab_note"),
                    pulse_card("Affiliation confidence", "pulse_confidence", "pulse_confidence_note"),
                    pulse_card("Dominant source", "pulse_source", "pulse_source_note"),
                    class_="pulse-grid",
                ),
                class_="research-pulse",
            ),
            ui.div(
                ui.span("Quick topic focus", class_="chip-label"),
                *[
                    ui.input_action_button(f"topic_chip_{idx}", topic, class_="topic-chip")
                    for idx, topic in enumerate(TOPIC_CHIPS)
                ],
                class_="topic-chip-row",
            ),
            ui.div(
                ui.div(
                    ui.div("Creative Visual Lab", class_="section-eyebrow"),
                    ui.h3("Experimental views that turn the NeurIPS corpus into galaxies, blooms, rivers, races, weather, orbits, DNA, and starfields."),
                    ui.p("All eight creative panels respond to the same year/topic/country/institution filters. Use the tabs to explore without overcrowding the dashboard."),
                    class_="creative-intro",
                ),
                ui.navset_tab(
                    creative_tab("Topic Galaxy", "A glowing constellation of topic scale and secondary-topic links.", "topic_galaxy"),
                    creative_tab("Research River", "Eras flow into dominant research themes like a braided river.", "research_river"),
                    creative_tab("Topic Race", "Annual rank changes show which topics climb, fall, and hold leadership.", "topic_race"),
                    creative_tab("Research Bloom", "A radial rose where topic petals encode scale and recent growth.", "research_bloom"),
                    creative_tab("Collaboration Orbits", "Institutions orbit around country hubs through participation links.", "institution_country_orbit"),
                    creative_tab("Metadata Weather", "Data quality becomes a yearly climate map of sunny and cloudy periods.", "metadata_weather"),
                    creative_tab("Paper Universe", "A sampled title/topic TF-IDF starfield of individual papers.", "paper_universe"),
                    creative_tab("Topic DNA", "A compact barcode of yearly topic composition.", "topic_dna"),
                    id="creative_tabs",
                ),
                class_="creative-lab",
            ),
            ui.div(
                panel("Topic growth", "Stacked history with broad-view forecast overlays.", "topic_growth", "hero-panel"),
                panel("Forecast focus", "Observed vs forecast trajectories for leading filtered topics.", "forecast_focus"),
                panel("Topic momentum", "Recent share changes reveal rising and fading research areas.", "topic_momentum"),
                panel("Topic heatmap", "Relative topic share by year.", "topic_heatmap", "tall"),
                panel("Global footprint", "Country-paper participations over time; multi-country papers count once per country.", "country_map", "tall"),
                panel("Country-topic exposure", "Sankey flow from leading countries into leading topics.", "collaboration_flow"),
                panel("Metadata coverage", "Filtered paper-level coverage and confidence over time.", "coverage_strip", "compact-panel"),
                panel("Affiliation provenance", "How affiliation data was recovered across sources.", "affiliation_provenance", "compact-panel"),
                panel("Institutions", "Institution-paper participation leaderboard.", "institution_leaderboard"),
                panel("Topic network", "Filtered topic similarity co-structure.", "topic_network"),
                ui.div(
                    ui.div(ui.h3("Paper Explorer"), ui.p("Searchable paper-level audit table with topic, affiliation, confidence, and link fields."), class_="panel-header"),
                    ui.output_data_frame("papers_table"),
                    class_="panel table-panel",
                ),
                class_="dashboard-grid",
            ),
            class_="dashboard-main",
        ),
        class_="app-shell",
    ),
)


def server(input, output, session):
    @reactive.Effect
    @reactive.event(input.reset_filters)
    def _reset_filters():
        ui.update_slider("year_range", value=(YEAR_MIN, YEAR_MAX))
        ui.update_selectize("topic", selected="All")
        ui.update_selectize("country", selected="All")
        ui.update_selectize("institution", selected="All")

    def _bind_topic_chip(idx: int, topic: str):
        @reactive.Effect
        @reactive.event(getattr(input, f"topic_chip_{idx}"))
        def _topic_chip_click():
            ui.update_selectize("topic", selected=topic)

    for chip_idx, chip_topic in enumerate(TOPIC_CHIPS):
        _bind_topic_chip(chip_idx, chip_topic)

    @reactive.Calc
    def filtered_papers():
        return apply_filters(
            PAPERS,
            input.year_range(),
            input.topic(),
            input.country(),
            input.institution(),
        )

    @output
    @render.text
    def kpi_papers():
        return f"{len(filtered_papers()):,}"

    @output
    @render.text
    def kpi_years():
        data = filtered_papers()
        if data.empty:
            return "No data"
        return f"{int(data['year'].min())}-{int(data['year'].max())}"

    @output
    @render.text
    def kpi_topics():
        data = filtered_papers()
        if data.empty:
            return "0"
        return f"{data['topic_label'].nunique():,}"

    @output
    @render.text
    def kpi_institutions():
        data = filtered_papers()
        if data.empty:
            return "0%"
        return percent(data["institution_known"].mean())

    @output
    @render.text
    def kpi_countries():
        data = filtered_papers()
        if data.empty:
            return "0%"
        return percent(data["country_known"].mean())

    @output
    @render.text
    def kpi_review():
        data = filtered_papers()
        if data.empty or "topic_review_flag" not in data.columns:
            return "0 · 0%"
        flagged = int(data["topic_review_flag"].sum())
        return f"{flagged:,} · {percent(data['topic_review_flag'].mean(), 1)}"

    @output
    @render.text
    def status_papers():
        data = filtered_papers()
        known_inst = percent(data["institution_known"].mean(), 1) if not data.empty else "0%"
        return f"{len(data):,} papers · {known_inst} institution coverage"

    @output
    @render.text
    def pulse_rising():
        data = topic_momentum_table(filtered_papers())
        if data.empty:
            return "Not enough years"
        return str(data.iloc[0]["topic_label"])

    @output
    @render.text
    def pulse_rising_note():
        data = topic_momentum_table(filtered_papers())
        if data.empty:
            return "Select a wider year range."
        row = data.iloc[0]
        return f"{row['delta_pp']:+.1f} pp recent-share shift"

    @output
    @render.text
    def pulse_collab():
        data = filtered_papers()
        countries = explode_tokens(data, "countries_text", "country")
        if data.empty or countries.empty:
            return "No known countries"
        per_paper = len(countries) / max(len(data), 1)
        return f"{per_paper:.2f} countries/paper"

    @output
    @render.text
    def pulse_collab_note():
        countries = explode_tokens(filtered_papers(), "countries_text", "country")
        if countries.empty:
            return "Country metadata unavailable."
        top = countries["country"].value_counts().head(1)
        return f"Top participation: {top.index[0]} ({int(top.iloc[0]):,})"

    @output
    @render.text
    def pulse_confidence():
        data = filtered_papers()
        if data.empty:
            return "0%"
        return percent(data["affiliation_confidence"].mean(), 1)

    @output
    @render.text
    def pulse_confidence_note():
        data = filtered_papers()
        if data.empty:
            return "No filtered papers."
        openalex = data["openalex_match_method"].fillna("none").ne("none").mean() if "openalex_match_method" in data.columns else 0
        return f"OpenAlex match rate: {percent(openalex, 1)}"

    @output
    @render.text
    def pulse_source():
        data = filtered_papers()
        if data.empty or "affiliation_source" not in data.columns:
            return "None"
        source = data["affiliation_source"].fillna("none").value_counts().index[0]
        return SOURCE_LABELS.get(source, source)

    @output
    @render.text
    def pulse_source_note():
        data = filtered_papers()
        if data.empty or "affiliation_source" not in data.columns:
            return "No provenance information."
        counts = data["affiliation_source"].fillna("none").value_counts(normalize=True)
        source = counts.index[0]
        return f"{percent(float(counts.iloc[0]), 1)} of filtered papers"

    @output
    @render_widget
    def topic_growth():
        return make_topic_growth(filtered_papers(), DATA["forecast"])

    @output
    @render_widget
    def forecast_focus():
        return make_forecast_focus(filtered_papers(), DATA["forecast"])

    @output
    @render_widget
    def topic_momentum():
        return make_topic_momentum(filtered_papers())

    @output
    @render_widget
    def country_map():
        return make_country_map(filtered_papers())

    @output
    @render_widget
    def collaboration_flow():
        return make_collaboration_flow(filtered_papers())

    @output
    @render_widget
    def institution_leaderboard():
        return make_institution_leaderboard(filtered_papers())

    @output
    @render_widget
    def coverage_strip():
        return make_coverage_strip(DATA["coverage"], filtered_papers())

    @output
    @render_widget
    def affiliation_provenance():
        return make_affiliation_provenance(filtered_papers())

    @output
    @render_widget
    def topic_heatmap():
        return make_topic_heatmap(filtered_papers())

    @output
    @render_widget
    def topic_network():
        return make_topic_network(filtered_papers(), DATA["topic_edges"])

    @output
    @render_widget
    def topic_galaxy():
        return make_topic_galaxy(filtered_papers())

    @output
    @render_widget
    def research_river():
        return make_research_river(filtered_papers())

    @output
    @render_widget
    def topic_race():
        return make_topic_race(filtered_papers())

    @output
    @render_widget
    def research_bloom():
        return make_research_bloom(filtered_papers())

    @output
    @render_widget
    def institution_country_orbit():
        return make_institution_country_orbit(filtered_papers())

    @output
    @render_widget
    def metadata_weather():
        return make_metadata_weather(filtered_papers())

    @output
    @render_widget
    def paper_universe():
        return make_paper_universe(filtered_papers())

    @output
    @render_widget
    def topic_dna():
        return make_topic_dna(filtered_papers())

    @output
    @render.data_frame
    def papers_table():
        return render.DataGrid(paper_table(filtered_papers()), filters=True, selection_mode="row")


app = App(app_ui, server)
