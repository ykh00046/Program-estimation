"""기록 조회 임베드 + 상태바 겹침 수정 스모크 (PDCA #38)."""
import importlib
import os
import sys
import unittest
from unittest.mock import MagicMock


def _ensure_ui_test_dependencies() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    missing = []
    for name in ("PySide6", "qfluentwidgets", "pandas"):
        try:
            importlib.import_module(name)
        except ModuleNotFoundError:
            missing.append(name)
    if missing:
        raise unittest.SkipTest(f"requires GUI deps: {', '.join(missing)}")


_ensure_ui_test_dependencies()

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from PySide6.QtWidgets import QApplication

from ui.builders import RecordsHostPage
from ui.components import StatusBar
from ui.controllers import StatusController
from ui.record_view_dialog import RecordViewDialog

app = QApplication.instance() or QApplication(sys.argv)


def _make_dm():
    dm = MagicMock()
    dm.get_mixing_records.return_value = []
    dm.get_all_material_names.return_value = []
    return dm


def _make_window(dm):
    window = MagicMock()
    window.data_manager = dm
    window.scan_effects_panel.get_data.return_value = {"dpi": 250}
    return window


class RecordsEmbedTests(unittest.TestCase):

    def test_show_creates_embedded_view_once(self):
        page = RecordsHostPage(_make_window(_make_dm()))
        page._ensure_view()
        first = page._view
        self.assertIsInstance(first, RecordViewDialog)
        self.assertTrue(first._embedded)
        page._ensure_view()
        self.assertIs(page._view, first)  # 재진입 시 재생성 아님

    def test_reshow_refreshes_records_and_effects(self):
        dm = _make_dm()
        window = _make_window(dm)
        page = RecordsHostPage(window)
        page._ensure_view()
        calls_before = dm.get_mixing_records.call_count
        window.scan_effects_panel.get_data.return_value = {"dpi": 300}
        page._ensure_view()
        self.assertGreater(dm.get_mixing_records.call_count, calls_before)  # 새로고침
        self.assertEqual(page._view.effects_params, {"dpi": 300})           # 효과 최신화

    def test_embedded_mode_hides_close_and_ignores_reject(self):
        view = RecordViewDialog(_make_dm(), {"dpi": 250}, embedded=True)
        labels = [b.text() for b in view.findChildren(type(view.export_btn))]
        self.assertNotIn("닫기", labels)
        view.show()
        view.reject()  # ESC 모사 — 임베드에선 숨겨지지 않아야 함
        self.assertTrue(view.isVisible())
        view.hide()

    def test_dialog_mode_keeps_close_button(self):
        view = RecordViewDialog(_make_dm(), {"dpi": 250}, embedded=False)
        labels = [b.text() for b in view.findChildren(type(view.export_btn))]
        self.assertIn("닫기", labels)


class StatusMessageOverlapTests(unittest.TestCase):
    """set_message가 main_label 단일 경로를 사용 — '준비됨' 겹침 방지."""

    def test_custom_statusbar_message_replaces_ready_label(self):
        bar = StatusBar()
        controller = StatusController(bar, MagicMock(), MagicMock())
        controller.set_message("기본 스케일: S1 | 허용오차: ±0.1")
        self.assertEqual(bar.main_label.text(), "기본 스케일: S1 | 허용오차: ±0.1")
        # showMessage 임시 메시지(겹침 원인)는 사용하지 않음
        self.assertEqual(bar.currentMessage(), "")

    def test_plain_statusbar_falls_back_to_show_message(self):
        plain = MagicMock(spec=["showMessage"])
        controller = StatusController(plain, MagicMock(), MagicMock())
        controller.set_message("hello")
        plain.showMessage.assert_called_once_with("hello")


if __name__ == "__main__":
    unittest.main()
