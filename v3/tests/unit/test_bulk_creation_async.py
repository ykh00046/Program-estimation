"""BulkCreationInterface 비동기 배선 테스트 (PDCA #36).

start_worker 동기 스텁 + DhrBulkGenerator mock — 스레드/COM 미사용.
"""
import importlib
import os
import sys
import unittest
from unittest.mock import MagicMock, patch


def _ensure_ui_test_dependencies() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    missing = []
    for module_name in ("PySide6", "qfluentwidgets"):
        try:
            importlib.import_module(module_name)
        except ModuleNotFoundError:
            missing.append(module_name)
    if missing:
        raise unittest.SkipTest(f"requires GUI deps: {', '.join(missing)}")


_ensure_ui_test_dependencies()

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from PySide6.QtWidgets import QApplication

from ui.panels.bulk_creation_interface import BulkCreationInterface

app = QApplication.instance() or QApplication(sys.argv)

_ENTRIES = [{"date": "2026-06-10", "amount": 100.0}]
_MATERIALS = [{"code": "M1", "name": "Mat1", "ratio": 50.0}]


class _RecordingSyncWorker:
    """start_worker 동기 스텁 — 호출 인자 기록 + 즉시 실행."""

    def __init__(self):
        self.calls = []

    def __call__(self, owner, fn, *, args=(), kwargs=None,
                 on_result=None, on_failed=None, busy_widgets=(), **_kw):
        self.calls.append({"busy_widgets": busy_widgets})
        try:
            result = fn(*args, **(kwargs or {}))
        except Exception as e:  # noqa: BLE001 — 워커 경계 모사
            if on_failed:
                on_failed(str(e))
        else:
            if on_result:
                on_result(result)


class BulkCreateAsyncTests(unittest.TestCase):

    def setUp(self):
        self.panel = BulkCreationInterface(dhr_db=MagicMock(), lot_manager=MagicMock())
        self.panel.product_name_edit.setText("제품A")
        self.stub = _RecordingSyncWorker()
        self.patchers = [
            patch("ui.panels.bulk_creation_interface.start_worker", new=self.stub),
            patch("ui.panels.bulk_creation_interface.QMessageBox"),
            patch("ui.panels.bulk_creation_interface.DhrBulkGenerator"),
            patch("ui.panels.bulk_creation_interface.parse_bulk_entries",
                  return_value=list(_ENTRIES)),
            patch("ui.panels.bulk_creation_interface.get_materials_from_table",
                  return_value=list(_MATERIALS)),
        ]
        started = [p.start() for p in self.patchers]
        self.mock_qmb = started[1]
        self.mock_gen_cls = started[2]
        self.mock_gen = self.mock_gen_cls.return_value
        self.mock_gen.generate.return_value = 3
        self.mock_gen.last_export_failures = []

    def tearDown(self):
        for p in self.patchers:
            p.stop()

    def test_success_runs_generate_in_worker_and_notifies_done(self):
        self.panel._bulk_create()
        self.assertEqual(len(self.stub.calls), 1)
        self.assertIn(self.panel.generate_btn, self.stub.calls[0]["busy_widgets"])
        kwargs = self.mock_gen.generate.call_args.kwargs
        self.assertEqual(kwargs["entries"], _ENTRIES)
        self.assertEqual(kwargs["product_name"], "제품A")
        self.assertEqual(kwargs["materials"], _MATERIALS)
        self.mock_qmb.information.assert_called_once()
        self.mock_qmb.critical.assert_not_called()

    def test_export_failures_show_partial_success(self):
        self.mock_gen.last_export_failures = ["LOT-A: PDF export failed"]
        self.panel._bulk_create()
        self.mock_qmb.warning.assert_called_once()
        self.assertIn("Partial Success", self.mock_qmb.warning.call_args[0][1])

    def test_generate_exception_shows_critical(self):
        self.mock_gen.generate.side_effect = ValueError("자재 LOT 누락")
        self.panel._bulk_create()
        self.mock_qmb.critical.assert_called_once()
        self.assertIn("자재 LOT 누락", self.mock_qmb.critical.call_args[0][2])

    def test_empty_product_name_skips_worker(self):
        self.panel.product_name_edit.setText("")
        self.panel._bulk_create()
        self.assertEqual(self.stub.calls, [])
        self.mock_gen.generate.assert_not_called()
        self.mock_qmb.warning.assert_called_once()

    def test_widget_values_are_snapshotted_into_generate_kwargs(self):
        """워커 함수가 위젯이 아닌 스냅샷 값을 사용하는지 검증."""
        self.panel.chk_include_time.setChecked(False)
        self.panel._bulk_create()
        kwargs = self.mock_gen.generate.call_args.kwargs
        self.assertIs(kwargs["include_time"], False)
        self.assertIsInstance(kwargs["scan_effects"], dict)
        self.assertIsInstance(kwargs["signature_options"], dict)


if __name__ == "__main__":
    unittest.main()
