"""StockSettingsDialog 스모크 테스트 (PDCA #27).

offscreen 환경에서 다이얼로그 생성/로드/저장 위임을 검증. 모달 hang 방지를 위해
QMessageBox를 patch한다(PDCA #20/#23 패턴).
"""
import importlib
import os
import sys
import unittest
from unittest.mock import MagicMock, patch


def _ensure_ui_deps() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    missing = []
    for name in ("PySide6", "qfluentwidgets"):
        try:
            importlib.import_module(name)
        except ModuleNotFoundError:
            missing.append(name)
    if missing:
        raise unittest.SkipTest(f"requires GUI deps: {', '.join(missing)}")


_ensure_ui_deps()

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from PySide6.QtWidgets import QApplication  # noqa: E402

from ui.dialogs.stock_settings_dialog import StockSettingsDialog  # noqa: E402

app = QApplication.instance() or QApplication(sys.argv)


def _make_dm(rows=None, default_threshold=0.0):
    dm = MagicMock()
    dm.seed_material_stock_from_history.return_value = 0
    dm.get_default_min_threshold.return_value = default_threshold
    dm.set_default_min_threshold.return_value = True
    dm.get_all_material_stock.return_value = rows or []
    dm.upsert_material_stock.return_value = True
    return dm


_SAMPLE = [
    {"material_code": "M1", "material_name": "재료A",
     "current_stock": 30.0, "min_stock_threshold": 100.0, "unit": "g"},
    {"material_code": "M2", "material_name": "재료B",
     "current_stock": 0.0, "min_stock_threshold": 50.0, "unit": "g"},
]


class StockSettingsDialogSmokeTests(unittest.TestCase):
    def test_loads_rows_into_table(self):
        dlg = StockSettingsDialog(_make_dm(_SAMPLE))
        self.assertEqual(dlg.table.rowCount(), 2)
        self.assertEqual(dlg.table.item(0, 0).text(), "M1")
        self.assertEqual(dlg.table.item(0, 1).text(), "재료A")

    def test_default_threshold_prefilled(self):
        dlg = StockSettingsDialog(_make_dm(_SAMPLE, default_threshold=500.0))
        self.assertEqual(dlg.default_threshold_edit.text(), "500")

    def test_save_delegates_upsert_for_each_row(self):
        dm = _make_dm(_SAMPLE)
        dlg = StockSettingsDialog(dm)
        with patch("ui.dialogs.stock_settings_dialog.QMessageBox"):
            dlg._on_save()
        self.assertEqual(dm.upsert_material_stock.call_count, 2)
        dm.set_default_min_threshold.assert_called_once()

    def test_reseed_button_invokes_seed(self):
        dm = _make_dm(_SAMPLE)
        dlg = StockSettingsDialog(dm)
        dm.seed_material_stock_from_history.reset_mock()
        with patch("ui.dialogs.stock_settings_dialog.QMessageBox"):
            dlg._on_reseed()
        dm.seed_material_stock_from_history.assert_called_once()

    def test_empty_rows_no_crash(self):
        dlg = StockSettingsDialog(_make_dm([]))
        self.assertEqual(dlg.table.rowCount(), 0)

    def test_auto_deduct_checkbox_reflects_setting(self):
        # PDCA #29: 체크박스가 get_auto_deduct_on_save 값을 반영
        dm = _make_dm(_SAMPLE)
        dm.get_auto_deduct_on_save.return_value = False
        dlg = StockSettingsDialog(dm)
        self.assertFalse(dlg.auto_deduct_check.isChecked())
        dm2 = _make_dm(_SAMPLE)
        dm2.get_auto_deduct_on_save.return_value = True
        dlg2 = StockSettingsDialog(dm2)
        self.assertTrue(dlg2.auto_deduct_check.isChecked())

    def test_save_persists_auto_deduct_toggle(self):
        # PDCA #29: 저장 시 set_auto_deduct_on_save 호출
        dm = _make_dm(_SAMPLE)
        dm.get_auto_deduct_on_save.return_value = True
        dlg = StockSettingsDialog(dm)
        dlg.auto_deduct_check.setChecked(False)
        with patch("ui.dialogs.stock_settings_dialog.QMessageBox"):
            dlg._on_save()
        dm.set_auto_deduct_on_save.assert_called_once_with(False)


if __name__ == "__main__":
    unittest.main()
