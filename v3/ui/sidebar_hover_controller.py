from typing import List

from PySide6.QtCore import QEvent, QObject, QTimer
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import QWidget
from qfluentwidgets import NavigationDisplayMode

from config.config_manager import config
from utils.logger import logger


class SidebarHoverController(QObject):
    """사이드바 호버 시 확장/축소 동작을 전담하는 컨트롤러."""

    def __init__(self, window) -> None:
        super().__init__(window)
        self._window = window
        self._enabled = bool(config.sidebar_hover_expand)
        self._hover_expanded = False
        self._filter_widgets: List[QWidget] = []

        self._collapse_timer = QTimer(window)
        self._collapse_timer.setSingleShot(True)
        self._collapse_timer.setInterval(200)
        self._collapse_timer.timeout.connect(self.collapse_after_hover)

        # 폴링 주기: 120ms→200ms. 페이지 전환 애니메이션과의 메인 스레드 경쟁을
        # 줄여 전환 시 끊김 완화(반응성 차이는 체감 미미).
        self._poll_timer = QTimer(window)
        self._poll_timer.setInterval(200)
        self._poll_timer.timeout.connect(self._poll_state)

    def is_enabled(self) -> bool:
        return bool(self._enabled)

    def set_enabled(self, enabled: bool, persist: bool = True) -> None:
        enabled = bool(enabled)
        self._enabled = enabled
        if persist:
            config.save_sidebar_hover_expand(enabled)

        if not enabled:
            self._collapse_timer.stop()
            self._poll_timer.stop()
            if self._hover_expanded:
                self.collapse_after_hover(force=True)
        elif hasattr(self._window, "navigationInterface"):
            self._poll_timer.start()

    def init_behavior(self) -> None:
        nav = getattr(self._window, "navigationInterface", None)
        if nav is None:
            return

        nav.setCollapsible(True)
        panel = getattr(nav, "panel", None)
        hover_widgets = [nav]
        if panel is not None:
            hover_widgets.append(panel)
            hover_widgets.extend(panel.findChildren(QWidget))

        # Install on all sidebar descendants because mouse enter/leave is often
        # received by internal scroll/viewport widgets instead of the panel.
        self._filter_widgets = []
        seen = set()
        for widget in hover_widgets:
            if widget is None:
                continue
            key = id(widget)
            if key in seen:
                continue
            seen.add(key)
            widget.installEventFilter(self._window)
            self._filter_widgets.append(widget)

        if self._enabled:
            self._poll_timer.start()

    def handle_filter_event(self, obj, event) -> None:
        nav = getattr(self._window, "navigationInterface", None)
        panel = getattr(nav, "panel", None) if nav else None

        if obj in self._filter_widgets or obj in (nav, panel):
            et = event.type()
            if et == QEvent.Enter:
                self._on_hover_enter()
            elif et == QEvent.Leave:
                self._on_hover_leave()

    def _on_hover_enter(self) -> None:
        if not self._enabled:
            return

        self._collapse_timer.stop()

        nav = getattr(self._window, "navigationInterface", None)
        panel = getattr(nav, "panel", None) if nav else None
        if nav is None or panel is None:
            return

        # `displayMode` can be unreliable for hover checks in some runtime states
        # (e.g. AUTO/MENU transitions). Treat a narrow panel as visually collapsed.
        is_visually_collapsed = (
            panel.width() <= 60
            or panel.displayMode in (NavigationDisplayMode.COMPACT, NavigationDisplayMode.MINIMAL)
        )
        if not is_visually_collapsed:
            return

        try:
            nav.expand()
            self._hover_expanded = True
        except Exception as e:
            logger.debug(f"sidebar hover expand skipped: {e}")

    def _on_hover_leave(self) -> None:
        if not self._enabled or not self._hover_expanded:
            return
        # Polling runs every 120ms; restarting a 220ms single-shot timer on every
        # tick prevents timeout from ever firing. Start only once per leave phase.
        if not self._collapse_timer.isActive():
            self._collapse_timer.start()

    def _cursor_in_sidebar_rect(self) -> bool:
        """nav/panel의 전역 rect만 검사하는 경량 판정(자식 위젯 순회 없음).

        미확장 상태의 enter fallback 전용 — 평상시(대부분의 시간) 폴링 비용을
        rect 검사 2회로 제한해 메인 스레드 부하를 최소화한다. 정밀 leave 감지가
        필요한 확장 상태에서는 _is_cursor_in_sidebar(자식 underMouse 포함)를 쓴다.
        """
        nav = getattr(self._window, "navigationInterface", None)
        panel = getattr(nav, "panel", None) if nav else None
        if nav is None or panel is None:
            return False

        global_pos = QCursor.pos()
        for widget in (panel, nav):
            try:
                if widget.isVisible() and widget.rect().contains(widget.mapFromGlobal(global_pos)):
                    return True
            except RuntimeError:
                continue
        return False

    def _is_cursor_in_sidebar(self) -> bool:
        nav = getattr(self._window, "navigationInterface", None)
        panel = getattr(nav, "panel", None) if nav else None
        if nav is None or panel is None:
            return False

        # Prefer Qt's hover state on actual descendants. This avoids global
        # coordinate mismatches and catches scroll/viewport children.
        for widget in self._filter_widgets:
            if widget is None or not widget.isVisible():
                continue
            try:
                if widget.underMouse():
                    return True
            except RuntimeError:
                # Widget can be deleted during shutdown/tab rebuild.
                continue

        global_pos = QCursor.pos()
        try:
            if panel.isVisible() and panel.rect().contains(panel.mapFromGlobal(global_pos)):
                return True
        except RuntimeError:
            pass

        try:
            if nav.isVisible() and nav.rect().contains(nav.mapFromGlobal(global_pos)):
                return True
        except RuntimeError:
            pass

        return False

    def _poll_state(self) -> None:
        if not self._enabled or not self._window.isVisible():
            return

        if self._hover_expanded:
            # 확장 상태: 정밀 leave 감지(자식 underMouse 순회 포함)
            if not self._is_cursor_in_sidebar():
                self._on_hover_leave()
        else:
            # 미확장 평상시: enter는 이벤트 필터(Enter)가 1차 담당, 폴링은 경량 rect
            # 검사로 보강만 — 매 틱 전체 위젯 순회를 피해 상시 부하를 제거한다.
            if self._cursor_in_sidebar_rect():
                self._on_hover_enter()

    def collapse_after_hover(self, force: bool = False) -> None:
        if not self._hover_expanded:
            return

        nav = getattr(self._window, "navigationInterface", None)
        panel = getattr(nav, "panel", None) if nav else None
        if nav is None or panel is None:
            self._hover_expanded = False
            return

        if not force and self._is_cursor_in_sidebar():
            return

        if panel.displayMode in (NavigationDisplayMode.EXPAND, NavigationDisplayMode.MENU):
            try:
                panel.collapse()
            except Exception as e:
                logger.debug(f"sidebar hover collapse skipped: {e}")

        self._hover_expanded = False
