from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QActionGroup
from PySide6.QtWidgets import QApplication, QDockWidget, QFileDialog, QInputDialog, QMainWindow, QVBoxLayout, QWidget

from csv_plot_maker._version import BUILD_DATE, __version__
from csv_plot_maker.data.column_store import ColumnStore
from csv_plot_maker.models.project import ProjectState
from csv_plot_maker.models.series import Series
from csv_plot_maker.models.serialization import config_path_for_csv, load_project, save_project
from csv_plot_maker.models.subplot import SubplotConfig
from csv_plot_maker.plotting.plot_grid_widget import PlotGridWidget
from csv_plot_maker.plotting.style_map import next_default_color
from csv_plot_maker.ui import theme
from csv_plot_maker.ui.csv_panel import CsvPanel
from csv_plot_maker.ui.grid_config_panel import GridConfigPanel
from csv_plot_maker.ui.series_panel import SeriesPanel
from csv_plot_maker.ui.style_panel import StylePanel

_AXIS_LABEL_FIELDS = {"bottom": "x_label", "left": "y_label_left", "right": "y_label_right"}


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(f"CSV Plot Maker v{__version__} ({BUILD_DATE})")

        self.column_store: ColumnStore | None = None
        self.project = ProjectState(grid_rows=1, grid_cols=1)
        self.project.build_default_grid()
        self._selected_series_id: str = ""

        self.plot_grid = PlotGridWidget()
        self.setCentralWidget(self.plot_grid)

        # Left dock: open a CSV, see its columns, drag one onto a subplot.
        self.csv_panel = CsvPanel()
        data_dock = QDockWidget("Load CSV and View datalist", self)
        data_dock.setWidget(self.csv_panel)
        self.addDockWidget(Qt.LeftDockWidgetArea, data_dock)

        # Right dock: Configure subplot -- grid dims, then the active subplot's
        # X/Y series, then (only once a series is picked) its style controls.
        self.grid_panel = GridConfigPanel()
        self.series_panel = SeriesPanel()
        self.style_panel = StylePanel()

        config_widget = QWidget()
        config_layout = QVBoxLayout(config_widget)
        config_layout.addWidget(self.grid_panel)
        config_layout.addWidget(self.series_panel, 1)
        config_layout.addWidget(self.style_panel)

        config_dock = QDockWidget("Configure subplot", self)
        config_dock.setWidget(config_widget)
        self.addDockWidget(Qt.RightDockWidgetArea, config_dock)

        self._build_menu()

        self.csv_panel.csv_loaded.connect(self._on_csv_loaded)
        self.grid_panel.grid_dims_changed.connect(self._on_grid_dims_changed)
        self.grid_panel.active_subplot_changed.connect(self._on_active_subplot_changed)
        self.grid_panel.clear_subplot_requested.connect(self._on_clear_subplot_requested)
        self.grid_panel.clear_all_requested.connect(self._on_clear_all_requested)
        self.grid_panel.link_x_toggled.connect(self._on_link_x_toggled)
        self.series_panel.x_column_changed.connect(self._on_x_column_changed)
        self.series_panel.series_selection_changed.connect(self._on_series_selection_changed)
        self.series_panel.series_delete_requested.connect(self._on_series_delete_requested)
        self.series_panel.legend_toggled.connect(self._on_legend_toggled)
        self.style_panel.style_changed.connect(self._on_style_changed)
        self.style_panel.axis_changed.connect(self._on_series_axis_changed)
        self.style_panel.remove_requested.connect(self._on_style_remove_requested)
        self.plot_grid.subplot_clicked.connect(self._on_canvas_subplot_clicked)
        self.plot_grid.column_dropped.connect(self._on_column_dropped)
        self.plot_grid.axis_label_double_clicked.connect(self._on_axis_label_double_clicked)

        self._refresh_subplot_selector()
        self._apply_theme("system")
        self.statusBar().showMessage("Ready")

    # -- menu ----------------------------------------------------------------

    def _build_menu(self) -> None:
        file_menu = self.menuBar().addMenu("File")
        save_action = file_menu.addAction("Save Layout")
        save_action.triggered.connect(self._on_save_config)
        save_as_action = file_menu.addAction("Save Layout As...")
        save_as_action.triggered.connect(self._on_save_config_as)
        load_action = file_menu.addAction("Load Layout")
        load_action.triggered.connect(self._on_load_config)
        load_as_action = file_menu.addAction("Load Layout As...")
        load_as_action.triggered.connect(self._on_load_config_as)

        settings_menu = self.menuBar().addMenu("Settings")
        theme_menu = settings_menu.addMenu("Theme")
        theme_group = QActionGroup(self)
        theme_group.setExclusive(True)
        for label, mode in (("Light mode", "light"), ("Dark mode", "dark"), ("System mode", "system")):
            action = theme_menu.addAction(label)
            action.setCheckable(True)
            action.setChecked(mode == "system")
            action.triggered.connect(lambda _checked=False, m=mode: self._apply_theme(m))
            theme_group.addAction(action)

    # -- helpers -----------------------------------------------------------

    def _active_subplot(self) -> SubplotConfig:
        return self.project.get_active_subplot()

    def _active_view(self):
        subplot = self._active_subplot()
        return self.plot_grid.get_view(subplot.row, subplot.col)

    def _subplot_at(self, row: int, col: int) -> SubplotConfig | None:
        return next((sp for sp in self.project.subplots if sp.row == row and sp.col == col), None)

    def _set_active_subplot(self, subplot_id: str) -> None:
        self.project.active_subplot_id = subplot_id
        self.grid_panel.set_active(subplot_id)
        self._refresh_active_subplot_controls()

    def _refresh_subplot_selector(self) -> None:
        options = [(sp.id, f"({sp.row}, {sp.col})") for sp in self.project.subplots]
        self.grid_panel.set_subplot_options(options)
        if self.project.active_subplot_id:
            self.grid_panel.set_active(self.project.active_subplot_id)
        self.grid_panel.sync_grid_spins(self.project.grid_rows, self.project.grid_cols)
        self.grid_panel.set_link_x_axes(self.project.link_x_axes)
        self.plot_grid.set_link_x_axes(self.project.link_x_axes)

    def _refresh_series_list(self) -> None:
        subplot = self._active_subplot()
        items = [(s.id, f"{s.y_column}  [{s.axis}]") for s in subplot.series]
        self.series_panel.refresh_series_list(items)
        # QListWidget selection is cleared on refresh; keep the style section in sync.
        self._selected_series_id = ""
        self.style_panel.set_series(None)

    def _refresh_active_subplot_controls(self) -> None:
        subplot = self._active_subplot()
        self.series_panel.set_x_column(subplot.x_column)
        self.series_panel.set_show_legend(subplot.show_legend)
        self._refresh_series_list()

    def _replot_subplot(self, subplot: SubplotConfig) -> None:
        if self.column_store is None or not subplot.x_column:
            return
        view = self.plot_grid.get_view(subplot.row, subplot.col)
        x_data = self.column_store.get(subplot.x_column)
        for series in subplot.series:
            y_data = self.column_store.get(series.y_column)
            view.set_series_data(series, x_data, y_data)
        view.set_labels(
            subplot.x_label or subplot.x_column,
            subplot.y_label_left,
            subplot.y_label_right,
        )
        # An empty subplot has nothing for a legend to label, so hide it
        # regardless of the show_legend toggle -- otherwise a bare legend
        # box with no entries sits in the corner of a blank plot.
        view.set_legend_visible(subplot.show_legend and bool(subplot.series))

    def _replot_all_subplots(self) -> None:
        for subplot in self.project.subplots:
            self._replot_subplot(subplot)

    def _default_x_columns(self, names: list[str]) -> None:
        if not names:
            return
        # Prefer the CSV's own "timestamp" column as the default X axis; fall
        # back to the always-present synthetic "Sequential" column when this
        # CSV has none (missing, or not numeric/temporal enough to parse).
        default = "timestamp" if "timestamp" in names else "Sequential"
        for subplot in self.project.subplots:
            if subplot.x_column not in names:
                subplot.x_column = default

    def _remove_series(self, series_id: str) -> None:
        subplot = self._active_subplot()
        subplot.remove_series(series_id)
        view = self._active_view()
        view.remove_series(series_id)
        if not subplot.series:
            view.set_legend_visible(False)
        self._refresh_series_list()

    def _clear_subplot(self, subplot: SubplotConfig) -> None:
        subplot.series = []
        subplot.x_label = ""
        subplot.y_label_left = ""
        subplot.y_label_right = ""
        subplot.show_legend = True
        view = self.plot_grid.get_view(subplot.row, subplot.col)
        view.clear()
        view.set_labels(subplot.x_column or "", "", "")
        view.set_legend_visible(False)

    def _apply_theme(self, mode: str) -> None:
        app = QApplication.instance()
        background, foreground = theme.apply_app_theme(app, mode)
        self.plot_grid.set_theme_colors(background, foreground)

    # -- signal handlers -----------------------------------------------------

    def _on_csv_loaded(self, store: ColumnStore) -> None:
        self.column_store = store

        # Always start from a clean single-subplot grid before applying this
        # CSV's own state -- otherwise subplots/series left over from a
        # previously opened (and structurally different) CSV would stick
        # around referencing column names that don't exist in this file.
        self.project = ProjectState(grid_rows=1, grid_cols=1)
        self.project.build_default_grid()

        config_path = config_path_for_csv(store.source_path)
        loaded_saved_layout = False
        if config_path.exists():
            try:
                self.project = load_project(str(config_path))
                loaded_saved_layout = True
            except Exception as exc:
                self.statusBar().showMessage(f"Failed to load saved layout {config_path.name}: {exc}")

        self.project.csv_path = store.source_path
        self.plot_grid.rebuild(self.project.grid_rows, self.project.grid_cols)

        names = store.numeric_column_names()
        self.series_panel.set_columns(names)
        self._default_x_columns(names)

        self._refresh_subplot_selector()
        self._refresh_active_subplot_controls()
        self._replot_all_subplots()

        message = f"{store.row_count:,} rows loaded from {store.source_path} in {store.load_time_ms:.0f} ms"
        if loaded_saved_layout:
            message += f" -- restored layout from {config_path.name}"
        self.statusBar().showMessage(message)

    def _on_grid_dims_changed(self, rows: int, cols: int) -> None:
        self.project.resize_grid(rows, cols)
        self.plot_grid.rebuild(rows, cols)

        if self.column_store is not None:
            self._default_x_columns(self.column_store.numeric_column_names())

        self._refresh_subplot_selector()
        self._refresh_active_subplot_controls()
        self._replot_all_subplots()

    def _on_active_subplot_changed(self, subplot_id: str) -> None:
        self.project.active_subplot_id = subplot_id
        self._refresh_active_subplot_controls()

    def _on_clear_subplot_requested(self) -> None:
        self._clear_subplot(self._active_subplot())
        self._refresh_active_subplot_controls()
        self.statusBar().showMessage("Cleared the active subplot")

    def _on_clear_all_requested(self) -> None:
        for subplot in self.project.subplots:
            self._clear_subplot(subplot)
        self._refresh_active_subplot_controls()
        self.statusBar().showMessage("Cleared all subplots")

    def _on_link_x_toggled(self, enabled: bool) -> None:
        self.project.link_x_axes = enabled
        self.plot_grid.set_link_x_axes(enabled)

    def _on_canvas_subplot_clicked(self, row: int, col: int) -> None:
        subplot = self._subplot_at(row, col)
        if subplot is not None:
            self._set_active_subplot(subplot.id)

    def _on_x_column_changed(self, name: str) -> None:
        subplot = self._active_subplot()
        subplot.x_column = name
        self._replot_subplot(subplot)

    def _on_column_dropped(self, row: int, col: int, column_name: str) -> None:
        if self.column_store is None:
            self.statusBar().showMessage("Still loading the CSV -- please wait before adding series")
            return
        if column_name not in self.column_store.numeric_column_names():
            return
        subplot = self._subplot_at(row, col)
        if subplot is None:
            return

        self._set_active_subplot(subplot.id)
        color = next_default_color(len(subplot.series))
        series = Series(y_column=column_name, color=color)
        subplot.add_series(series)
        self._refresh_active_subplot_controls()
        self._replot_subplot(subplot)
        self.series_panel.select_series_id(series.id)

    def _on_series_selection_changed(self, series_id: str) -> None:
        self._selected_series_id = series_id
        subplot = self._active_subplot()
        series = subplot.get_series(series_id) if series_id else None
        self.style_panel.set_series(series, len(subplot.series))

    def _on_series_delete_requested(self, series_id: str) -> None:
        self._remove_series(series_id)

    def _on_legend_toggled(self, visible: bool) -> None:
        subplot = self._active_subplot()
        subplot.show_legend = visible
        self._active_view().set_legend_visible(visible and bool(subplot.series))

    def _on_axis_label_double_clicked(self, row: int, col: int, axis_name: str) -> None:
        subplot = self._subplot_at(row, col)
        if subplot is None or axis_name not in _AXIS_LABEL_FIELDS:
            return
        field = _AXIS_LABEL_FIELDS[axis_name]
        current = getattr(subplot, field) or (subplot.x_column if axis_name == "bottom" else "")
        text, ok = QInputDialog.getText(self, "Edit axis label", "Label:", text=current)
        if ok:
            setattr(subplot, field, text)
            self._replot_subplot(subplot)

    def _on_series_axis_changed(self, axis: str) -> None:
        if not self._selected_series_id or self.column_store is None:
            return
        subplot = self._active_subplot()
        series = subplot.get_series(self._selected_series_id)
        if series is None or series.axis == axis:
            return
        series.axis = axis
        x_data = self.column_store.get(subplot.x_column)
        y_data = self.column_store.get(series.y_column)
        self._active_view().set_series_data(series, x_data, y_data)
        self._refresh_series_list()
        self.series_panel.select_series_id(series.id)

    def _on_style_changed(self) -> None:
        if not self._selected_series_id:
            return
        subplot = self._active_subplot()
        series = subplot.get_series(self._selected_series_id)
        if series is None:
            return
        series.color = self.style_panel.current_color()
        series.line_style = self.style_panel.current_line_style()
        series.marker = self.style_panel.current_marker()
        series.width = self.style_panel.current_width()
        self._active_view().update_series_style(series)

    def _on_style_remove_requested(self) -> None:
        if self._selected_series_id:
            self._remove_series(self._selected_series_id)

    def _on_save_config(self) -> None:
        if not self.project.csv_path:
            self.statusBar().showMessage("Load a CSV first")
            return
        config_path = config_path_for_csv(self.project.csv_path)
        save_project(self.project, str(config_path))
        self.statusBar().showMessage(f"Saved layout to {config_path.name}")

    def _on_save_config_as(self) -> None:
        if not self.project.csv_path:
            self.statusBar().showMessage("Load a CSV first")
            return
        default_path = str(config_path_for_csv(self.project.csv_path))
        path, _ = QFileDialog.getSaveFileName(self, "Save Layout As", default_path, "JSON Files (*.json)")
        if not path:
            return
        save_project(self.project, path)
        self.statusBar().showMessage(f"Saved layout to {Path(path).name}")

    def _on_load_config(self) -> None:
        if not self.project.csv_path:
            self.statusBar().showMessage("Load a CSV first")
            return
        config_path = config_path_for_csv(self.project.csv_path)
        if not config_path.exists():
            self.statusBar().showMessage(f"No saved layout found at {config_path.name}")
            return
        self._load_layout_from_path(str(config_path))

    def _on_load_config_as(self) -> None:
        if not self.project.csv_path:
            self.statusBar().showMessage("Load a CSV first")
            return
        path, _ = QFileDialog.getOpenFileName(self, "Load Layout As", "", "JSON Files (*.json)")
        if not path:
            return
        self._load_layout_from_path(path)

    def _load_layout_from_path(self, path: str) -> None:
        try:
            project = load_project(path)
        except Exception as exc:
            self.statusBar().showMessage(f"Failed to load layout: {exc}")
            return

        # A layout's JSON is portable -- it names columns by string, not by
        # position -- so it can be reused against any CSV. But a column it
        # references may not exist in *this* CSV (different file, renamed
        # column, etc.): drop only those series/mismatched X columns instead
        # of failing the whole load, and always point the loaded project at
        # the CSV that's actually open rather than whatever path it was
        # originally saved against.
        dropped = 0
        if self.column_store is not None:
            valid_names = self.column_store.numeric_column_names()
            valid_set = set(valid_names)
            for subplot in project.subplots:
                kept = [s for s in subplot.series if s.y_column in valid_set]
                dropped += len(subplot.series) - len(kept)
                subplot.series = kept
                if subplot.x_column not in valid_set and valid_names:
                    subplot.x_column = valid_names[0]
            project.csv_path = self.column_store.source_path

        self.project = project
        self.plot_grid.rebuild(self.project.grid_rows, self.project.grid_cols)
        self._refresh_subplot_selector()
        self._refresh_active_subplot_controls()
        self._replot_all_subplots()

        message = f"Loaded layout from {Path(path).name}"
        if dropped:
            message += f" ({dropped} series dropped: column not found in the current CSV)"
        self.statusBar().showMessage(message)
