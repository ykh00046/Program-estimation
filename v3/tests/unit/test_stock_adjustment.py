"""apply_adjustment(재고 원복/재정산 + MOVE_ADJUST 이력) 단위 테스트 (PDCA #31).

임시 DB + LEGACY_DB_PATH 패치로 운영 데이터 격리(#27/#30 테스트 패턴 준수).
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


class StockAdjustmentTests(unittest.TestCase):
    """`apply_adjustment` 저수준 동작 + 무회귀 검증."""

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

    def _stock(self, code):
        for row in self.db.get_all_material_stock():
            if row["material_code"] == code:
                return row["current_stock"]
        return None

    # ── 가산(원복) ──
    def test_positive_delta_adds_stock_and_records_adjust(self):
        self.db.upsert_material_stock("M1", "재료A", 70.0, 0.0)
        updated = self.db.apply_adjustment(
            [{"material_code": "M1", "delta": 30.0}], "배합 기록 삭제 원복"
        )
        self.assertEqual(updated, 1)
        self.assertEqual(self._stock("M1"), 100.0)
        hist = self.db.get_stock_history("M1")
        self.assertEqual(len(hist), 1)
        self.assertEqual(hist[0]["change_type"], "ADJUST")
        self.assertEqual(hist[0]["quantity"], 30.0)        # 부호 +
        self.assertEqual(hist[0]["stock_after"], 100.0)
        self.assertEqual(hist[0]["note"], "배합 기록 삭제 원복")

    # ── 차감(재정산) + 0 floor ──
    def test_negative_delta_reduces_stock(self):
        self.db.upsert_material_stock("M1", "재료A", 100.0, 0.0)
        updated = self.db.apply_adjustment([{"material_code": "M1", "delta": -40.0}])
        self.assertEqual(updated, 1)
        self.assertEqual(self._stock("M1"), 60.0)
        self.assertEqual(self.db.get_stock_history("M1")[0]["quantity"], -40.0)

    def test_negative_delta_clamps_at_zero(self):
        self.db.upsert_material_stock("M1", "재료A", 30.0, 0.0)
        self.db.apply_adjustment([{"material_code": "M1", "delta": -50.0}])
        self.assertEqual(self._stock("M1"), 0.0)
        self.assertEqual(self.db.get_stock_history("M1")[0]["stock_after"], 0.0)

    # ── 합산 ──
    def test_same_code_deltas_aggregate(self):
        self.db.upsert_material_stock("M1", "재료A", 50.0, 0.0)
        updated = self.db.apply_adjustment([
            {"material_code": "M1", "delta": 30.0},
            {"material_code": "M1", "delta": -10.0},
        ])
        self.assertEqual(updated, 1)              # 합산 1회 UPDATE
        self.assertEqual(self._stock("M1"), 70.0)  # 50 +30 -10

    # ── 스킵 케이스 ──
    def test_zero_delta_and_blank_code_skipped(self):
        self.db.upsert_material_stock("M1", "재료A", 100.0, 0.0)
        updated = self.db.apply_adjustment([
            {"material_code": "M1", "delta": 0.0},
            {"material_code": "", "delta": 10.0},
        ])
        self.assertEqual(updated, 0)
        self.assertEqual(self._stock("M1"), 100.0)
        self.assertEqual(self.db.get_stock_history(), [])

    def test_unknown_material_skipped_no_history(self):
        self.db.upsert_material_stock("M1", "재료A", 100.0, 0.0)
        updated = self.db.apply_adjustment([
            {"material_code": "M1", "delta": 10.0},
            {"material_code": "GHOST", "delta": 99.0},   # 마스터에 없음 → 미생성
        ])
        self.assertEqual(updated, 1)
        codes = {r["material_code"] for r in self.db.get_all_material_stock()}
        self.assertEqual(codes, {"M1"})              # GHOST 행 생성 안 됨
        hist_codes = {h["material_code"] for h in self.db.get_stock_history()}
        self.assertEqual(hist_codes, {"M1"})         # GHOST 이력 없음

    def test_empty_returns_zero(self):
        self.assertEqual(self.db.apply_adjustment([]), 0)
        self.assertEqual(self.db.apply_adjustment(None), 0)

    # ── 무회귀: apply_consumption 은 여전히 CONSUME ──
    def test_consumption_still_records_consume(self):
        self.db.upsert_material_stock("M1", "재료A", 100.0, 0.0)
        updated = self.db.apply_consumption([{"material_code": "M1", "actual_amount": 40.0}])
        self.assertEqual(updated, 1)
        self.assertEqual(self.db.get_stock_history("M1")[0]["change_type"], "CONSUME")


if __name__ == "__main__":
    unittest.main()
