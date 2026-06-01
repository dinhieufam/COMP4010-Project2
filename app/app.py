from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP_ROOT = Path(__file__).resolve().parent
for path in (PROJECT_ROOT, APP_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from shiny import App, reactive, render, ui
from shinywidgets import output_widget, render_widget

from charts.explorer import paper_table
from charts.geography import make_country_map
from charts.heatmap import make_topic_heatmap
from charts.impact import make_citation_impact
from charts.institutions import make_institution_leaderboard
from charts.network import make_topic_network
from charts.streamgraph import make_topic_growth
from data_loader import load_data
from filters import apply_filters


DATA = load_data()
PAPERS = DATA["papers"]
YEAR_MIN = int(PAPERS["year"].min())
YEAR_MAX = int(PAPERS["year"].max())
TOPIC_CHOICES = ["All"] + sorted(PAPERS["topic_label"].dropna().unique().tolist())
COUNTRY_CHOICES = ["All"] + sorted(
    {part.strip() for value in PAPERS["countries_text"].dropna() for part in str(value).split(",") if part.strip()}
)
INSTITUTION_CHOICES = ["All"] + sorted(
    {part.strip() for value in PAPERS["institutions_text"].dropna() for part in str(value).split(",") if part.strip()}
)


def kpi_card(title: str, output_id: str):
    return ui.div(
        ui.div(title, class_="kpi-label"),
        ui.output_text(output_id),
        class_="kpi-card",
    )


app_ui = ui.page_fluid(
    ui.include_css(APP_ROOT / "www" / "styles.css"),
    ui.div(
        ui.div(
            ui.div(
                ui.div("NeurIPS Observatory", class_="brand-mark"),
                ui.h1("AI Conference Research Observatory"),
                ui.p("Full-history NeurIPS proceedings, 1987-2025"),
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
                ui.span("Curated taxonomy"),
                ui.span("Primary + secondary topics"),
                ui.span("Local MVP"),
                class_="sidebar-meta",
            ),
            class_="sidebar",
        ),
        ui.div(
            ui.div(
                ui.div(
                    ui.div("Research dashboard", class_="eyebrow"),
                    ui.h2("NeurIPS research landscape"),
                    ui.p("Topic structure, citation signals, geography, and institutional participation."),
                    class_="page-title",
                ),
                ui.div(
                    ui.span("Updated topic taxonomy", class_="status-pill"),
                    ui.span("30,602 papers", class_="status-pill subtle"),
                    class_="status-strip",
                ),
                class_="topbar",
            ),
            ui.div(
                kpi_card("Papers", "kpi_papers"),
                kpi_card("Year Span", "kpi_years"),
                kpi_card("Topics", "kpi_topics"),
                kpi_card("Leading Topic", "kpi_topic"),
                kpi_card("Citation Coverage", "kpi_citations"),
                kpi_card("Review Flags", "kpi_review"),
                class_="kpi-grid",
            ),
            ui.div(
                ui.div(output_widget("topic_growth"), class_="panel hero-panel"),
                ui.div(output_widget("topic_heatmap"), class_="panel tall"),
                ui.div(output_widget("citation_impact"), class_="panel"),
                ui.div(output_widget("country_map"), class_="panel"),
                ui.div(
                    ui.div(
                        ui.input_radio_buttons(
                            "institution_metric",
                            "Institution metric",
                            choices={"output": "Output", "impact": "Citations"},
                            selected="output",
                            inline=True,
                        ),
                        class_="panel-control",
                    ),
                    output_widget("institution_leaderboard"),
                    class_="panel",
                ),
                ui.div(output_widget("topic_network"), class_="panel"),
                ui.div(ui.h2("Paper Explorer"), ui.output_data_frame("papers_table"), class_="panel table-panel"),
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
    def kpi_topic():
        data = filtered_papers()
        if data.empty:
            return "No data"
        return str(data["topic_label"].mode().iloc[0])

    @output
    @render.text
    def kpi_topics():
        data = filtered_papers()
        if data.empty:
            return "0"
        return f"{data['topic_label'].nunique():,}"

    @output
    @render.text
    def kpi_citations():
        data = filtered_papers()
        if data.empty:
            return "0%"
        rate = data["citation_count"].gt(0).mean()
        return f"{rate * 100:.0f}%"

    @output
    @render.text
    def kpi_review():
        data = filtered_papers()
        if data.empty or "topic_review_flag" not in data.columns:
            return "0"
        return f"{int(data['topic_review_flag'].sum()):,}"

    @output
    @render_widget
    def topic_growth():
        return make_topic_growth(filtered_papers(), DATA["forecast"])

    @output
    @render_widget
    def citation_impact():
        return make_citation_impact(filtered_papers())

    @output
    @render_widget
    def country_map():
        return make_country_map(filtered_papers())

    @output
    @render_widget
    def institution_leaderboard():
        return make_institution_leaderboard(filtered_papers(), input.institution_metric())

    @output
    @render_widget
    def topic_heatmap():
        return make_topic_heatmap(filtered_papers())

    @output
    @render_widget
    def topic_network():
        return make_topic_network(filtered_papers(), DATA["topic_edges"])

    @output
    @render.data_frame
    def papers_table():
        return render.DataGrid(paper_table(filtered_papers()), filters=True, selection_mode="row")


app = App(app_ui, server)
