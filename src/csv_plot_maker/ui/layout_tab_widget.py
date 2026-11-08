from __future__ import annotations

from PySide6.QtCore import QCoreApplication, QEvent, QPoint, QSize, Qt, Signal
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import (
    QAbstractButton,
    QInputDialog,
    QMenu,
    QStyle,
    QStyleOptionTab,
    QTabBar,
    QTabWidget,
    QWidget,
)


class _TabShapedButton(QAbstractButton):
    """A small button ("+", "⋯") drawn as an unselected tab by the current
    style, so it looks like one more tab and follows the light/dark palette."""

    def __init__(self, tab_bar: QTabBar, text: str, tooltip: str, parent: QWidget | None = None) -> None:
        super().__init__(parent if parent is not None else tab_bar)
        self._tab_bar = tab_bar
        self.setText(text)
        self.setToolTip(tooltip)
        self.setCursor(Qt.PointingHandCursor)
        self.setAttribute(Qt.WA_Hover)

    def sizeHint(self) -> QSize:
        height = self._tab_bar.tabRect(0).height() if self._tab_bar.count() else 24
        return QSize(max(height, 28), height)

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        option = QStyleOptionTab()
        option.initFrom(self)
        option.shape = self._tab_bar.shape()
        option.documentMode = self._tab_bar.documentMode()
        option.position = QStyleOptionTab.TabPosition.End
        option.selectedPosition = QStyleOptionTab.SelectedPosition.NotAdjacent
        option.state &= ~QStyle.StateFlag.State_Selected
        if self.isDown():
            option.state |= QStyle.StateFlag.State_Sunken
        self.style().drawControl(QStyle.ControlElement.CE_TabBarTabShape, option, painter, self)
        font = painter.font()
        font.setBold(True)
        font.setPointSizeF(font.pointSizeF() * 1.3)
        painter.setFont(font)
        painter.setPen(self.palette().windowText().color())
        painter.drawText(self.rect(), Qt.AlignCenter, self.text())


class _LayoutTabBar(QTabBar):
    """A tab bar with the "+" button sitting right after the last tab."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.add_button = _TabShapedButton(self, "+", "Add a layout tab")
        # Set by LayoutTabWidget when the tabs don't all fit: the in-bar "+"
        # then hides and a copy pinned at the right end takes over.
        self.overflowing = False

    def _button_width(self) -> int:
        return 0 if self.overflowing else self.add_button.sizeHint().width()

    def tabs_width(self) -> int:
        """Width all tabs plus the in-bar "+" need to be shown unscrolled."""
        return super().sizeHint().width() + self.add_button.sizeHint().width()

    def sizeHint(self) -> QSize:
        hint = super().sizeHint()
        return QSize(hint.width() + self._button_width(), hint.height())

    def minimumSizeHint(self) -> QSize:
        hint = super().minimumSizeHint()
        return QSize(hint.width() + self._button_width(), hint.height())

    def _place_add_button(self) -> None:
        parent = self.parentWidget()
        if isinstance(parent, LayoutTabWidget):
            parent._update_overflow()
        if self.overflowing:
            self.add_button.hide()
            return
        self.add_button.show()
        # QTabWidget only re-sizes its tab bar when tabs are added/removed, so
        # a tab that got wider (renamed) would push "+" off the bar's end.
        # Grow the bar ourselves (resizeEvent calls back here once more).
        if parent is not None:
            wanted = min(self.sizeHint().width(), parent.width())
            if self.width() < wanted:
                self.resize(wanted, self.height())
                return
        size = self.add_button.sizeHint()
        x = self.tabRect(self.count() - 1).right() + 1 if self.count() else 0
        x = max(0, min(x, self.width() - size.width()))
        y = self.tabRect(0).top() if self.count() else 0
        self.add_button.setGeometry(x, y, size.width(), size.height())
        self.add_button.raise_()

    def tabLayoutChange(self) -> None:
        super().tabLayoutChange()
        self._place_add_button()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._place_add_button()


class LayoutTabWidget(QTabWidget):
    """The central area: one tab per layout, each page a PlotGridWidget.

    Only the tab bar's own interactions live here (add button, tab list,
    rename, context menu, keeping the last tab unclosable); what a tab *holds* is
    MainWindow's business, so adding/duplicating/closing are only requested
    via signals and carried out there.
    """

    add_requested = Signal()
    duplicate_requested = Signal(int)  # tab index
    close_requested = Signal(int)  # tab index
    rename_requested = Signal(int, str)  # tab index, new name

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setTabBar(_LayoutTabBar(self))
        self.setMovable(True)
        self.setDocumentMode(True)
        # Dragging a column/series over another tab's title switches to that
        # tab, so it can be dropped onto that tab's subplots.
        self.tabBar().setChangeCurrentOnDrag(True)
        self.tabBar().setAcceptDrops(True)

        self.add_button = self.tabBar().add_button
        self.add_button.clicked.connect(self.add_requested.emit)

        # When the tabs don't all fit (the bar scrolls), "⋯" at the left end
        # lists every tab to jump to, and "+" is pinned at the right end.
        self.list_button = _TabShapedButton(self.tabBar(), "⋯", "Show all layout tabs", self)
        self.list_button.clicked.connect(self._show_tab_list)
        self.setCornerWidget(self.list_button, Qt.TopLeftCorner)
        self.corner_add_button = _TabShapedButton(self.tabBar(), "+", "Add a layout tab", self)
        self.corner_add_button.clicked.connect(self.add_requested.emit)
        self.setCornerWidget(self.corner_add_button, Qt.TopRightCorner)
        self.list_button.hide()
        self.corner_add_button.hide()

        self.tabCloseRequested.connect(self.close_requested.emit)
        self.tabBarDoubleClicked.connect(self._on_tab_double_clicked)
        self.tabBar().setContextMenuPolicy(Qt.CustomContextMenu)
        self.tabBar().customContextMenuRequested.connect(self._on_tab_context_menu)

    def tab_names(self) -> list[str]:
        return [self.tabText(i) for i in range(self.count())]

    def pages(self) -> list[QWidget]:
        return [self.widget(i) for i in range(self.count())]

    def tabInserted(self, index: int) -> None:
        super().tabInserted(index)
        self._sync_closable()

    def tabRemoved(self, index: int) -> None:
        super().tabRemoved(index)
        self._sync_closable()

    def _sync_closable(self) -> None:
        # The last remaining tab can't be closed -- there is always a layout
        # to drop columns onto.
        self.setTabsClosable(self.count() > 1)
        # Showing/hiding the close buttons resizes the tabs without a
        # tabLayoutChange(), so the "+" button has to follow by hand.
        self.tabBar()._place_add_button()

    def is_overflowing(self) -> bool:
        return self.tabBar().overflowing

    def _update_overflow(self) -> None:
        bar = self.tabBar()
        overflowing = self.count() > 1 and bar.tabs_width() > self.width()
        if overflowing == bar.overflowing:
            return
        bar.overflowing = overflowing
        self.list_button.setVisible(overflowing)
        self.corner_add_button.setVisible(overflowing)
        # Corner widgets showing/hiding doesn't re-lay the bar out by itself.
        QCoreApplication.postEvent(self, QEvent(QEvent.Type.LayoutRequest))

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._update_overflow()

    def tab_list_menu(self) -> QMenu:
        """Menu of every tab (current one checked); choosing one switches to it."""
        menu = QMenu(self)
        for index, name in enumerate(self.tab_names()):
            action = menu.addAction(name)
            action.setCheckable(True)
            action.setChecked(index == self.currentIndex())
            action.triggered.connect(lambda _checked=False, i=index: self.setCurrentIndex(i))
        return menu

    def _show_tab_list(self) -> None:
        menu = self.tab_list_menu()
        menu.exec(self.list_button.mapToGlobal(self.list_button.rect().bottomLeft()))
        menu.deleteLater()

    def ask_rename(self, index: int) -> None:
        if not 0 <= index < self.count():
            return
        name, ok = QInputDialog.getText(self, "Rename tab", "Tab name:", text=self.tabText(index))
        name = name.strip()
        if ok and name:
            self.rename_requested.emit(index, name)

    def _on_tab_double_clicked(self, index: int) -> None:
        self.ask_rename(index)

    def _on_tab_context_menu(self, pos: QPoint) -> None:
        index = self.tabBar().tabAt(pos)
        if index < 0:
            return
        menu = QMenu(self)
        rename_action = menu.addAction("Rename...")
        duplicate_action = menu.addAction("Duplicate")
        close_action = menu.addAction("Close")
        close_action.setEnabled(self.count() > 1)
        chosen = menu.exec(self.tabBar().mapToGlobal(pos))
        if chosen is rename_action:
            self.ask_rename(index)
        elif chosen is duplicate_action:
            self.duplicate_requested.emit(index)
        elif chosen is close_action:
            self.close_requested.emit(index)
