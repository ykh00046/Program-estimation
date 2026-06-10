"""ReconcileDialog 스모크 + 재고 설정 허브 배선 (PDCA #34).

offscreen Qt + mock data_manager. QMessageBox는 patch(모달 블록 방지, #23 교훈),
자식 다이얼로그는 클래스 mock(#30 교훈).
"""
import importlib
import os
import sys
import unittest
from unittest.mock import MagicMock, patch


def _ensure_ui_test_dependencies() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    missing = []
    for name in ("PySide6", "qfluentwidgets"):
        try:
            importlib.import_module(name)
        except ModuleNotFoundError:
            missing.append(name)
    if missing:
        raise unittest.SkipTest(f"requires GUI deps: {', '.join(missing)}")


_ensure_ui_test_dependencies()

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from ui.dialogs.reconcile_dialog import ReconcileDialog
from ui.dialogs.stock_settings_dialog import StockSettingsDialog

app = QApplication.instance() or QApplication(sys.argv)


def _make_dm(issues=None, lots=None):
    dm = MagicMock()
    dm.check_ledger_consistency.return_value = issues or []
    dm.find_undeducted_lots.return_value = lots or []
    dm.record_reconcile_entry.return_value = True
    dm.retro_deduct_lots.return_value = len(lots or [])
    return dm


_ISSUE = {"material_code": "M1", "material_name": "재료A",
          "current_stock": 80.0, "ledger_stock": 100.0, "drift": -20.0, "unit": "g"}
_LOT = {"product_lot": "LOT-A", "recipe_name": "R1",
        "work_date": "2026-06-10", "total_amount": 30.0}


class ReconcileDialogSmokeTests(unittest.TestCase):

    def test_empty_results_no_crash(self):
        dlg = ReconcileDialog(_make_dm())
        self.assertEqual(dlg.ledger_table.rowCount(), 0)
        self.assertEqual(dlg.lot_table.rowCount(), 0)
        self.assertFalse(dlg.reconcile_btn.isEnabled())
        self.assertFalse(dlg.retro_btn.isEnabled())

    def test_loads_issue_and_lot_rows(self):
        dlg = ReconcileDialog(_make_dm(issues=[_ISSUE], lots=[_LOT]))
        self.assertEqual(dlg.ledger_table.rowCount(), 1)
        self.assertEqual(dlg.ledger_table.item(0, 0).text(), "M1")
        self.assertEqual(dlg.lot_table.rowCount(), 1)
        self.assertEqual(dlg.lot_table.item(0, 0).text(), "LOT-A")
        self.assertTrue(dlg.reconcile_btn.isEnabled())
        self.assertTrue(dlg.retro_btn.isEnabled())

    def test_reconcile_confirmed_delegates_per_row(self):
        dm = _make_dm(issues=[_ISSUE])
        with patch("ui.dialogs.reconcile_dialog.QMessageBox") as MB:
            MB.Yes, MB.No = 1, 0
            MB.question.return_value = 1
            dlg = ReconcileDialog(dm)
            dlg._on_reconcile_ledger()
        dm.record_reconcile_entry.assert_called_once_with("M1")

    def test_reconcile_declined_does_nothing(self):
        dm = _make_dm(issues=[_ISSUE])
        with patch("ui.dialogs.reconcile_dialog.QMessageBox") as MB:
            MB.Yes, MB.No = 1, 0
            MB.question.return_value = 0
            dlg = ReconcileDialog(dm)
            dlg._on_reconcile_ledger()
        dm.record_reconcile_entry.assert_not_called()

    def test_retro_deduct_checked_lots_delegates(self):
        dm = _make_dm(lots=[_LOT])
        with patch("ui.dialogs.reconcile_dialog.QMessageBox") as MB:
            MB.Yes, MB.No = 1, 0
            MB.question.return_value = 1
            dlg = ReconcileDialog(dm)
            dlg.lot_table.item(0, 0).setCheckState(Qt.Checked)
            dlg._on_retro_deduct()
        dm.retro_deduct_lots.assert_called_once_with(["LOT-A"])

    def test_retro_deduct_without_selection_warns_no_delegate(self):
        dm = _make_dm(lots=[_LOT])
        with patch("ui.dialogs.reconcile_dialog.QMessageBox") as MB:
            dlg = ReconcileDialog(dm)
            dlg._on_retro_deduct()
        MB.warning.assert_called_once()
        dm.retro_deduct_lots.assert_not_called()


class StockSettingsReconcileWiringTests(unittest.TestCase):

    def test_reconcile_button_opens_dialog_and_reloads(self):
        dm = MagicMock()
        dm.seed_material_stock_from_history.return_value = 0
        dm.get_default_min_threshold.return_value = 0.0
        dm.get_all_material_stock.return_value = []
        dlg = StockSettingsDialog(dm)
        with patch("ui.dialogs.reconcile_dialog.ReconcileDialog") as MockDialog:
            MockDialog.return_value.exec.return_value = 1
            dlg._open_reconcile()
        MockDialog.assert_called_once()
        self.assertIs(MockDialog.call_args[0][0], dm)


if __name__ == "__main__":
    unittest.main()
