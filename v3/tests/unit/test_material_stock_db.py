"""material_stock 테이블 CRUD/시드 단위 테스트 (PDCA #27).

임시 DB + LEGACY_DB_PATH 패치로 운영 데이터 격리(기존 집계 테스트 패턴 준수).
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


def _detail(code, name, actual, order=1):
    return {
        "material_code": code, "material_name": name, "material_lot": "L1",
        "ratio": 100, "theory_amount": actual, "actual_amount": actual,
        "sequence_order": order,
    }


class MaterialStockDbTests(unittest.TestCase):
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

    def test_empty_db_returns_empty_list(self):
        self.assertEqual(self.db.get_all_material_stock(), [])

    def test_upsert_then_get_round_trip(self):
        ok = self.db.upsert_material_stock("M1", "재료A", 30.0, 100.0, "g")
        self.assertTrue(ok)
        rows = self.db.get_all_material_stock()
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["material_code"], "M1")
        self.assertEqual(row["material_name"], "재료A")
        self.assertEqual(row["current_stock"], 30.0)
        self.assertEqual(row["min_stock_threshold"], 100.0)

    def test_upsert_updates_existing_row(self):
        self.db.upsert_material_stock("M1", "재료A", 30.0, 100.0)
        self.db.upsert_material_stock("M1", "재료A개명", 80.0, 120.0)
        rows = self.db.get_all_material_stock()
        self.assertEqual(len(rows), 1)  # 중복 생성 없음(UNIQUE)
        self.assertEqual(rows[0]["material_name"], "재료A개명")
        self.assertEqual(rows[0]["current_stock"], 80.0)
        self.assertEqual(rows[0]["min_stock_threshold"], 120.0)

    def test_upsert_negative_clamped_to_zero(self):
        self.db.upsert_material_stock("M1", "재료A", -5.0, -10.0)
        row = self.db.get_all_material_stock()[0]
        self.assertEqual(row["current_stock"], 0.0)
        self.assertEqual(row["min_stock_threshold"], 0.0)

    def test_upsert_blank_code_fails(self):
        self.assertFalse(self.db.upsert_material_stock("", "", 1.0, 1.0))

    def test_get_low_stock_filters_and_sorts(self):
        self.db.upsert_material_stock("LOW", "부족", 10.0, 100.0)    # shortage 90
        self.db.upsert_material_stock("OK", "충분", 200.0, 100.0)    # 제외
        self.db.upsert_material_stock("MID", "중간", 70.0, 100.0)    # shortage 30
        self.db.upsert_material_stock("UNSET", "미설정", 0.0, 0.0)   # 임계값0→제외
        rows = self.db.get_low_stock_materials()
        codes = [r["material_code"] for r in rows]
        self.assertEqual(codes, ["LOW", "MID"])
        self.assertAlmostEqual(rows[0]["shortage"], 90.0)

    def test_get_low_stock_applies_default_threshold(self):
        # 자재별 임계값 0이지만 전역 기본 임계값으로 평가
        self.db.upsert_material_stock("M1", "재료A", 20.0, 0.0)
        self.assertEqual(self.db.get_low_stock_materials(default_threshold=0.0), [])
        rows = self.db.get_low_stock_materials(default_threshold=50.0)
        self.assertEqual(len(rows), 1)
        self.assertAlmostEqual(rows[0]["shortage"], 30.0)

    def test_pure_and_sql_paths_agree(self):
        """순수 함수 evaluate_inventory_alerts 와 SQL get_low_stock_materials 판정 일치(parity)."""
        from models.inventory_alert import evaluate_inventory_alerts
        self.db.upsert_material_stock("LOW", "부족", 10.0, 100.0)
        self.db.upsert_material_stock("OK", "충분", 200.0, 100.0)
        self.db.upsert_material_stock("MID", "중간", 70.0, 100.0)
        self.db.upsert_material_stock("UNSET", "미설정", 20.0, 0.0)
        default = 50.0
        sql_codes = [r["material_code"]
                     for r in self.db.get_low_stock_materials(default_threshold=default)]
        rows = self.db.get_all_material_stock()
        pure_codes = [a.material_code
                      for a in evaluate_inventory_alerts(rows, default_threshold=default)]
        self.assertEqual(set(sql_codes), set(pure_codes))
        # UNSET(현재고20 ≤ 기본50)도 양쪽 모두 포함
        self.assertIn("UNSET", sql_codes)
        self.assertIn("UNSET", pure_codes)

    # ------------------------------------------------------------------
    # apply_consumption (PDCA #29 — 배합 저장 시 자동 차감)
    # ------------------------------------------------------------------

    def test_apply_consumption_reduces_existing_stock(self):
        self.db.upsert_material_stock("M1", "재료A", 100.0, 0.0)
        updated = self.db.apply_consumption([{"material_code": "M1", "actual_amount": 40.0}])
        self.assertEqual(updated, 1)
        self.assertEqual(self.db.get_all_material_stock()[0]["current_stock"], 60.0)

    def test_apply_consumption_clamps_at_zero(self):
        self.db.upsert_material_stock("M1", "재료A", 30.0, 0.0)
        updated = self.db.apply_consumption([{"material_code": "M1", "actual_amount": 50.0}])
        self.assertEqual(updated, 1)
        self.assertEqual(self.db.get_all_material_stock()[0]["current_stock"], 0.0)

    def test_apply_consumption_aggregates_duplicate_codes(self):
        self.db.upsert_material_stock("M1", "재료A", 100.0, 0.0)
        updated = self.db.apply_consumption([
            {"material_code": "M1", "actual_amount": 30.0},
            {"material_code": "M1", "actual_amount": 20.0},
        ])
        self.assertEqual(updated, 1)  # 합산 1회 UPDATE
        self.assertEqual(self.db.get_all_material_stock()[0]["current_stock"], 50.0)

    def test_apply_consumption_skips_unknown_material(self):
        self.db.upsert_material_stock("M1", "재료A", 100.0, 0.0)
        updated = self.db.apply_consumption([
            {"material_code": "M1", "actual_amount": 10.0},
            {"material_code": "GHOST", "actual_amount": 99.0},  # 마스터에 없음 → 미생성
        ])
        self.assertEqual(updated, 1)
        codes = {r["material_code"] for r in self.db.get_all_material_stock()}
        self.assertEqual(codes, {"M1"})  # GHOST 행 생성 안 됨
        self.assertEqual(self.db.get_all_material_stock()[0]["current_stock"], 90.0)

    def test_apply_consumption_skips_nonpositive_and_blank(self):
        self.db.upsert_material_stock("M1", "재료A", 100.0, 0.0)
        updated = self.db.apply_consumption([
            {"material_code": "M1", "actual_amount": 0.0},
            {"material_code": "M1", "actual_amount": -5.0},
            {"material_code": "", "actual_amount": 10.0},
        ])
        self.assertEqual(updated, 0)
        self.assertEqual(self.db.get_all_material_stock()[0]["current_stock"], 100.0)

    def test_apply_consumption_empty_returns_zero(self):
        self.assertEqual(self.db.apply_consumption([]), 0)
        self.assertEqual(self.db.apply_consumption(None), 0)

    def test_seed_from_history_inserts_used_materials(self):
        record = {
            "product_lot": "L1", "recipe_name": "R1", "worker": "W1",
            "work_date": date.today().isoformat(), "work_time": "09:00:00",
            "total_amount": 100.0, "scale": "S1",
        }
        self.db.save_mixing_record(record, [_detail("MAT1", "재료1", 60.0),
                                            _detail("MAT2", "재료2", 40.0)])
        inserted = self.db.seed_material_stock_from_history()
        self.assertEqual(inserted, 2)
        codes = {r["material_code"] for r in self.db.get_all_material_stock()}
        self.assertEqual(codes, {"MAT1", "MAT2"})
        # 재시드는 중복 삽입 없음
        self.assertEqual(self.db.seed_material_stock_from_history(), 0)


if __name__ == "__main__":
    unittest.main()
