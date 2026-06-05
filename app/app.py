from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go

PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP_ROOT = Path(__file__).resolve().parent
for path in (PROJECT_ROOT, APP_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from shiny import App, reactive, render, req, ui
from shinywidgets import output_widget, render_widget

from charts.collaboration import make_collaboration_flow
from charts.creative import (
    make_institution_country_treemap,
    make_research_river,
    make_topic_race,
)
from charts.explorer import make_explorer_html
from charts.forecast import make_forecast_focus
from charts.geography import make_country_map, make_country_trend
from charts.heatmap import make_topic_heatmap
from charts.institutions import make_institution_leaderboard
from charts.momentum import make_topic_momentum
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
    DATA["institution_year"]
    .loc[DATA["institution_year"]["institution"].ne("Unknown"), "institution"]
    .unique()
    .tolist()
)


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


app_ui = ui.page_fluid(
    ui.include_css(APP_ROOT / "www" / "styles.css"),
    ui.div(
        # ── Sidebar ──────────────────────────────────────────
        ui.div(
            ui.div(
                ui.div("NeurIPS Observatory", class_="brand-mark"),
                ui.h1("AI Conference Research Observatory"),
                ui.p("Minimalist analytical atlas of NeurIPS topics, geography, institutions, and forecasts."),
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
        # ── Main content ──────────────────────────────────────
        ui.div(
            ui.div(
                ui.div(
                    ui.div("Research dashboard", class_="eyebrow"),
                    ui.h2("NeurIPS research landscape"),
                    ui.p("Explore topic shifts, global participation, institutional output, and forecast signals."),
                    class_="page-title",
                ),
                ui.div(
                    ui.span(ui.output_text("status_papers"), class_="status-pill subtle"),
                    class_="status-strip",
                ),
                class_="topbar",
            ),
            ui.div(
                ui.navset_underline(
                    # ── Tab 1: Overview ──────────────────────────────
                    ui.nav_panel(
                        "Overview",
                        ui.div(
                            kpi_card("Filtered papers", "kpi_papers", "Unique proceedings papers"),
                            kpi_card("Year span", "kpi_years", "Visible range after filters"),
                            kpi_card("Topics represented", "kpi_topics", "Primary topic labels"),
                            kpi_card("Known institutions", "kpi_institutions", "Paper-level coverage"),
                            kpi_card("Known countries", "kpi_countries", "Paper-level coverage"),
                            kpi_card("Review workload", "kpi_review", "Topic audit flags"),
                            class_="kpi-grid",
                        ),
                    ),
                    # ── Tab 2: Topics ─────────────────────────────────
                    ui.nav_panel(
                        "Topics",
                        ui.div(
                            panel("Topic growth", "Stacked area by topic; dashed lines = Holt-Winters forecasts. Box-select to brush year range.", "topic_growth", "hero-panel"),
                            panel("Forecast focus", "Solid = observed, dotted = forecast, band = 95% CI.", "forecast_focus"),
                            panel("Topic momentum", "Bars show share gain/loss: recent vs. early years. Right = rising; left = fading.", "topic_momentum"),
                            panel("Topic heatmap", "Click any cell to filter by topic. Colour intensity = share of papers that year.", "topic_heatmap", "tall"),
                            panel("Topic similarity", "Colour intensity = pairwise co-occurrence weight. Click a cell to filter by topic.", "topic_network"),
                            panel("Research River", "Eras flow left-to-right into dominant research themes. Width ∝ paper share.", "research_river"),
                            panel("Topic Race", "Lines show annual rank changes. Rising = growing topics; crossing lines = leadership changes.", "topic_race"),
                            class_="dashboard-grid",
                        ),
                    ),
                    # ── Tab 3: Geography ──────────────────────────────
                    ui.nav_panel(
                        "Geography",
                        ui.div(
                            panel("Global footprint", "Click a country to filter. Animate to watch participation grow from 1987.", "country_map", "tall"),
                            panel("Top countries per year", "Annual paper-participation count for the top 10 countries. Lines show trajectories; use sidebar filters to compare subsets.", "country_trend"),
                            panel("Country-topic focus", "Colour intensity = % of each country's papers in that topic. Each row sums to 100%.", "collaboration_flow"),
                            class_="dashboard-grid",
                        ),
                    ),
                    # ── Tab 4: Institutions ───────────────────────────
                    ui.nav_panel(
                        "Institutions",
                        ui.div(
                            panel("Institution leaderboard", "Click a bar to filter by institution. Top-12 by paper participation count.", "institution_leaderboard"),
                            panel("Institution-country distribution", "Tile area = paper count. Countries are parent tiles; institutions are children.", "institution_country_treemap"),
                            class_="dashboard-grid",
                        ),
                    ),
                    # ── Tab 5: Explorer ───────────────────────────────
                    ui.nav_panel(
                        "Explorer",
                        ui.div(
                            ui.div(
                                ui.h3("Paper Explorer"),
                                ui.p("All papers matching the active sidebar filters. Search by title or author, then click any URL link to open the paper."),
                                class_="panel-header",
                            ),
                            ui.div(
                                ui.input_text(
                                    "explorer_search",
                                    "Search title / author",
                                    placeholder="Type to filter…",
                                ),
                                class_="explorer-search-row",
                            ),
                            ui.output_ui("papers_html"),
                            class_="panel table-panel",
                        ),
                    ),
                    id="main_tabs",
                ),
                class_="main-tabs-wrapper",
            ),
            class_="dashboard-main",
        ),
        class_="app-shell",
    ),
)


def server(input, output, session):
    _clicked_institution = reactive.Value(None)
    _clicked_topic = reactive.Value(None)
    _brushed_years = reactive.Value(None)

    @reactive.Effect
    @reactive.event(input.reset_filters)
    def _reset_filters():
        ui.update_slider("year_range", value=(YEAR_MIN, YEAR_MAX))
        ui.update_selectize("topic", selected="All")
        ui.update_selectize("country", selected="All")
        ui.update_selectize("institution", selected="All")
        _clicked_institution.set(None)
        _clicked_topic.set(None)
        _brushed_years.set(None)

    @reactive.Calc
    def filtered_papers():
        return apply_filters(
            PAPERS,
            input.year_range(),
            input.topic(),
            input.country(),
            input.institution(),
        )

    # ── KPI outputs ───────────────────────────────────────────

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
        return f"{int(data['year'].min())}–{int(data['year'].max())}"

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
        v = data["institution_known"].mean()
        return f"{v * 100:.0f}%"

    @output
    @render.text
    def kpi_countries():
        data = filtered_papers()
        if data.empty:
            return "0%"
        v = data["country_known"].mean()
        return f"{v * 100:.0f}%"

    @output
    @render.text
    def kpi_review():
        data = filtered_papers()
        if data.empty or "topic_review_flag" not in data.columns:
            return "0 · 0%"
        flagged = int(data["topic_review_flag"].sum())
        pct = data["topic_review_flag"].mean() * 100
        return f"{flagged:,} · {pct:.1f}%"

    @output
    @render.text
    def status_papers():
        data = filtered_papers()
        pct = f"{data['institution_known'].mean() * 100:.1f}%" if not data.empty else "0%"
        return f"{len(data):,} papers · {pct} institution coverage"

    # ── Topic charts ──────────────────────────────────────────

    @output
    @render_widget
    def topic_growth():
        fw = go.FigureWidget(make_topic_growth(filtered_papers(), DATA["forecast"]))

        def _on_select(trace, points, selector):
            xs = list(points.xs) if points.xs else []
            years = [int(x) for x in xs if x is not None]
            if len(years) >= 2:
                _brushed_years.set((min(years), max(years)))

        for trace in fw.data:
            trace.on_selection(_on_select)
        return fw

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
    def topic_heatmap():
        fw = go.FigureWidget(make_topic_heatmap(filtered_papers()))

        def _on_click(trace, points, selector):
            ys = list(points.ys) if points.ys else []
            if ys:
                _clicked_topic.set(str(ys[0]))

        for trace in fw.data:
            trace.on_click(_on_click)
        return fw

    @output
    @render_widget
    def topic_network():
        fw = go.FigureWidget(make_topic_network(filtered_papers(), DATA["topic_edges"]))

        def _on_click(trace, points, selector):
            ys = list(points.ys) if points.ys else []
            if ys:
                _clicked_topic.set(str(ys[0]))

        for trace in fw.data:
            trace.on_click(_on_click)
        return fw

    @output
    @render_widget
    def research_river():
        return make_research_river(filtered_papers())

    @output
    @render_widget
    def topic_race():
        return make_topic_race(filtered_papers())

    # ── Geography charts ──────────────────────────────────────

    @output
    @render_widget
    def country_map():
        return make_country_map(filtered_papers())

    @output
    @render_widget
    def country_trend():
        return make_country_trend(filtered_papers())

    @output
    @render_widget
    def collaboration_flow():
        return make_collaboration_flow(filtered_papers())

    # ── Institution charts ────────────────────────────────────

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
    @render_widget
    def institution_country_treemap():
        return make_institution_country_treemap(filtered_papers())

    # ── Explorer ──────────────────────────────────────────────

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
        return ui.HTML(make_explorer_html(explorer_papers()))

    # ── Cross-filter effects ──────────────────────────────────

    @reactive.Effect
    def _institution_cross_filter():
        name = _clicked_institution.get()
        if name and name in INSTITUTION_CHOICES:
            ui.update_selectize("institution", selected=name)

    @reactive.Effect
    def _topic_cross_filter():
        name = _clicked_topic.get()
        if name and name in TOPIC_CHOICES:
            ui.update_selectize("topic", selected=name)

    @reactive.Effect
    def _year_brush_apply():
        yr = _brushed_years.get()
        if yr:
            y_min = max(YEAR_MIN, yr[0])
            y_max = min(YEAR_MAX, yr[1])
            if y_min <= y_max:
                ui.update_slider("year_range", value=(y_min, y_max))


app = App(app_ui, server)
