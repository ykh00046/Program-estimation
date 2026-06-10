"""DashboardPanel 내보내기 스모크 (PDCA #25)."""
import importlib
import os
import sys
import unittest
from unittest.mock import MagicMock, patch


def _ensure_ui_test_dependencies() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    missing = []
    for name in ("PySide6", "qfluentwidgets", "openpyxl"):
        try:
            importlib.import_module(name)
        except ModuleNotFoundError:
            missing.append(name)
    if missing:
        raise unittest.SkipTest(f"requires GUI deps: {', '.join(missing)}")


_ensure_ui_test_dependencies()

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from PySide6.QtWidgets import QApplication

from ui.panels.dashboard_panel import DashboardPanel
from models.dashboard_exporter import DashboardExporter

app = QApplication.instance() or QApplication(sys.argv)


def _sync_start_worker(owner, fn, *, args=(), kwargs=None,
                       on_result=None, on_failed=None, **_kw):
    """start_worker 동기 스텁 (PDCA #33) — 배선만 검증, 스레드 미사용."""
    try:
        result = fn(*args, **(kwargs or {}))
    except Exception as e:  # noqa: BLE001 — 워커 경계 모사
        if on_failed:
            on_failed(str(e))
    else:
        if on_result:
            on_result(result)


def _make_dm():
    dm = MagicMock()
    for m in ("get_monthly_production_stats", "get_top_materials",
              "get_worker_stats", "get_recipe_frequency"):
        getattr(dm, m).return_value = []
    return dm


class TestDashboardExportSmoke(unittest.TestCase):
    def test_panel_has_export_buttons_and_exporter(self):
        panel = DashboardPanel(_make_dm())
        self.assertIsInstance(panel._exporter, DashboardExporter)
        self.assertEqual(panel.export_excel_btn.text(), "Excel 내보내기")
        self.assertEqual(panel.export_pdf_btn.text(), "PDF 내보내기")

    def test_export_excel_delegates_and_opens_folder(self):
        panel = DashboardPanel(_make_dm())
        panel._exporter = MagicMock()
        panel._exporter.export_excel.return_value = "/out/대시보드_전체.xlsx"
        with patch("ui.panels.dashboard_panel.start_worker", new=_sync_start_worker), \
                patch("ui.panels.dashboard_panel.QMessageBox") as MB, \
                patch("ui.panels.dashboard_panel.os.startfile", create=True) as startfile:
            MB.Yes, MB.No = 1, 0
            MB.question.return_value = 1
            panel._export_excel()
        panel._exporter.export_excel.assert_called_once()
        startfile.assert_called_once()

    def test_export_pdf_failure_warns(self):
        panel = DashboardPanel(_make_dm())
        panel._exporter = MagicMock()
        panel._exporter.export_pdf.return_value = None
        with patch("ui.panels.dashboard_panel.start_worker", new=_sync_start_worker), \
                patch("ui.panels.dashboard_panel.QMessageBox") as MB, \
                patch("ui.panels.dashboard_panel.os.startfile", create=True) as startfile:
            panel._export_pdf()
        panel._exporter.export_pdf.assert_called_once()
        MB.warning.assert_called_once()
        startfile.assert_not_called()

    def test_export_exception_routes_to_error_dialog(self):
        """워커 실패 경로 — _notify_export_error로 경고 표시 (PDCA #33)."""
        panel = DashboardPanel(_make_dm())
        panel._exporter = MagicMock()
        panel._exporter.export_pdf.side_effect = RuntimeError("COM boom")
        with patch("ui.panels.dashboard_panel.start_worker", new=_sync_start_worker), \
                patch("ui.panels.dashboard_panel.QMessageBox") as MB:
            panel._export_pdf()
        MB.warning.assert_called_once()
        self.assertIn("COM boom", MB.warning.call_args[0][2])


if __name__ == "__main__":
    unittest.main()
