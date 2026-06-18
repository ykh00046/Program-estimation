"""PurchaseOrderDialog 스모크 테스트 (PDCA #32 purchase_order_management).

offscreen 환경에서 발주 관리 다이얼로그 생성/로드/위임을 검증한다. 모달 hang 방지를 위해
QMessageBox/QInputDialog를 patch하고, 재고허브→발주 다이얼로그 배선은 자식 다이얼로그를
mock으로 대체해 segfault를 회피한다(PDCA #30 교훈 5).
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

from ui.dialogs.purchase_order_dialog import PurchaseOrderDialog, _NewOrderDialog  # noqa: E402
from ui.dialogs.stock_settings_dialog import StockSettingsDialog  # noqa: E402
from models.repositories.purchase_order_repository import (  # noqa: E402
    PO_PENDING, PO_PARTIAL,
)

app = QApplication.instance() or QApplication(sys.argv)


_SAMPLE_STOCK = [
    {"material_code": "M1", "material_name": "재료A",
     "current_stock": 30.0, "min_stock_threshold": 100.0, "unit": "g"},
]

_SAMPLE_POS = [
    {"id": 1, "po_number": "PO-20260602-001", "material_code": "M1", "material_name": "재료A",
     "supplier": "공급사X", "ordered_qty": 100.0, "received_qty": 40.0, "remaining_qty": 60.0,
     "unit": "g", "status": PO_PARTIAL, "note": ""},
    {"id": 2, "po_number": "PO-20260602-002", "material_code": "M2", "material_name": "재료B",
     "supplier": "", "ordered_qty": 50.0, "received_qty": 0.0, "remaining_qty": 50.0,
     "unit": "g", "status": PO_PENDING, "note": ""},
]


def _make_dm(pos=None, stock=None):
    dm = MagicMock()
    dm.get_purchase_orders.return_value = pos if pos is not None else list(_SAMPLE_POS)
    dm.get_all_material_stock.return_value = stock if stock is not None else list(_SAMPLE_STOCK)
    dm.create_purchase_order.return_value = 7
    dm.receive_purchase_order.return_value = True
    dm.cancel_purchase_order.return_value = True
    return dm


class PurchaseOrderDialogSmokeTests(unittest.TestCase):
    def test_loads_orders_into_table(self):
        dlg = PurchaseOrderDialog(_make_dm())
        self.assertEqual(dlg.table.rowCount(), 2)

    def test_empty_orders_no_crash(self):
        dlg = PurchaseOrderDialog(_make_dm(pos=[]))
        self.assertEqual(dlg.table.rowCount(), 0)

    def test_filter_combo_has_all_statuses(self):
        dlg = PurchaseOrderDialog(_make_dm())
        # 전체 + 4개 상태 = 5개
        self.assertEqual(dlg.filter_combo.count(), 5)

    def test_filter_change_requeries_with_status(self):
        dm = _make_dm()
        dlg = PurchaseOrderDialog(dm)
        dm.get_purchase_orders.reset_mock()
        dlg.filter_combo.setCurrentIndex(1)  # 대기(PENDING)
        dm.get_purchase_orders.assert_called()
        args = dm.get_purchase_orders.call_args[0]
        self.assertEqual(args[0], PO_PENDING)

    def test_receive_delegates_when_row_selected(self):
        dm = _make_dm()
        dlg = PurchaseOrderDialog(dm)
        dlg.table.setCurrentCell(0, 0)  # PARTIAL 행 선택
        with patch("ui.dialogs.purchase_order_dialog.QInputDialog.getDouble", return_value=(60.0, True)), \
             patch("ui.dialogs.purchase_order_dialog.QMessageBox"):
            dlg._on_receive()
        dm.receive_purchase_order.assert_called_once()
        self.assertEqual(dm.receive_purchase_order.call_args[0][0], 1)  # po id
        self.assertEqual(dm.receive_purchase_order.call_args[0][1], 60.0)

    def test_receive_without_selection_warns_no_delegate(self):
        dm = _make_dm()
        dlg = PurchaseOrderDialog(dm)
        dlg.table.setCurrentCell(-1, -1)
        with patch("ui.dialogs.purchase_order_dialog.QMessageBox"):
            dlg._on_receive()
        dm.receive_purchase_order.assert_not_called()

    def test_cancel_delegates_when_confirmed(self):
        dm = _make_dm()
        dlg = PurchaseOrderDialog(dm)
        dlg.table.setCurrentCell(1, 0)  # PENDING 행
        with patch("ui.dialogs.purchase_order_dialog.QMessageBox") as mb:
            mb.Yes = 1
            mb.question.return_value = 1
            dlg._on_cancel_order()
        dm.cancel_purchase_order.assert_called_once_with(2)


class NewOrderDialogSmokeTests(unittest.TestCase):
    def test_combo_lists_materials_plus_blank(self):
        dlg = _NewOrderDialog(_make_dm())
        # 빈 항목 + 자재 1종
        self.assertEqual(dlg.material_combo.count(), 2)

    def test_submit_delegates_create(self):
        dm = _make_dm()
        dlg = _NewOrderDialog(dm)
        dlg.material_combo.setEditText("M3")
        dlg.name_edit.setText("재료C")
        dlg.supplier_edit.setText("공급사Y")
        dlg.qty_edit.setText("80")
        with patch("ui.dialogs.purchase_order_dialog.QMessageBox"):
            dlg._on_submit()
        dm.create_purchase_order.assert_called_once()
        args = dm.create_purchase_order.call_args[0]
        self.assertEqual(args[0], "M3")
        self.assertEqual(args[3], 80.0)

    def test_submit_rejects_nonpositive_qty(self):
        dm = _make_dm()
        dlg = _NewOrderDialog(dm)
        dlg.material_combo.setEditText("M3")
        dlg.qty_edit.setText("0")
        with patch("ui.dialogs.purchase_order_dialog.QMessageBox"):
            dlg._on_submit()
        dm.create_purchase_order.assert_not_called()

    def test_submit_rejects_blank_code(self):
        dm = _make_dm()
        dlg = _NewOrderDialog(dm)
        dlg.material_combo.setEditText("")
        dlg.qty_edit.setText("50")
        with patch("ui.dialogs.purchase_order_dialog.QMessageBox"):
            dlg._on_submit()
        dm.create_purchase_order.assert_not_called()


class StockSettingsPurchaseOrderWiringTests(unittest.TestCase):
    def _make_settings_dm(self):
        dm = MagicMock()
        dm.seed_material_stock_from_history.return_value = 0
        dm.get_default_min_threshold.return_value = 0.0
        dm.get_all_material_stock.return_value = list(_SAMPLE_STOCK)
        return dm

    def test_po_button_opens_dialog_and_reloads(self):
        dm = self._make_settings_dm()
        dlg = StockSettingsDialog(dm)
        fake = MagicMock()
        with patch("ui.dialogs.purchase_order_dialog.PurchaseOrderDialog", fake):
            dm.get_all_material_stock.reset_mock()
            dlg._open_purchase_orders()
        fake.assert_called_once()           # 발주 다이얼로그 생성
        dm.get_all_material_stock.assert_called()  # 닫힌 뒤 재고 테이블 갱신


if __name__ == "__main__":
    unittest.main()
