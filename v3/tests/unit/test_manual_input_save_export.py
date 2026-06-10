"""Unit tests for ManualInputInterface._save_and_export (PDCA #12).

Layer D1 (Orchestration) + Layer D3 (Error Paths).
외부 경계(DHR DB / ExcelExporter)는 모두 Mock으로 격리한다.
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
        raise unittest.SkipTest(
            f"UI tests require optional GUI dependencies: {', '.join(missing)}"
        )


_ensure_ui_test_dependencies()

from PySide6.QtWidgets import QApplication, QTableWidgetItem

current_dir = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(current_dir))
sys.path.insert(0, PROJECT_ROOT)

app = QApplication.instance() or QApplication(sys.argv)


def _sync_start_worker(owner, fn, *, args=(), kwargs=None,
                       on_result=None, on_failed=None, **_kw):
    """start_worker 동기 스텁 (PDCA #36) — 배선만 검증, 스레드 미사용."""
    try:
        result = fn(*args, **(kwargs or {}))
    except Exception as e:  # noqa: BLE001 — 워커 경계 모사
        if on_failed:
            on_failed(str(e))
    else:
        if on_result:
            on_result(result)


def _fill_row(panel, row, values):
    for col, value in enumerate(values):
        item = panel.table.item(row, col)
        if item is None:
            item = QTableWidgetItem("")
            panel.table.setItem(row, col, item)
        item.setText(str(value))


def _make_panel_with_data(product_lot_from_db="TEST-20260417-01"):
    """제품명/수량/자재 2행이 이미 채워진 패널 생성."""
    from ui.panels.manual_input_interface import ManualInputInterface

    mock_db = MagicMock()
    mock_db.generate_product_lot.return_value = product_lot_from_db
    mock_db.save_dhr_record.return_value = 42  # record_id

    panel = ManualInputInterface(dhr_db=mock_db, lot_manager=MagicMock())
    panel.product_name_edit.setText("TEST")
    panel.amount_spin.setValue(500.0)
    panel.table.setRowCount(0)
    panel._add_row()
    _fill_row(panel, 0, ["M1", "Mat1", "40", "200", "199.5", "L1"])
    panel._add_row()
    _fill_row(panel, 1, ["M2", "Mat2", "60", "300", "300.2", "L2"])
    return panel


class _SaveExportTestBase(unittest.TestCase):
    """D1/D3 공통 setUp/tearDown."""

    def setUp(self):
        self.panel = _make_panel_with_data()
        self.qmb_patcher = patch("ui.panels.manual_input_interface.QMessageBox")
        self.exp_patcher = patch("models.excel_exporter.ExcelExporter")
        # PDCA #36: 출력은 워커로 발사됨 — 동기 스텁으로 배선만 검증
        self.worker_patcher = patch(
            "ui.panels.manual_input_interface.start_worker", new=_sync_start_worker)
        self.mock_qmb = self.qmb_patcher.start()
        self.mock_exp_cls = self.exp_patcher.start()
        self.worker_patcher.start()
        self.mock_exp = self.mock_exp_cls.return_value
        self.mock_exp.export_to_excel.return_value = "/tmp/TEST-20260417-01.xlsx"
        self.mock_exp.export_to_pdf.return_value = "/tmp/TEST-20260417-01.pdf"

    def tearDown(self):
        self.qmb_patcher.stop()
        self.exp_patcher.stop()
        self.worker_patcher.stop()


# ---------------------------------------------------------------------------
# Layer D1 — Orchestration
# ---------------------------------------------------------------------------

class TestSaveAndExportOrchestration(_SaveExportTestBase):
    """정상 흐름에서 DB → Excel → PDF가 순서대로 호출되는지 검증."""

    def test_save_and_export_calls_db_then_excel_then_pdf(self):
        self.panel._save_and_export()

        self.panel.dhr_db.save_dhr_record.assert_called_once()
        self.mock_exp_cls.assert_called_once_with()
        self.mock_exp.export_to_excel.assert_called_once()
        self.mock_exp.export_to_pdf.assert_called_once()
        self.mock_qmb.information.assert_called_once()
        self.mock_qmb.critical.assert_not_called()

    def test_save_and_export_passes_resolved_lot_from_db(self):
        self.panel._save_and_export()

        record_args = self.panel.dhr_db.save_dhr_record.call_args[0]
        record_data = record_args[0]
        self.assertEqual(record_data["product_lot"], "TEST-20260417-01")

        export_data = self.mock_exp.export_to_excel.call_args[0][0]
        self.assertEqual(export_data["product_lot"], "TEST-20260417-01")
        self.assertEqual(self.panel.product_lot_edit.text(), "TEST-20260417-01")

    def test_save_and_export_passes_include_time_flag(self):
        self.panel.chk_include_time.setChecked(False)
        self.panel._save_and_export()

        record_data = self.panel.dhr_db.save_dhr_record.call_args[0][0]
        self.assertEqual(record_data["work_time"], "")

        _, kwargs = self.mock_exp.export_to_excel.call_args
        self.assertIs(kwargs.get("include_work_time"), False)

        export_data = self.mock_exp.export_to_excel.call_args[0][0]
        self.assertEqual(export_data["work_time"], "")

    def test_save_and_export_passes_materials_list_structure(self):
        self.panel._save_and_export()

        details = self.panel.dhr_db.save_dhr_record.call_args[0][1]
        self.assertEqual(len(details), 2)
        self.assertEqual(details[0]["material_code"], "M1")
        self.assertEqual(details[0]["material_name"], "Mat1")
        self.assertEqual(details[0]["material_lot"], "L1")
        self.assertEqual(details[0]["ratio"], 40.0)
        self.assertAlmostEqual(details[0]["theory_amount"], 200.0)
        self.assertAlmostEqual(details[0]["actual_amount"], 199.5)

        export_data = self.mock_exp.export_to_excel.call_args[0][0]
        self.assertEqual(export_data["materials"], details)

    def test_save_and_export_passes_scan_effects_to_pdf(self):
        expected = self.panel.scan_effects_panel.get_data()
        self.panel._save_and_export()

        args, _ = self.mock_exp.export_to_pdf.call_args
        self.assertEqual(args[0], "/tmp/TEST-20260417-01.xlsx")
        self.assertEqual(args[1], expected)


# ---------------------------------------------------------------------------
# Layer D3 — Error Paths
# ---------------------------------------------------------------------------

class TestSaveAndExportErrorPaths(_SaveExportTestBase):
    """DB/Excel/PDF 각 단계 실패 시 경로 검증."""

    def test_db_failure_shows_critical_and_skips_export(self):
        self.panel.dhr_db.save_dhr_record.side_effect = RuntimeError("db down")
        self.panel._save_and_export()

        self.mock_qmb.critical.assert_called_once()
        self.mock_exp_cls.assert_not_called()
        self.mock_exp.export_to_excel.assert_not_called()
        self.mock_exp.export_to_pdf.assert_not_called()

    def test_excel_failure_shows_partial_success_warning(self):
        self.mock_exp.export_to_excel.return_value = None
        self.panel._save_and_export()

        self.panel.dhr_db.save_dhr_record.assert_called_once()
        self.mock_qmb.warning.assert_called_once()
        self.mock_qmb.information.assert_not_called()
        # Excel 실패 시 PDF는 시도되지 않는다 (export_to_excel에서 RuntimeError raise)
        self.mock_exp.export_to_pdf.assert_not_called()

    def test_pdf_failure_keeps_excel_and_shows_partial_success(self):
        self.mock_exp.export_to_pdf.return_value = None
        self.panel._save_and_export()

        self.mock_exp.export_to_excel.assert_called_once()
        self.mock_exp.export_to_pdf.assert_called_once()
        self.mock_qmb.warning.assert_called_once()
        self.mock_qmb.information.assert_not_called()


if __name__ == "__main__":
    unittest.main()
