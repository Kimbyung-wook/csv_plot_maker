from __future__ import annotations

from PySide6.QtCore import QPoint, QSize, Qt, Signal
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


class _AddTabButton(QAbstractButton):
    """The "+" button, drawn as an unselected tab by the current style (so
    it looks like one more tab and follows the light/dark palette)."""

    def __init__(self, tab_bar: QTabBar) -> None:
        super().__init__(tab_bar)
        self._tab_bar = tab_bar
        self.setText("+")
        self.setToolTip("Add a layout tab")
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
        painter.setFont(font)
        painter.setPen(self.palette().windowText().color())
        painter.drawText(self.rect(), Qt.AlignCenter, self.text())


class _LayoutTabBar(QTabBar):
    """A tab bar with the "+" button sitting right after the last tab."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.add_button = _AddTabButton(self)

    def _button_width(self) -> int:
        return self.add_button.sizeHint().width()

    def sizeHint(self) -> QSize:
        hint = super().sizeHint()
        return QSize(hint.width() + self._button_width(), hint.height())

    def minimumSizeHint(self) -> QSize:
        hint = super().minimumSizeHint()
        return QSize(hint.width() + self._button_width(), hint.height())

    def _place_add_button(self) -> None:
        # QTabWidget only re-sizes its tab bar when tabs are added/removed, so
        # a tab that got wider (renamed) would push "+" off the bar's end.
        # Grow the bar ourselves (resizeEvent calls back here once more).
        parent = self.parentWidget()
        if parent is not None:
            wanted = min(self.sizeHint().width(), parent.width())
            if self.width() < wanted:
                self.resize(wanted, self.height())
                return
        size = self.add_button.sizeHint()
        x = self.tabRect(self.count() - 1).right() + 1 if self.count() else 0
        # With more tabs than fit, keep it visible at the right edge.
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

    Only the tab bar's own interactions live here (add button, rename,
    context menu, keeping the last tab unclosable); what a tab *holds* is
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
