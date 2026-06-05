from __future__ import annotations

from typing import Callable

import plotly.graph_objects as go
from shiny import module, ui
from shinywidgets import output_widget, render_widget


@module.ui
def chart_panel_ui(title: str, subtitle: str, *extra_classes: str) -> ui.Tag:
    return ui.div(
        ui.div(ui.h3(title), ui.p(subtitle), class_="panel-header"),
        output_widget("chart"),
        class_=" ".join(["panel", *extra_classes]),
    )


@module.server
def chart_panel_server(input, output, session, *, make_chart: Callable[[], go.Figure]) -> None:
    @output
    @render_widget
    def chart() -> go.Figure:
        return make_chart()
