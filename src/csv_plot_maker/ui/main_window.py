from __future__ import annotations

import re
from contextlib import contextmanager
from pathlib import Path

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtGui import QActionGroup
from PySide6.QtWidgets import (
    QApplication,
    QDockWidget,
    QFileDialog,
    QInputDialog,
    QMainWindow,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)

from csv_plot_maker._version import BUILD_DATE, __version__
from csv_plot_maker.models.data_source import DataSource, SourceRef
from csv_plot_maker.models.project import ProjectState
from csv_plot_maker.models.series import Series
from csv_plot_maker.models.serialization import (
    LayoutFile,
    config_path_for_csv,
    default_tab_name,
    duplicate_tab_name,
    load_layout_file,
    save_project,
    save_workspace,
)
from csv_plot_maker.models.subplot import SubplotConfig
from csv_plot_maker.plotting.deferred_delete import defer_delete
from csv_plot_maker.plotting.plot_grid_widget import PlotGridWidget
from csv_plot_maker.plotting.style_map import next_default_color
from csv_plot_maker.ui import theme
from csv_plot_maker.ui.csv_panel import CsvPanel
from csv_plot_maker.ui.grid_config_panel import GridConfigPanel
from csv_plot_maker.ui.layout_tab_widget import LayoutTabWidget
from csv_plot_maker.ui.license_dialog import LicenseDialog
from csv_plot_maker.ui.series_panel import SeriesPanel
from csv_plot_maker.ui.style_panel import StylePanel
from csv_plot_maker.ui.version_history_dialog import VersionHistoryDialog

_AXIS_LABEL_FIELDS = {"bottom": "x_label", "left": "y_label_left", "right": "y_label_right"}
# Characters Windows doesn't allow in a file name (Save Tab As's default name).
_FILENAME_UNSAFE = re.compile(r'[<>:"/\\|?*]')


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(f"CSV Plot Maker v{__version__} (build date : {BUILD_DATE})")

        # Every open CSV, keyed by a per-load-session id (not path) -- a
        # column/series is always addressed as (source_id, column_name), so
        # the same column name existing in two different files never
        # collides (see DataSource).
        self.data_sources: dict[str, DataSource] = {}
        self._selected_series_id: str = ""
        # The first CSV opened this session: Save Layout / Load Layout use
        # the .json beside it, and no layout can be loaded without it.
        self._layout_csv_path: str | None = None
        # App-wide, not per tab: every tab's legends use the same text size.
        self._legend_font_size = 9
        self._theme_colors: tuple | None = None

        # Central area: one tab per layout. Each tab is a PlotGridWidget with
        # its own ProjectState (self._projects); self.plot_grid / self.project
        # are whichever tab is showing, or the one _tab_context() points at.
        # The open CSVs (self.data_sources) are shared by every tab.
        self._projects: dict[PlotGridWidget, ProjectState] = {}
        self._context_grid: PlotGridWidget | None = None
        self.layout_tabs = LayoutTabWidget()
        self.setCentralWidget(self.layout_tabs)
        self._add_tab(self._new_project())

        # Left dock: open one or more CSVs, see their columns, drag one onto a subplot.
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
        # Reserve the style section's width up front, even while it is hidden,
        # so the first series selection doesn't widen the dock to fit it.
        margins = config_layout.contentsMargins()
        config_widget.setMinimumWidth(
            self.style_panel.minimumSizeHint().width() + margins.left() + margins.right()
        )

        config_dock = QDockWidget("Configure subplot", self)
        config_dock.setWidget(config_widget)
        self.addDockWidget(Qt.RightDockWidgetArea, config_dock)
        self._config_dock = config_dock

        self._build_menu()

        self.csv_panel.csv_loaded.connect(self._on_csv_loaded)
        self.csv_panel.csv_closed.connect(self._on_csv_closed)
        self.csv_panel.all_files_closed.connect(self._on_all_files_closed)
        self.csv_panel.source_renamed.connect(self._on_source_renamed)
        self.grid_panel.grid_dims_changed.connect(self._on_grid_dims_changed)
        self.grid_panel.active_subplot_changed.connect(self._on_active_subplot_changed)
        self.grid_panel.clear_subplot_requested.connect(self._on_clear_subplot_requested)
        self.grid_panel.clear_all_requested.connect(self._on_clear_all_requested)
        self.series_panel.series_selection_changed.connect(self._on_series_selection_changed)
        self.series_panel.series_delete_requested.connect(self._on_series_delete_requested)
        self.series_panel.legend_toggled.connect(self._on_legend_toggled)
        self.series_panel.link_x_toggled.connect(self._on_subplot_link_x_toggled)
        self.style_panel.style_changed.connect(self._on_style_changed)
        self.style_panel.axis_changed.connect(self._on_series_axis_changed)
        self.style_panel.transform_changed.connect(self._on_series_transform_changed)
        self.style_panel.x_column_changed.connect(self._on_series_x_column_changed)
        self.style_panel.x_offset_changed.connect(self._on_series_x_offset_changed)
        self.style_panel.zero_at_start_requested.connect(self._on_series_zero_at_start_requested)
        self.style_panel.apply_x_to_matching_requested.connect(self._on_apply_x_to_matching_series_requested)
        self.style_panel.remove_requested.connect(self._on_style_remove_requested)
        self.layout_tabs.currentChanged.connect(self._on_current_tab_changed)
        self.layout_tabs.add_requested.connect(self._on_add_tab_requested)
        self.layout_tabs.duplicate_requested.connect(self._on_duplicate_tab_requested)
        self.layout_tabs.close_requested.connect(self._on_close_tab_requested)
        self.layout_tabs.rename_requested.connect(self._on_rename_tab_requested)

        self._refresh_subplot_selector()
        self._apply_theme("system")
        self.statusBar().showMessage("Ready")

    # -- layout tabs ---------------------------------------------------------

    @property
    def plot_grid(self) -> PlotGridWidget:
        if self._context_grid is not None:
            return self._context_grid
        return self.layout_tabs.currentWidget()

    @property
    def project(self) -> ProjectState:
        return self._projects[self.plot_grid]

    @project.setter
    def project(self, project: ProjectState) -> None:
        self._projects[self.plot_grid] = project

    def _grids(self) -> list[PlotGridWidget]:
        """Every tab's grid, in tab order."""
        return self.layout_tabs.pages()

    def _is_showing_context_tab(self) -> bool:
        return self.plot_grid is self.layout_tabs.currentWidget()

    @contextmanager
    def _tab_context(self, grid: PlotGridWidget):
        """Point self.plot_grid / self.project at `grid`'s tab (shown or not)
        for the duration, so the per-tab helpers can work on any tab. The
        side panels only ever show the current tab, so code inside must not
        refresh them unless _is_showing_context_tab()."""
        previous = self._context_grid
        self._context_grid = grid
        try:
            yield
        finally:
            self._context_grid = previous

    def _new_project(self, name: str | None = None) -> ProjectState:
        project = ProjectState(grid_rows=1, grid_cols=1, legend_font_size=self._legend_font_size)
        project.build_default_grid()
        project.name = name if name is not None else default_tab_name(self.layout_tabs.tab_names())
        return project

    def _unique_tab_name(self, name: str, ignore: PlotGridWidget | None = None) -> str:
        others = [self._projects[g].name for g in self._grids() if g is not ignore and g in self._projects]
        return name if name not in others else duplicate_tab_name(name, others)

    def _new_grid(self) -> PlotGridWidget:
        grid = PlotGridWidget()
        if self._theme_colors is not None:
            grid.set_theme_colors(*self._theme_colors)
        grid.set_legend_font_size(self._legend_font_size)
        grid.subplot_clicked.connect(self._on_canvas_subplot_clicked)
        grid.column_dropped.connect(self._on_column_dropped)
        grid.axis_label_double_clicked.connect(self._on_axis_label_double_clicked)
        return grid

    def _add_tab(self, project: ProjectState, index: int = -1) -> PlotGridWidget:
        """Add a tab holding `project` (grid built, nothing plotted yet --
        see _show_project_in_tab) and switch to it."""
        project.legend_font_size = self._legend_font_size
        grid = self._new_grid()
        # Registered before insertTab: inserting can emit currentChanged.
        self._projects[grid] = project
        grid.rebuild(project.grid_rows, project.grid_cols)
        index = self.layout_tabs.insertTab(index, grid, project.name)
        self.layout_tabs.setCurrentIndex(index)
        return grid

    def _remove_tab(self, grid: PlotGridWidget) -> None:
        index = self.layout_tabs.indexOf(grid)
        if index < 0:
            return
        self.layout_tabs.removeTab(index)
        self._projects.pop(grid, None)
        # Let Qt delete the grid (and its subplots) later, not Python right
        # now -- see deferred_delete.py.
        defer_delete(grid)

    def _reset_tabs(self) -> None:
        """Back to the start-up state: one empty 1x1 layout tab."""
        old_grids = self._grids()
        self._add_tab(self._new_project(default_tab_name([])))
        for grid in old_grids:
            self._remove_tab(grid)

    def _rename_tab(self, grid: PlotGridWidget, name: str) -> None:
        self._projects[grid].name = name
        self.layout_tabs.setTabText(self.layout_tabs.indexOf(grid), name)

    def _show_project_in_tab(self, grid: PlotGridWidget, project: ProjectState, restore_saved_ranges: bool) -> int:
        """Make `project` (freshly loaded or copied) the contents of `grid`'s
        tab: map it onto the open files, rebuild and plot it. Doesn't touch
        the side panels. Returns how many series were dropped as no longer
        valid."""
        project.legend_font_size = self._legend_font_size
        self._projects[grid] = project
        self._rename_tab(grid, project.name)
        with self._tab_context(grid):
            # A layout is a reusable template -- its subplot grid and per-file
            # series get remapped by position onto whichever files are
            # currently open (see ProjectState.reconcile_data_sources), which
            # is exactly what lets the same layout be applied to a different
            # CSV than it was originally saved against.
            dropped = self._reconcile_project_data_sources() + self._prune_invalid_references()
            self.plot_grid.rebuild(project.grid_rows, project.grid_cols)
            self._plot_tab(restore_saved_ranges)
        return dropped

    def _plot_tab(self, restore_saved_ranges: bool) -> None:
        """Replot every subplot of the (context) tab, auto-range, and
        optionally restore its saved Y ranges.

        If the tab has a linked subplot group, _sync_linked_views() applies
        that membership and broadcasts the reference subplot's still-empty
        default (0, 1) X range to the rest of the group -- which disables
        their autoRange before _replot_all_subplots() has added any real data
        to fit. Auto-ranging now that the data actually exists (same as
        clicking each subplot's "A" button) re-syncs the link using the
        now-correctly-fitted reference range.
        """
        self.plot_grid.set_legend_font_size(self._legend_font_size)
        self._sync_linked_views()
        self._replot_all_subplots()
        self._autorange_all_views()
        if restore_saved_ranges:
            self._restore_saved_y_ranges()

    def _on_current_tab_changed(self, _index: int) -> None:
        if self.layout_tabs.currentWidget() not in self._projects:
            return  # mid-add/remove
        if not hasattr(self, "series_panel"):
            return  # still in __init__
        self._refresh_selector_and_controls()
        self.plot_grid.schedule_axis_width_sync()

    def _on_add_tab_requested(self) -> None:
        self._add_tab(self._new_project())

    def _on_duplicate_tab_requested(self, index: int) -> None:
        grid = self.layout_tabs.widget(index)
        if grid not in self._projects:
            return
        with self._tab_context(grid):
            # Copy the Y ranges as they are on screen, not as last saved.
            self._capture_current_y_ranges()
        source = self._projects[grid]
        clone = source.clone_with_new_ids()
        clone.name = duplicate_tab_name(source.name, self.layout_tabs.tab_names())
        new_grid = self._add_tab(clone, index + 1)
        self._show_project_in_tab(new_grid, clone, restore_saved_ranges=True)
        self._refresh_selector_and_controls()

    def _on_close_tab_requested(self, index: int) -> None:
        grid = self.layout_tabs.widget(index)
        if grid not in self._projects or self.layout_tabs.count() <= 1:
            return
        project = self._projects[grid]
        if project.has_series():
            answer = QMessageBox.question(
                self, "Close tab", f"Close the tab '{project.name}'? Its graphs will be removed."
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
        self._remove_tab(grid)

    def _on_rename_tab_requested(self, index: int, name: str) -> None:
        grid = self.layout_tabs.widget(index)
        if grid in self._projects:
            self._rename_tab(grid, name)

    # -- menu ----------------------------------------------------------------

    def _build_menu(self) -> None:
        file_menu = self.menuBar().addMenu("File")
        # "Layout" = every tab at once; "Tab" = just the current tab.
        for entry in (
            ("Save Layout", self._on_save_config),
            ("Save Layout As...", self._on_save_config_as),
            ("Load Layout", self._on_load_config),
            ("Load Layout As...", self._on_load_config_as),
            None,
            ("Save Tab As...", self._on_save_tab_as),
            ("Load Tab As...", self._on_load_tab_as),
            ("Load Tab As New...", self._on_load_tab_as_new),
        ):
            if entry is None:
                file_menu.addSeparator()
                continue
            text, slot = entry
            file_menu.addAction(text).triggered.connect(slot)

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

        legend_font_menu = settings_menu.addMenu("Legend Font Size")
        legend_font_group = QActionGroup(self)
        legend_font_group.setExclusive(True)
        self._legend_font_actions: dict[int, object] = {}
        for label, size_pt in (("Tiny", 5), ("Small", 7), ("Medium", 9), ("Large", 11)):
            action = legend_font_menu.addAction(label)
            action.setCheckable(True)
            action.setChecked(size_pt == self._legend_font_size)
            action.triggered.connect(lambda _checked=False, p=size_pt: self._on_legend_font_size_changed(p))
            legend_font_group.addAction(action)
            self._legend_font_actions[size_pt] = action

        info_menu = self.menuBar().addMenu("Info")
        license_action = info_menu.addAction("License Info")
        license_action.triggered.connect(self._on_show_license_info)
        version_history_action = info_menu.addAction("Version History")
        version_history_action.triggered.connect(self._on_show_version_history)

    def _on_show_license_info(self) -> None:
        LicenseDialog(self).exec()

    def _on_show_version_history(self) -> None:
        VersionHistoryDialog(self).exec()

    def _on_legend_font_size_changed(self, size_pt: int) -> None:
        self._set_legend_font_size(size_pt)

    def _set_legend_font_size(self, size_pt: int) -> None:
        """The legend text size is app-wide: applied to every tab."""
        self._legend_font_size = size_pt
        for grid in self._grids():
            self._projects[grid].legend_font_size = size_pt
            grid.set_legend_font_size(size_pt)
        self._sync_legend_font_menu()

    def _sync_legend_font_menu(self) -> None:
        action = self._legend_font_actions.get(self._legend_font_size)
        if action is not None:
            action.setChecked(True)

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

    def _selected_series(self) -> Series | None:
        if not self._selected_series_id:
            return None
        return self._active_subplot().get_series(self._selected_series_id)

    def _source_label(self, source_id: str) -> str:
        source = self.data_sources.get(source_id)
        return source.label if source is not None else "?"

    def _legend_prefix_for(self, subplot: SubplotConfig, series: Series) -> str:
        """A "label: " prefix for this series' legend/list entry, but only
        when the subplot actually mixes series from more than one source --
        the common single-file case stays exactly as before (no prefix).
        """
        if len({s.source_id for s in subplot.series}) <= 1:
            return ""
        return f"{self._source_label(series.source_id)}: "

    def _source_column_options(self, source_id: str) -> list[str]:
        """Every numeric column of one specific, already-loaded source --
        used to populate the Style panel's X combo for whichever series is
        selected, scoped to just that series' own file (its Y data's
        source_id) since X must always come from the same file as Y (see
        Series.x_column). Empty while that source hasn't finished loading.
        """
        source = self.data_sources.get(source_id)
        if source is None or source.store is None:
            return []
        return source.store.numeric_column_names()

    def _default_x_column_for_source(self, source: DataSource) -> str | None:
        """The column a subplot should default to when it starts using
        `source` -- its timestamp column if it has one, else the synthetic
        row-index fallback every file always has. None if `source` hasn't
        finished loading (nothing to default to yet).
        """
        if source.store is None:
            return None
        names = source.store.numeric_column_names()
        if not names:
            return None
        return "timestamp" if "timestamp" in names else "Sequential"

    def _series_ready(self, series: Series) -> bool:
        """Checked per series (not per subplot) so one file still loading
        only leaves that one series unplotted, not the whole subplot --
        other series in it from an already-loaded file still render
        normally. See Series.is_ready.
        """
        return series.is_ready(self.data_sources.get(series.source_id))

    def _refresh_subplot_selector(self) -> None:
        options = [(sp.id, f"({sp.row}, {sp.col})") for sp in self.project.subplots]
        self.grid_panel.set_subplot_options(options)
        if self.project.active_subplot_id:
            self.grid_panel.set_active(self.project.active_subplot_id)
        self.grid_panel.sync_grid_spins(self.project.grid_rows, self.project.grid_cols)
        self.plot_grid.set_legend_font_size(self._legend_font_size)
        self._sync_legend_font_menu()
        self._sync_linked_views()

    def _sync_linked_views(self) -> None:
        linked = {(sp.row, sp.col) for sp in self.project.subplots if sp.link_x_axis}
        self.plot_grid.set_linked_views(linked)

    def _refresh_selector_and_controls(self) -> None:
        self._refresh_subplot_selector()
        self._refresh_active_subplot_controls()

    def _refresh_series_list(self) -> None:
        subplot = self._active_subplot()
        # With only one CSV open there's nothing to tell apart, so the color
        # tint is left off entirely -- matches DraggableColumnList's own
        # _sync_group_chrome, which hides the equivalent chrome on the left.
        show_colors = len(self.data_sources) > 1
        items = []
        for s in subplot.series:
            source = self.data_sources.get(s.source_id)
            prefix = self._legend_prefix_for(subplot, s)
            text = f"{prefix}{s.y_column}  [{s.axis}]"
            color = source.color if (source and show_colors) else ""
            items.append((s.id, s.source_id, s.y_column, text, color))
        self.series_panel.refresh_series_list(items)
        # QListWidget selection is cleared on refresh; keep the style section in sync.
        self._selected_series_id = ""
        self._set_style_series(None)

    def _refresh_active_subplot_controls(self) -> None:
        subplot = self._active_subplot()
        self.series_panel.set_show_legend(subplot.show_legend)
        self.series_panel.set_link_x_axis(subplot.link_x_axis)
        self._refresh_series_list()

    def _series_x_data(self, series: Series) -> np.ndarray:
        return series.x_data(self.data_sources[series.source_id])

    def _series_y_data(self, series: Series) -> np.ndarray:
        return series.y_data(self.data_sources[series.source_id])

    def _push_series_data(self, view, subplot: SubplotConfig, series: Series) -> None:
        """Recompute `series`' plotted data from its source and resend it to
        `view`. Assumes `series` is already ready (see _series_ready) --
        callers that iterate all series in a subplot (like _replot_subplot)
        still need to check that themselves first.
        """
        x_data = self._series_x_data(series)
        y_data = self._series_y_data(series)
        view.set_series_data(series, x_data, y_data, self._legend_prefix_for(subplot, series))

    def _sync_x_axis_titles(self) -> None:
        for subplot in self.project.subplots:
            view = self.plot_grid.get_view(subplot.row, subplot.col)
            view.set_bottom_label(self.project.effective_x_label(subplot))

    def _replot_subplot(self, subplot: SubplotConfig) -> None:
        view = self.plot_grid.get_view(subplot.row, subplot.col)
        for series in subplot.series:
            if not self._series_ready(series):
                # Its own file isn't open/loaded yet -- leave it undrawn for
                # now rather than the whole subplot; it appears the moment
                # that file's load finishes and this subplot is replotted
                # again (see _on_csv_loaded).
                view.remove_series(series.id)
                continue
            self._push_series_data(view, subplot, series)
        view.set_labels(
            self.project.effective_x_label(subplot),
            subplot.y_label_left,
            subplot.y_label_right,
        )
        # Whether every OTHER subplot's own bottom title should currently be
        # shown or blanked also depends on this subplot's X column/offset
        # (see ProjectState.has_shared_x_axis), so a change here can flip
        # their titles too, not just this one's.
        self._sync_x_axis_titles()
        # An empty subplot has nothing for a legend to label, so hide it
        # regardless of the show_legend toggle -- otherwise a bare legend
        # box with no entries sits in the corner of a blank plot.
        view.set_legend_visible(subplot.show_legend and bool(subplot.series))
        # Adding/clearing a Y-axis title changes how much width that axis
        # needs but doesn't touch the Y range, so it wouldn't otherwise
        # trigger the left-axis width re-sync -- leaving a newly-typed title
        # squeezed into whatever (too-narrow) width was pinned before it
        # existed, overlapping the tick numbers.
        self.plot_grid.schedule_axis_width_sync()

    def _replot_all_subplots(self) -> None:
        for subplot in self.project.subplots:
            self._replot_subplot(subplot)

    def _prune_invalid_references(self) -> int:
        """See ProjectState.prune_invalid_series. A reference to a source
        that hasn't finished loading yet (or was never resolved to any open
        file at all) is left alone by that method -- it either resolves once
        that load finishes, or gets cleaned up via _on_csv_closed if that
        load ultimately fails.
        """
        return self.project.prune_invalid_series(self.data_sources)

    def _reconcile_project_data_sources(self) -> int:
        """See ProjectState.reconcile_data_sources. Returns how many series
        it dropped because the layout referenced more files than are
        currently open.
        """
        return self.project.reconcile_data_sources(self.data_sources)

    def _remove_series_from(self, subplot: SubplotConfig, series_id: str) -> None:
        subplot.remove_series(series_id)
        view = self.plot_grid.get_view(subplot.row, subplot.col)
        view.remove_series(series_id)
        if not subplot.series:
            view.set_legend_visible(False)
        self.plot_grid.schedule_axis_width_sync()
        if subplot.id == self.project.active_subplot_id and self._is_showing_context_tab():
            self._refresh_series_list()

    def _remove_series(self, series_id: str) -> None:
        self._remove_series_from(self._active_subplot(), series_id)

    def _clear_subplot(self, subplot: SubplotConfig) -> None:
        subplot.series = []
        subplot.x_label = ""
        subplot.y_label_left = ""
        subplot.y_label_right = ""
        subplot.show_legend = True
        view = self.plot_grid.get_view(subplot.row, subplot.col)
        view.clear()
        view.set_labels(self.project.effective_x_label(subplot), "", "")
        view.set_legend_visible(False)

    def _apply_theme(self, mode: str) -> None:
        app = QApplication.instance()
        background, foreground = theme.apply_app_theme(app, mode)
        self._theme_colors = (background, foreground)
        for grid in self._grids():
            grid.set_theme_colors(background, foreground)

    # -- signal handlers -----------------------------------------------------

    def _on_csv_loaded(self, source: DataSource) -> None:
        is_first_source = not self.data_sources
        self.data_sources[source.id] = source

        loaded_saved_layout = False
        dropped = 0
        config_path = None
        if is_first_source:
            # The very first file opened in this session starts from its own
            # saved layout (every tab in it), or else from one clean
            # single-subplot tab -- subsequent files add alongside whatever's
            # already plotted instead of resetting it.
            self._layout_csv_path = source.path
            config_path = config_path_for_csv(source.path)
            layout = None
            if config_path.exists():
                try:
                    layout = load_layout_file(str(config_path))
                except Exception as exc:
                    self.statusBar().showMessage(f"Failed to load saved layout {config_path.name}: {exc}")
            if layout is not None:
                dropped = self._replace_all_tabs(layout)
                loaded_saved_layout = True
            else:
                self._reset_tabs()
                with self._tab_context(self.plot_grid):
                    self._plot_tab(restore_saved_ranges=False)
        else:
            for grid in self._grids():
                with self._tab_context(grid):
                    dropped += self._prune_invalid_references()
                    self._plot_tab(restore_saved_ranges=False)
        self._refresh_selector_and_controls()

        store = source.store
        data_mb = store.total_nbytes() / (1024 * 1024)
        message = (
            f"{store.row_count:,} rows loaded from {source.path} "
            f"in {store.load_time_ms:.0f} ms ({data_mb:,.0f} MB in memory)"
        )
        if is_first_source and loaded_saved_layout:
            message += f" -- restored layout from {config_path.name}"
        if dropped:
            message += f" ({dropped} series dropped: no longer valid)"
        self.statusBar().showMessage(message)

    def _on_csv_closed(self, source_id: str) -> None:
        self.data_sources.pop(source_id, None)
        for grid in self._grids():
            with self._tab_context(grid):
                for subplot in list(self.project.subplots):
                    for series in [s for s in subplot.series if s.source_id == source_id]:
                        self._remove_series_from(subplot, series.id)
        self._refresh_active_subplot_controls()
        self.statusBar().showMessage("Closed a data file")

    def _on_all_files_closed(self) -> None:
        """Reset back to the exact same blank state as before any CSV was
        ever opened -- the "start over" action that used to happen for free
        every time a new (single) CSV replaced the old one, before multi-CSV
        support made opening a new file additive instead (see
        _on_csv_loaded's is_first_source branch).
        """
        self.data_sources = {}
        self._layout_csv_path = None
        self._reset_tabs()
        self._refresh_selector_and_controls()
        self.statusBar().showMessage("Closed all files")

    def _on_source_renamed(self, source_id: str) -> None:
        """A file's nickname changed -- CsvPanel already mutated the shared
        DataSource.label in place (main_window.data_sources[source_id] is
        that same object), so only the places that baked the old label into
        already-built UI/graph text need to be refreshed: every subplot's
        legend text that mixes this source with another, and the active
        subplot's series list.
        """
        for grid in self._grids():
            with self._tab_context(grid):
                for subplot in self.project.subplots:
                    if any(s.source_id == source_id for s in subplot.series):
                        self._replot_subplot(subplot)
        self._refresh_active_subplot_controls()

    def _autorange_all_views(self) -> None:
        """Fit every subplot's X and Y range to its actual data, same as
        clicking each one's "A" (auto range) button.

        Deliberately computed directly from the underlying column data
        rather than by asking pyqtgraph's ViewBox to auto-fit (via
        enableAutoRange()/autoRange()/updateAutoRange()): all three were
        tried and, called immediately after a fresh replot, computed a bogus
        tiny range -- pyqtgraph's own auto-fit depends on the curve's
        on-screen downsampled/clipped representation, whose geometry hasn't
        actually propagated through Qt's scene graph yet at this point, and
        no amount of extra processEvents() after enabling it made that
        reliable. Computing the range ourselves from the raw column data has
        no such dependency on Qt's layout timing.
        """
        if not self.data_sources:
            return
        for subplot in self.project.subplots:
            ready = [s for s in subplot.series if self._series_ready(s)]
            if not ready:
                continue
            view = self.plot_grid.get_view(subplot.row, subplot.col)
            # Each series can come from a different file with its own X data
            # (see Series.x_column), so the fit range spans the union of
            # every ready series' own X/Y, not one shared array.
            x_min = min(float(np.nanmin(self._series_x_data(s))) for s in ready)
            x_max = max(float(np.nanmax(self._series_x_data(s))) for s in ready)
            y_min = min(float(np.nanmin(self._series_y_data(s))) for s in ready)
            y_max = max(float(np.nanmax(self._series_y_data(s))) for s in ready)
            if x_max > x_min:
                view.set_x_range(x_min, x_max, padding=0.02)
            if y_max > y_min:
                view.set_y_range(y_min, y_max, padding=0.02)
        self._sync_linked_views()

    def _snapshot_by_position(self, getter, predicate=lambda sp: True) -> dict[tuple[int, int], object]:
        """Capture getter(view) for every subplot satisfying predicate, keyed
        by grid (row, col) position rather than subplot id/object -- a grid
        rebuild discards and recreates every SubplotView, but each surviving
        subplot keeps its own (row, col), so position is what a later
        _apply_by_position() call can still look values back up by. Subplots
        failing predicate simply get no entry (not a None entry).
        """
        return {
            (sp.row, sp.col): getter(self.plot_grid.get_view(sp.row, sp.col))
            for sp in self.project.subplots
            if predicate(sp)
        }

    def _apply_by_position(self, snapshot: dict[tuple[int, int], object], setter) -> None:
        """Apply setter(view, value) for every subplot whose (row, col) has a
        non-None entry in `snapshot` -- see _snapshot_by_position.
        """
        for sp in self.project.subplots:
            value = snapshot.get((sp.row, sp.col))
            if value is not None:
                setter(self.plot_grid.get_view(sp.row, sp.col), value)

    def _capture_current_y_ranges(self) -> None:
        """Snapshot each subplot's on-screen Y range (primary + secondary,
        whatever the user last zoomed/panned to, or whatever autorange last
        computed) into the project so Save Layout persists it. An empty
        subplot has no meaningful view to capture, so it's reset to None
        rather than saving pyqtgraph's meaningless default (0, 1) range.
        """
        has_series = lambda sp: sp.series
        left = self._snapshot_by_position(lambda v: list(v.get_y_range()), has_series)
        right = self._snapshot_by_position(
            lambda v: list(v.get_y_range(secondary=True)) if v.has_secondary_series() else None, has_series
        )
        for subplot in self.project.subplots:
            key = (subplot.row, subplot.col)
            subplot.y_range_left = left.get(key)
            subplot.y_range_right = right.get(key)

    def _capture_data_source_refs(self) -> None:
        self.project.data_sources = [SourceRef.from_source(s) for s in self.data_sources.values()]

    def _restore_saved_y_ranges(self) -> None:
        """Apply each subplot's saved Y range (see _capture_current_y_ranges)
        on top of whatever _autorange_all_views() just computed -- a
        subplot with no saved range (never saved before, or had none to
        capture) is left at that fresh autorange fit instead.
        """
        populated = [sp for sp in self.project.subplots if sp.series]
        left = {(sp.row, sp.col): sp.y_range_left for sp in populated}
        self._apply_by_position(left, lambda v, r: v.set_y_range(*r, padding=0))
        right = {
            (sp.row, sp.col): sp.y_range_right
            for sp in populated
            if self.plot_grid.get_view(sp.row, sp.col).has_secondary_series()
        }
        self._apply_by_position(right, lambda v, r: v.set_y_range(*r, secondary=True, padding=0))

    def _on_grid_dims_changed(self, rows: int, cols: int) -> None:
        # rebuild() below throws away every subplot's PlotItem/ViewBox --
        # including whatever X range the user had panned/zoomed to -- and
        # replaces them with fresh ones that start at the default (0, 1)
        # range. Capture each surviving subplot's current X range by
        # position first so it can be restored afterward instead of
        # silently resetting every other subplot's zoom just because the
        # grid dimensions changed.
        # Subplots with no series yet are still sitting at the meaningless
        # pyqtgraph default (0, 1) -- pinning that "previous" range after
        # the resize would permanently disable autoRange for them, so any
        # data dropped onto them afterward would stay stuck at (0, 1)
        # instead of fitting. Only preserve subplots that actually had
        # something plotted.
        previous_x_ranges = self._snapshot_by_position(lambda v: v.get_x_range(), predicate=lambda sp: sp.series)

        self.project.resize_grid(rows, cols)
        self.plot_grid.rebuild(rows, cols)

        self._refresh_selector_and_controls()
        self._replot_all_subplots()

        self._apply_by_position(previous_x_ranges, lambda v, r: v.set_x_range(*r, padding=0))

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

    def _on_subplot_link_x_toggled(self, enabled: bool) -> None:
        subplot = self._active_subplot()
        subplot.link_x_axis = enabled
        self._sync_linked_views()

    def _on_canvas_subplot_clicked(self, row: int, col: int) -> None:
        subplot = self._subplot_at(row, col)
        if subplot is not None:
            self._set_active_subplot(subplot.id)

    def _on_series_x_column_changed(self, column_name: str) -> None:
        series = self._selected_series()
        if series is None:
            return
        series.x_column = column_name
        self._replot_subplot(self._active_subplot())

    def _on_series_x_offset_changed(self, value: float) -> None:
        series = self._selected_series()
        if series is None:
            return
        series.x_offset = value
        self._replot_subplot(self._active_subplot())

    def _on_series_zero_at_start_requested(self) -> None:
        series = self._selected_series()
        if series is None:
            return
        source = self.data_sources.get(series.source_id)
        if source is None or source.store is None or not series.x_column:
            return
        raw_x = source.store.get(series.x_column)
        series.x_offset = -float(np.nanmin(raw_x))
        self.style_panel.set_x_offset(series.x_offset)
        self._replot_subplot(self._active_subplot())

    def _on_apply_x_to_matching_series_requested(self) -> None:
        """Copy the selected series' X column/offset onto every other series
        (in any subplot) that shares its source_id -- the per-series
        successor to the old "Apply X to All Subplots" button, scoped to the
        one file this series actually belongs to instead of every subplot,
        since X is no longer a whole-subplot setting.

        Deliberately does not autorange afterward: unlike a fresh column
        drop, this is a bulk edit to series that already had *some* X column
        chosen and a view range the user may have already set up -- forcing
        every affected subplot to re-fit would blow away that state. A
        subplot that needs its range resynced to the new X data can use its
        own "A" (auto range) button, or be kept in step automatically via
        "Link X axis with other linked subplots".
        """
        series = self._selected_series()
        if series is None or not series.x_column:
            return
        count = 0
        for subplot in self.project.subplots:
            for other in subplot.series:
                if other.id == series.id or other.source_id != series.source_id:
                    continue
                other.x_column = series.x_column
                other.x_offset = series.x_offset
                count += 1
        self._replot_all_subplots()
        self.statusBar().showMessage(
            f"Applied to {count} other series from {self._source_label(series.source_id)}"
        )

    def _find_series_to_move(
        self, subplot: SubplotConfig, source_id: str, column_name: str, series_id: str = ""
    ) -> tuple[SubplotConfig, Series] | None:
        """A column already plotted in a *different* subplot gets moved to the
        drop target instead of duplicated there -- dragging it onto another
        subplot reads as "move this series here", not "add a second copy".
        Only called for a move-intent drop (see _on_column_dropped) -- a drag
        out of the Data tab's raw column list always adds instead, even when
        this would otherwise match, since that list isn't dragging an
        already-placed series in the first place.

        `series_id`, when given (a real drag from the series list always
        supplies it -- see column_drag.start_column_drag), picks out that
        *exact* series: unambiguous even if the same column is already
        plotted in more than one other subplot, since the drag names which
        placed series it's dragging, not just which column. Without it
        (direct calls, e.g. from tests), falls back to matching by (source,
        column) together, which stays ambiguous -- and so leaves every
        copy alone -- once more than one other subplot has a match, since
        which one to move would otherwise be a guess.
        """
        if series_id:
            for sp in self.project.subplots:
                if sp.id == subplot.id:
                    continue
                series = sp.get_series(series_id)
                if series is not None:
                    return sp, series
            return None
        matches = [
            (sp, s)
            for sp in self.project.subplots
            if sp.id != subplot.id
            for s in sp.series
            if s.y_column == column_name and s.source_id == source_id
        ]
        return matches[0] if len(matches) == 1 else None

    def _build_dropped_series(self, subplot: SubplotConfig, source: DataSource, source_id: str, column_name: str) -> Series:
        """A mostly-empty column (e.g. a rarely-updated periodic "echo"
        field) has its few real samples too far apart for a plain
        connecting line to ever draw between two of them -- default it to
        marker-only so it's visible immediately instead of looking like
        nothing was added. A connecting line would also be misleading here
        even on the rare occasion two real samples do land on adjacent
        rows: it implies a smooth transition between two far-apart
        timestamps that isn't actually in the data.
        """
        sparse = source.store.is_sparse(column_name)
        return Series(
            y_column=column_name,
            source_id=source_id,
            x_column=self._default_x_column_for_source(source) or "",
            color=next_default_color(len(subplot.series)),
            marker="dot" if sparse else None,
            line_style="none" if sparse else "solid",
        )

    def _on_column_dropped(
        self,
        row: int,
        col: int,
        source_id: str,
        column_name: str,
        move: bool = True,
        series_id: str = "",
    ) -> None:
        source = self.data_sources.get(source_id)
        if source is None or source.store is None:
            self.statusBar().showMessage("Still loading the CSV -- please wait before adding series")
            return
        if column_name not in source.store.numeric_column_names():
            return
        subplot = self._subplot_at(row, col)
        if subplot is None:
            return

        # `move` is False only for a drag out of the Data tab's raw column
        # list (see column_drag.start_column_drag) -- that always adds,
        # never relocates, even if the column is already plotted elsewhere.
        match = self._find_series_to_move(subplot, source_id, column_name, series_id) if move else None
        moved_from: tuple[int, int] | None = None
        if match is not None:
            # Move the existing Series object itself rather than deleting it
            # and adding a fresh default-styled one -- a move should carry
            # over whatever color/marker/axis the user already set on it,
            # not reset to defaults just because it changed subplots.
            source_subplot, series = match
            self._remove_series_from(source_subplot, series.id)
            moved_from = (source_subplot.row, source_subplot.col)
            subplot.add_series(series)
        else:
            series = self._build_dropped_series(subplot, source, source_id, column_name)
            subplot.add_series(series)

        self._set_active_subplot(subplot.id)
        self._refresh_active_subplot_controls()
        self._replot_subplot(subplot)
        self.series_panel.select_series_id(series.id)
        if moved_from is not None:
            self.statusBar().showMessage(f"Moved '{column_name}' from {moved_from} to ({row}, {col})")

    def _set_style_series(self, *args) -> None:
        """StylePanel.set_series, keeping the right dock at the width it had.

        The style section is shown only while a series is selected, and until
        the user drags a dock's edge QMainWindow sizes it from its contents'
        size hint -- so selecting/deselecting a series made the whole right
        dock jump wider/narrower. Re-applying the previous width pins it
        (resizeDocks clamps to the new minimum width if that is larger).
        """
        width = self._config_dock.width()
        self.style_panel.set_series(*args)
        if self._config_dock.isVisible() and not self._config_dock.isFloating():
            self.resizeDocks([self._config_dock], [width], Qt.Horizontal)

    def _on_series_selection_changed(self, series_id: str) -> None:
        self._selected_series_id = series_id
        subplot = self._active_subplot()
        series = subplot.get_series(series_id) if series_id else None
        x_options = self._source_column_options(series.source_id) if series else []
        self._set_style_series(series, len(subplot.series), x_options)

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
        current = getattr(subplot, field) or (subplot.default_x_label() if axis_name == "bottom" else "")
        text, ok = QInputDialog.getText(self, "Edit axis label", "Label:", text=current)
        if ok:
            setattr(subplot, field, text)
            self._replot_subplot(subplot)

    def _on_series_axis_changed(self, axis: str) -> None:
        series = self._selected_series()
        if series is None or series.axis == axis:
            return
        subplot = self._active_subplot()
        series.axis = axis
        self._push_series_data(self._active_view(), subplot, series)
        # Reassigning a series to/from the secondary axis changes whether this
        # subplot's right axis needs its shared reserved width (see
        # PlotGridWidget._sync_right_axis_widths) -- without this, the other
        # subplots' columns wouldn't pick up the new width until some later
        # unrelated replot.
        self.plot_grid.schedule_axis_width_sync()
        self._refresh_series_list()
        self.series_panel.select_series_id(series.id)

    def _on_style_changed(self) -> None:
        series = self._selected_series()
        if series is None:
            return
        series.color = self.style_panel.current_color()
        series.line_style = self.style_panel.current_line_style()
        series.marker = self.style_panel.current_marker()
        series.width = self.style_panel.current_width()
        self._active_view().update_series_style(series)

    def _on_series_transform_changed(self) -> None:
        series = self._selected_series()
        if series is None:
            return
        subplot = self._active_subplot()
        series.scale = self.style_panel.current_scale()
        series.offset = self.style_panel.current_offset()
        self._push_series_data(self._active_view(), subplot, series)

    def _on_style_remove_requested(self) -> None:
        if self._selected_series_id:
            self._remove_series(self._selected_series_id)

    # -- layout files ----------------------------------------------------------
    # "Layout" = every tab (the multi-tab file format); "Tab" = the current tab
    # only (the single-tab format every layout file had before tabs existed).

    def _capture_tab_for_saving(self, grid: PlotGridWidget) -> ProjectState:
        with self._tab_context(grid):
            self._capture_current_y_ranges()
            self._capture_data_source_refs()
            return self.project

    def _collect_layout(self) -> LayoutFile:
        return LayoutFile(
            tabs=[self._capture_tab_for_saving(grid) for grid in self._grids()],
            active_tab=self.layout_tabs.currentIndex(),
            legend_font_size=self._legend_font_size,
            multi_tab=True,
        )

    def _on_save_config(self) -> None:
        if not self._layout_csv_path:
            self.statusBar().showMessage("Load a CSV first")
            return
        config_path = config_path_for_csv(self._layout_csv_path)
        save_workspace(self._collect_layout(), str(config_path))
        self.statusBar().showMessage(f"Saved layout ({self.layout_tabs.count()} tabs) to {config_path.name}")

    def _on_save_config_as(self) -> None:
        if not self._layout_csv_path:
            self.statusBar().showMessage("Load a CSV first")
            return
        default_path = str(config_path_for_csv(self._layout_csv_path))
        path, _ = QFileDialog.getSaveFileName(self, "Save Layout As", default_path, "JSON Files (*.json)")
        if not path:
            return
        save_workspace(self._collect_layout(), path)
        self.statusBar().showMessage(f"Saved layout ({self.layout_tabs.count()} tabs) to {Path(path).name}")

    def _default_tab_file_path(self) -> str:
        """Beside the CSV, named after the current tab."""
        name = _FILENAME_UNSAFE.sub("_", self.project.name).strip(" .") or "layout"
        return str(Path(self._layout_csv_path).parent / f"{name}.json")

    def _on_save_tab_as(self) -> None:
        if not self._layout_csv_path:
            self.statusBar().showMessage("Load a CSV first")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Tab As", self._default_tab_file_path(), "JSON Files (*.json)"
        )
        if not path:
            return
        self._save_tab_to_path(path)

    def _save_tab_to_path(self, path: str) -> None:
        save_project(self._capture_tab_for_saving(self.plot_grid), path)
        self.statusBar().showMessage(f"Saved tab '{self.project.name}' to {Path(path).name}")

    def _warn_load_csv_first(self) -> None:
        # A layout is applied onto the currently open CSV(s) and never opens
        # files by itself, so without one there is nothing for it to map onto.
        QMessageBox.warning(self, "Load Layout", "Load a CSV file first, then load the layout.")

    def _on_load_config(self) -> None:
        if not self._layout_csv_path:
            self._warn_load_csv_first()
            return
        config_path = config_path_for_csv(self._layout_csv_path)
        if not config_path.exists():
            self.statusBar().showMessage(f"No saved layout found at {config_path.name}")
            return
        self._load_layout_from_path(str(config_path))

    def _on_load_config_as(self) -> None:
        if not self._layout_csv_path:
            self._warn_load_csv_first()
            return
        path, _ = QFileDialog.getOpenFileName(self, "Load Layout As", "", "JSON Files (*.json)")
        if not path:
            return
        self._load_layout_from_path(path)

    def _read_layout_file(self, path: str) -> LayoutFile | None:
        try:
            return load_layout_file(path)
        except Exception as exc:
            self.statusBar().showMessage(f"Failed to load layout: {exc}")
            return None

    def _ask_replace_or_append(self, layout: LayoutFile, file_name: str) -> str:
        """"replace", "append" or "" (cancelled)."""
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Question)
        box.setWindowTitle("Load Layout")
        count = len(layout.tabs)
        box.setText(
            f"{file_name} has {count} tab{'s' if count != 1 else ''}.\n"
            "Replace the open tabs with them, or add them after the open tabs?"
        )
        replace_button = box.addButton("Replace", QMessageBox.ButtonRole.AcceptRole)
        append_button = box.addButton("Append", QMessageBox.ButtonRole.ActionRole)
        box.addButton(QMessageBox.StandardButton.Cancel)
        box.setDefaultButton(replace_button)
        box.exec()
        clicked = box.clickedButton()
        if clicked is replace_button:
            return "replace"
        if clicked is append_button:
            return "append"
        return ""

    def _load_layout_from_path(self, path: str, mode: str = "ask") -> None:
        """Load every tab in a layout file. `mode`: "replace" the open tabs,
        "append" after them, or "ask" the user which."""
        layout = self._read_layout_file(path)
        if layout is None:
            return
        if mode == "ask":
            mode = self._ask_replace_or_append(layout, Path(path).name)
        if mode == "replace":
            dropped = self._replace_all_tabs(layout)
        elif mode == "append":
            dropped = self._append_tabs(layout)
        else:
            return
        self._refresh_selector_and_controls()

        count = len(layout.tabs)
        message = f"Loaded layout ({count} tab{'s' if count != 1 else ''}) from {Path(path).name}"
        if dropped:
            message += f" ({dropped} series dropped: no longer valid)"
        self.statusBar().showMessage(message)

    def _replace_all_tabs(self, layout: LayoutFile) -> int:
        """Swap every open tab for the layout's tabs, its legend text size
        included. Returns how many series were dropped as no longer valid."""
        old_grids = self._grids()
        self._legend_font_size = layout.legend_font_size
        new_grids = [self._add_tab(project) for project in layout.tabs]
        for grid in old_grids:
            self._remove_tab(grid)
        dropped = sum(
            self._show_project_in_tab(grid, project, restore_saved_ranges=True)
            for grid, project in zip(new_grids, layout.tabs)
        )
        self.layout_tabs.setCurrentIndex(layout.active_tab)
        self._sync_legend_font_menu()
        return dropped

    def _append_tabs(self, layout: LayoutFile) -> int:
        """Add the layout's tabs after the open ones (the app-wide legend
        text size stays as it is)."""
        dropped = 0
        first_new = self.layout_tabs.count()
        for project in layout.tabs:
            project.name = self._unique_tab_name(project.name)
            grid = self._add_tab(project)
            dropped += self._show_project_in_tab(grid, project, restore_saved_ranges=True)
        self.layout_tabs.setCurrentIndex(first_new + layout.active_tab)
        return dropped

    def _pick_tab(self, layout: LayoutFile, title: str) -> ProjectState | None:
        """The one tab to load from a layout file -- asked for when the
        file holds several."""
        if len(layout.tabs) == 1:
            return layout.tabs[0]
        names = [tab.name for tab in layout.tabs]
        name, ok = QInputDialog.getItem(
            self, title, "This file has several tabs. Load which one?", names, layout.active_tab, False
        )
        if not ok:
            return None
        return layout.tabs[names.index(name)]

    def _ask_tab_file(self, title: str) -> str:
        if not self._layout_csv_path:
            self._warn_load_csv_first()
            return ""
        path, _ = QFileDialog.getOpenFileName(self, title, "", "JSON Files (*.json)")
        return path

    def _on_load_tab_as(self) -> None:
        path = self._ask_tab_file("Load Tab As")
        if path:
            self._load_tab_from_path(path, new_tab=False)

    def _on_load_tab_as_new(self) -> None:
        path = self._ask_tab_file("Load Tab As New")
        if path:
            self._load_tab_from_path(path, new_tab=True)

    def _load_tab_from_path(self, path: str, new_tab: bool) -> None:
        """Load one tab from a layout file into the current tab (replacing
        it) or into a new tab. A single-tab file's tab is named after the
        file; a multi-tab file's keeps its saved name."""
        layout = self._read_layout_file(path)
        if layout is None:
            return
        project = self._pick_tab(layout, "Load Tab As New" if new_tab else "Load Tab As")
        if project is None:
            return
        if new_tab:
            project.name = self._unique_tab_name(project.name)
            grid = self._add_tab(project, self.layout_tabs.currentIndex() + 1)
        else:
            grid = self.plot_grid
            project.name = self._unique_tab_name(project.name, ignore=grid)
        dropped = self._show_project_in_tab(grid, project, restore_saved_ranges=True)
        self._refresh_selector_and_controls()

        message = f"Loaded tab '{project.name}' from {Path(path).name}"
        if dropped:
            message += f" ({dropped} series dropped: no longer valid)"
        self.statusBar().showMessage(message)
