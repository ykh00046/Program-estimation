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
from ui.dialogs.inbound_dialog import InboundDialog  # noqa: E402
from ui.dialogs.stock_history_dialog import StockHistoryDialog  # noqa: E402

app = QApplication.instance() or QApplication(sys.argv)


def _make_dm(rows=None, default_threshold=0.0):
    dm = MagicMock()
    dm.seed_material_stock_from_history.return_value = 0
    dm.get_default_min_threshold.return_value = default_threshold
    dm.set_default_min_threshold.return_value = True
    dm.get_all_material_stock.return_value = rows or []
    dm.upsert_material_stock.return_value = True
    dm.add_inbound.return_value = True
    dm.get_stock_history.return_value = []
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


class InboundDialogSmokeTests(unittest.TestCase):
    """입고 등록 다이얼로그 스모크 (PDCA #30)."""

    def test_combo_lists_existing_materials_plus_blank(self):
        dlg = InboundDialog(_make_dm(_SAMPLE))
        # 빈 항목(신규 입력) + 기존 자재 2
        self.assertEqual(dlg.material_combo.count(), 3)

    def test_submit_delegates_add_inbound(self):
        dm = _make_dm(_SAMPLE)
        dlg = InboundDialog(dm)
        dlg.material_combo.setEditText("M9")
        dlg.name_edit.setText("신규자재")
        dlg.qty_edit.setText("25")
        dlg.note_edit.setText("매입처A")
        with patch("ui.dialogs.inbound_dialog.QMessageBox"):
            dlg._on_submit()
        dm.add_inbound.assert_called_once()
        args = dm.add_inbound.call_args[0]
        self.assertEqual(args[0], "M9")
        self.assertEqual(args[2], 25.0)

    def test_submit_rejects_nonpositive_quantity(self):
        dm = _make_dm(_SAMPLE)
        dlg = InboundDialog(dm)
        dlg.material_combo.setEditText("M9")
        dlg.qty_edit.setText("0")
        with patch("ui.dialogs.inbound_dialog.QMessageBox"):
            dlg._on_submit()
        dm.add_inbound.assert_not_called()

    def test_submit_rejects_blank_code(self):
        dm = _make_dm(_SAMPLE)
        dlg = InboundDialog(dm)
        dlg.material_combo.setEditText("")
        dlg.qty_edit.setText("10")
        with patch("ui.dialogs.inbound_dialog.QMessageBox"):
            dlg._on_submit()
        dm.add_inbound.assert_not_called()


class StockHistoryDialogSmokeTests(unittest.TestCase):
    """입출고 이력 다이얼로그 스모크 (PDCA #30)."""

    _HISTORY = [
        {"material_code": "M1", "material_name": "재료A", "change_type": "INBOUND",
         "quantity": 50.0, "stock_after": 50.0, "unit": "g", "note": "입고",
         "created_at": "2026-06-02 09:00:00"},
        {"material_code": "M1", "material_name": "재료A", "change_type": "CONSUME",
         "quantity": -20.0, "stock_after": 30.0, "unit": "g", "note": "배합 자동 차감",
         "created_at": "2026-06-02 10:00:00"},
    ]

    def test_loads_history_rows(self):
        dm = _make_dm(_SAMPLE)
        dm.get_stock_history.return_value = self._HISTORY
        dlg = StockHistoryDialog(dm)
        self.assertEqual(dlg.table.rowCount(), 2)
        # 유형 한글 라벨 + 부호 표기
        self.assertEqual(dlg.table.item(0, 2).text(), "입고")
        self.assertTrue(dlg.table.item(0, 3).text().startswith("+"))
        self.assertEqual(dlg.table.item(1, 2).text(), "차감")

    def test_filter_combo_includes_all_option(self):
        dm = _make_dm(_SAMPLE)
        dlg = StockHistoryDialog(dm)
        self.assertEqual(dlg.filter_combo.itemText(0), "전체")
        self.assertEqual(dlg.filter_combo.count(), 3)  # 전체 + 자재 2

    def test_empty_history_no_crash(self):
        dlg = StockHistoryDialog(_make_dm(_SAMPLE))
        self.assertEqual(dlg.table.rowCount(), 0)


class StockSettingsInventoryHubTests(unittest.TestCase):
    """재고 설정 다이얼로그의 입고/이력 진입점 (PDCA #30)."""

    def test_inbound_button_opens_dialog_and_reloads(self):
        dm = _make_dm(_SAMPLE)
        dlg = StockSettingsDialog(dm)
        fake = MagicMock()
        fake.return_value.exec.return_value = 1  # 등록 성공
        with patch("ui.dialogs.inbound_dialog.InboundDialog", fake):
            dm.get_all_material_stock.reset_mock()
            dlg._open_inbound()
        fake.assert_called_once()
        dm.get_all_material_stock.assert_called()  # 성공 후 재고 재조회

    def test_history_button_opens_dialog(self):
        dm = _make_dm(_SAMPLE)
        dlg = StockSettingsDialog(dm)
        fake = MagicMock()
        fake.return_value.exec.return_value = 0
        with patch("ui.dialogs.stock_history_dialog.StockHistoryDialog", fake):
            dlg._open_history()
        fake.assert_called_once()


if __name__ == "__main__":
    unittest.main()
