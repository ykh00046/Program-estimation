"""배합 기록 수정/삭제 시 재고 원복·재정산 오케스트레이션 테스트 (PDCA #31).

DataManager 는 무거운 의존이 있어 ``__new__`` 로 인스턴스만 만들고 db_manager 만
임시 DB로 주입해 ``delete_record`` / ``update_record`` 의 재고 원복 경로를 격리 검증한다.
(#29 test_inventory_auto_deduction 패턴 준수)
"""
import os
import sys
import tempfile
import unittest
from datetime import date
from unittest.mock import patch


current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from models.database import MixingDatabaseManager  # noqa: E402
from models.data_manager import DataManager  # noqa: E402


def _detail(code, name, actual, order=1):
    return {
        "material_code": code, "material_name": name, "material_lot": "L1",
        "ratio": 100, "theory_amount": actual, "actual_amount": actual,
        "sequence_order": order,
    }


class InventoryReversalTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self._legacy_patch = patch(
            "models.database.LEGACY_DB_PATH",
            os.path.join(self.tmpdir.name, "__nonexistent_legacy.db"),
        )
        self._legacy_patch.start()
        db_path = os.path.join(self.tmpdir.name, "test_mixing.db")
        self.db = MixingDatabaseManager(db_path=db_path)
        self.dm = DataManager.__new__(DataManager)
        self.dm.db_manager = self.db

    def tearDown(self):
        self._legacy_patch.stop()
        self.tmpdir.cleanup()

    def _stock(self, code):
        for row in self.db.get_all_material_stock():
            if row["material_code"] == code:
                return row["current_stock"]
        return None

    def _adjust_hist(self, code):
        return [h for h in self.db.get_stock_history(code) if h["change_type"] == "ADJUST"]

    def _save_and_deduct(self, lot, details):
        """배합 기록 저장 + (#29) 차감을 재현한다."""
        record = {
            "product_lot": lot, "recipe_name": "R1", "worker": "W1",
            "work_date": date.today().isoformat(), "work_time": "09:00:00",
            "total_amount": sum(d["actual_amount"] for d in details), "scale": "S1",
        }
        self.db.save_mixing_record(record, details)
        with patch("models.data_manager.config.get", return_value=True):
            self.dm._deduct_inventory(details)

    # ── 삭제 원복 ──
    def test_delete_restores_stock_with_adjust_history(self):
        self.db.upsert_material_stock("M1", "재료A", 100.0, 0.0)
        self.db.upsert_material_stock("M2", "재료B", 50.0, 0.0)
        details = [_detail("M1", "재료A", 30.0, 1), _detail("M2", "재료B", 20.0, 2)]
        self._save_and_deduct("LOT-DEL", details)
        self.assertEqual(self._stock("M1"), 70.0)   # 차감 확인
        self.assertEqual(self._stock("M2"), 30.0)

        with patch("models.data_manager.config.get", return_value=True):
            ok = self.dm.delete_record("LOT-DEL")
        self.assertTrue(ok)
        self.assertEqual(self._stock("M1"), 100.0)  # 원복
        self.assertEqual(self._stock("M2"), 50.0)
        # 자재당 ADJUST(+) 1건
        h1 = self._adjust_hist("M1")
        self.assertEqual(len(h1), 1)
        self.assertEqual(h1[0]["quantity"], 30.0)
        self.assertEqual(h1[0]["stock_after"], 100.0)

    # ── 수정 재정산 (사용량 증가) ──
    def test_update_increase_readjusts_with_two_adjust_entries(self):
        self.db.upsert_material_stock("M1", "재료A", 100.0, 0.0)
        details = [_detail("M1", "재료A", 30.0)]
        self._save_and_deduct("LOT-UPD", details)
        self.assertEqual(self._stock("M1"), 70.0)

        new_materials = [_detail("M1", "재료A", 50.0)]  # 30 → 50
        with patch("models.data_manager.config.get", return_value=True):
            ok = self.dm.update_record("LOT-UPD", "W1", 50.0, new_materials)
        self.assertTrue(ok)
        # 원복 +30 → 100, 재차감 -50 → 50
        self.assertEqual(self._stock("M1"), 50.0)
        adj = self._adjust_hist("M1")
        self.assertEqual(len(adj), 2)                 # 2건 ADJUST
        quantities = sorted(h["quantity"] for h in adj)
        self.assertEqual(quantities, [-50.0, 30.0])   # 재차감 -50, 원복 +30

    # ── 수정 재정산 (사용량 감소) ──
    def test_update_decrease_readjusts(self):
        self.db.upsert_material_stock("M1", "재료A", 100.0, 0.0)
        details = [_detail("M1", "재료A", 40.0)]
        self._save_and_deduct("LOT-DEC", details)
        self.assertEqual(self._stock("M1"), 60.0)

        new_materials = [_detail("M1", "재료A", 10.0)]  # 40 → 10
        with patch("models.data_manager.config.get", return_value=True):
            self.dm.update_record("LOT-DEC", "W1", 10.0, new_materials)
        # 원복 +40 → 100, 재차감 -10 → 90
        self.assertEqual(self._stock("M1"), 90.0)

    # ── 토글 off ──
    def test_toggle_off_skips_reversal_on_delete(self):
        self.db.upsert_material_stock("M1", "재료A", 100.0, 0.0)
        details = [_detail("M1", "재료A", 30.0)]
        record = {
            "product_lot": "LOT-OFF", "recipe_name": "R1", "worker": "W1",
            "work_date": date.today().isoformat(), "work_time": "09:00:00",
            "total_amount": 30.0, "scale": "S1",
        }
        self.db.save_mixing_record(record, details)  # 차감 없이 저장만
        with patch("models.data_manager.config.get", return_value=False):
            ok = self.dm.delete_record("LOT-OFF")
        self.assertTrue(ok)
        self.assertEqual(self._stock("M1"), 100.0)        # 원복 미수행(불변)
        self.assertEqual(self._adjust_hist("M1"), [])     # ADJUST 이력 없음

    # ── best-effort: 원복 실패해도 삭제는 성공 ──
    def test_reversal_failure_does_not_block_delete(self):
        self.db.upsert_material_stock("M1", "재료A", 100.0, 0.0)
        details = [_detail("M1", "재료A", 30.0)]
        self._save_and_deduct("LOT-ERR", details)
        with patch("models.data_manager.config.get", return_value=True), \
                patch.object(self.db, "apply_adjustment", side_effect=RuntimeError("boom")):
            ok = self.dm.delete_record("LOT-ERR")
        self.assertTrue(ok)  # 삭제는 정상 반환
        # 레코드는 실제로 삭제됨
        self.assertIsNone(self.db.get_mixing_record_by_lot("LOT-ERR"))


if __name__ == "__main__":
    unittest.main()
