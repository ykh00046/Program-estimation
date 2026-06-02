"""자재 발주(purchase_orders) Repository 단위 테스트 (PDCA #32 purchase_order_management).

임시 DB + LEGACY_DB_PATH 패치로 운영 데이터 격리(기존 재고 테스트 패턴 준수).
발주 생성/조회/상태전이/입고 연동(재고+이력)/취소/별칭을 검증한다.
"""
import os
import sys
import tempfile
import unittest
from unittest.mock import patch


current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from models.database import MixingDatabaseManager  # noqa: E402
from models.repositories.purchase_order_repository import (  # noqa: E402
    PO_PENDING, PO_PARTIAL, PO_RECEIVED, PO_CANCELLED,
)
from models.repositories.material_stock_repository import MOVE_INBOUND  # noqa: E402


class PurchaseOrderDbTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self._legacy_patch = patch(
            "models.database.LEGACY_DB_PATH",
            os.path.join(self.tmpdir.name, "__nonexistent_legacy.db"),
        )
        self._legacy_patch.start()
        db_path = os.path.join(self.tmpdir.name, "test_mixing.db")
        self.db = MixingDatabaseManager(db_path=db_path)

    def tearDown(self):
        self._legacy_patch.stop()
        self.tmpdir.cleanup()

    # ---------------- 생성 / 조회 ----------------

    def test_create_returns_id_and_pending(self):
        po_id = self.db.create_purchase_order("M1", "재료A", "공급사X", 100.0, "g", "납기 6/10")
        self.assertIsNotNone(po_id)
        orders = self.db.get_purchase_orders()
        self.assertEqual(len(orders), 1)
        o = orders[0]
        self.assertEqual(o["material_code"], "M1")
        self.assertEqual(o["supplier"], "공급사X")
        self.assertEqual(o["ordered_qty"], 100.0)
        self.assertEqual(o["received_qty"], 0.0)
        self.assertEqual(o["remaining_qty"], 100.0)
        self.assertEqual(o["status"], PO_PENDING)
        self.assertTrue(o["po_number"].startswith("PO-"))

    def test_create_rejects_blank_code_and_nonpositive_qty(self):
        self.assertIsNone(self.db.create_purchase_order("", "", "공급사", 10.0))
        self.assertIsNone(self.db.create_purchase_order("M1", "재료A", "공급사", 0.0))
        self.assertIsNone(self.db.create_purchase_order("M1", "재료A", "공급사", -5.0))
        self.assertEqual(self.db.get_purchase_orders(), [])

    def test_po_number_increments_per_day(self):
        self.db.create_purchase_order("M1", "재료A", "", 10.0)
        self.db.create_purchase_order("M2", "재료B", "", 20.0)
        numbers = sorted(o["po_number"] for o in self.db.get_purchase_orders())
        self.assertTrue(numbers[0].endswith("-001"))
        self.assertTrue(numbers[1].endswith("-002"))

    def test_get_filters_by_status(self):
        pid1 = self.db.create_purchase_order("M1", "재료A", "", 100.0)
        self.db.create_purchase_order("M2", "재료B", "", 50.0)
        self.db.receive_purchase_order(pid1, 100.0)  # → RECEIVED
        pending = self.db.get_purchase_orders(PO_PENDING)
        received = self.db.get_purchase_orders(PO_RECEIVED)
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0]["material_code"], "M2")
        self.assertEqual(len(received), 1)
        self.assertEqual(received[0]["material_code"], "M1")

    # ---------------- 입고 연동 ----------------

    def test_receive_partial_sets_partial_and_updates_stock(self):
        pid = self.db.create_purchase_order("M1", "재료A", "", 100.0, "g")
        ok = self.db.receive_purchase_order(pid, 40.0)
        self.assertTrue(ok)
        o = self.db.get_purchase_orders()[0]
        self.assertEqual(o["received_qty"], 40.0)
        self.assertEqual(o["remaining_qty"], 60.0)
        self.assertEqual(o["status"], PO_PARTIAL)
        # 재고 누적
        stock = {s["material_code"]: s for s in self.db.get_all_material_stock()}
        self.assertEqual(stock["M1"]["current_stock"], 40.0)
        # INBOUND 이력 1건(부호 +, 발주번호 메모)
        hist = self.db.get_stock_history("M1")
        self.assertEqual(len(hist), 1)
        self.assertEqual(hist[0]["change_type"], MOVE_INBOUND)
        self.assertEqual(hist[0]["quantity"], 40.0)
        self.assertIn(o["po_number"], hist[0]["note"])

    def test_receive_remainder_sets_received(self):
        pid = self.db.create_purchase_order("M1", "재료A", "", 100.0)
        self.db.receive_purchase_order(pid, 40.0)
        self.db.receive_purchase_order(pid, 60.0)
        o = self.db.get_purchase_orders()[0]
        self.assertEqual(o["received_qty"], 100.0)
        self.assertEqual(o["status"], PO_RECEIVED)
        stock = {s["material_code"]: s for s in self.db.get_all_material_stock()}
        self.assertEqual(stock["M1"]["current_stock"], 100.0)
        self.assertEqual(len(self.db.get_stock_history("M1")), 2)

    def test_receive_default_qty_is_remaining(self):
        pid = self.db.create_purchase_order("M1", "재료A", "", 100.0)
        self.db.receive_purchase_order(pid, 30.0)
        # received_qty=None → 잔량(70) 전체
        ok = self.db.receive_purchase_order(pid)
        self.assertTrue(ok)
        o = self.db.get_purchase_orders()[0]
        self.assertEqual(o["received_qty"], 100.0)
        self.assertEqual(o["status"], PO_RECEIVED)

    def test_receive_on_received_fails(self):
        pid = self.db.create_purchase_order("M1", "재료A", "", 50.0)
        self.db.receive_purchase_order(pid, 50.0)  # RECEIVED
        self.assertFalse(self.db.receive_purchase_order(pid, 10.0))
        stock = {s["material_code"]: s for s in self.db.get_all_material_stock()}
        self.assertEqual(stock["M1"]["current_stock"], 50.0)  # 변동 없음
        self.assertEqual(len(self.db.get_stock_history("M1")), 1)

    def test_receive_nonpositive_fails(self):
        pid = self.db.create_purchase_order("M1", "재료A", "", 50.0)
        self.assertFalse(self.db.receive_purchase_order(pid, 0.0))
        self.assertFalse(self.db.receive_purchase_order(pid, -10.0))
        self.assertEqual(self.db.get_stock_history("M1"), [])

    def test_receive_unknown_po_fails(self):
        self.assertFalse(self.db.receive_purchase_order(9999, 10.0))

    def test_receive_overdelivery_caps_status_received(self):
        pid = self.db.create_purchase_order("M1", "재료A", "", 100.0)
        self.db.receive_purchase_order(pid, 120.0)  # 초과 입고
        o = self.db.get_purchase_orders()[0]
        self.assertEqual(o["received_qty"], 120.0)
        self.assertEqual(o["remaining_qty"], 0.0)  # 음수 → 0
        self.assertEqual(o["status"], PO_RECEIVED)

    # ---------------- 취소 ----------------

    def test_cancel_pending(self):
        pid = self.db.create_purchase_order("M1", "재료A", "", 100.0)
        self.assertTrue(self.db.cancel_purchase_order(pid))
        self.assertEqual(self.db.get_purchase_orders()[0]["status"], PO_CANCELLED)

    def test_cancel_partial(self):
        pid = self.db.create_purchase_order("M1", "재료A", "", 100.0)
        self.db.receive_purchase_order(pid, 40.0)
        self.assertTrue(self.db.cancel_purchase_order(pid))
        self.assertEqual(self.db.get_purchase_orders()[0]["status"], PO_CANCELLED)

    def test_cancel_received_fails(self):
        pid = self.db.create_purchase_order("M1", "재료A", "", 50.0)
        self.db.receive_purchase_order(pid, 50.0)
        self.assertFalse(self.db.cancel_purchase_order(pid))
        self.assertEqual(self.db.get_purchase_orders()[0]["status"], PO_RECEIVED)

    def test_cancel_does_not_revert_stock(self):
        pid = self.db.create_purchase_order("M1", "재료A", "", 100.0)
        self.db.receive_purchase_order(pid, 40.0)
        self.db.cancel_purchase_order(pid)
        stock = {s["material_code"]: s for s in self.db.get_all_material_stock()}
        self.assertEqual(stock["M1"]["current_stock"], 40.0)  # 입고분 보존

    def test_cancel_unknown_po_fails(self):
        self.assertFalse(self.db.cancel_purchase_order(9999))

    # ---------------- apply_replenishment 별칭 ----------------

    def test_apply_replenishment_alias_matches_add_inbound(self):
        ok = self.db.apply_replenishment("M9", "재료Z", 25.0, "g", "보충")
        self.assertTrue(ok)
        stock = {s["material_code"]: s for s in self.db.get_all_material_stock()}
        self.assertEqual(stock["M9"]["current_stock"], 25.0)
        hist = self.db.get_stock_history("M9")
        self.assertEqual(len(hist), 1)
        self.assertEqual(hist[0]["change_type"], MOVE_INBOUND)
        self.assertEqual(hist[0]["quantity"], 25.0)

    def test_apply_replenishment_rejects_nonpositive(self):
        self.assertFalse(self.db.apply_replenishment("M9", "재료Z", 0.0))
        self.assertFalse(self.db.apply_replenishment("M9", "재료Z", -3.0))

    # ---------------- 불변식 ----------------

    def test_receive_history_stock_after_consistency(self):
        pid = self.db.create_purchase_order("M1", "재료A", "", 100.0)
        self.db.receive_purchase_order(pid, 40.0)
        self.db.receive_purchase_order(pid, 30.0)
        hist = self.db.get_stock_history("M1")  # 최신순
        self.assertEqual(hist[0]["stock_after"], 70.0)
        self.assertEqual(hist[1]["stock_after"], 40.0)


if __name__ == "__main__":
    unittest.main()
