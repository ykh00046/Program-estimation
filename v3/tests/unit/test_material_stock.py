"""자재 재고 임계값 알림 — DB 계층 단위 테스트 (PDCA: material-stock-threshold-alert)."""
import os
import sys
import tempfile
import unittest

# v3 루트를 import 경로에 추가
_V3_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _V3_ROOT not in sys.path:
    sys.path.insert(0, _V3_ROOT)

from models.database import MixingDatabaseManager


class TestMaterialStock(unittest.TestCase):
    def setUp(self) -> None:
        fd, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.db = MixingDatabaseManager(db_path=self.db_path)

    def tearDown(self) -> None:
        try:
            os.remove(self.db_path)
        except OSError:
            pass

    def test_upsert_inserts_then_updates(self):
        self.assertTrue(self.db.upsert_material_stock("M-001", "탄산칼슘", 100.0, 500.0))
        rows = self.db.get_all_material_stock()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["material_code"], "M-001")
        self.assertEqual(rows[0]["current_stock"], 100.0)

        # 같은 코드 → UPDATE (행 증가 없음)
        self.assertTrue(self.db.upsert_material_stock("M-001", "탄산칼슘", 250.0, 600.0))
        rows = self.db.get_all_material_stock()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["current_stock"], 250.0)
        self.assertEqual(rows[0]["min_stock_threshold"], 600.0)

    def test_upsert_clamps_negative_to_zero(self):
        self.db.upsert_material_stock("M-002", "이산화규소", -50.0, -10.0)
        rows = self.db.get_all_material_stock()
        self.assertEqual(rows[0]["current_stock"], 0.0)
        self.assertEqual(rows[0]["min_stock_threshold"], 0.0)

    def test_upsert_empty_code_falls_back_to_name(self):
        self.assertTrue(self.db.upsert_material_stock("", "무코드자재", 5.0, 10.0))
        rows = self.db.get_all_material_stock()
        self.assertEqual(rows[0]["material_code"], "무코드자재")

    def test_low_stock_uses_per_material_threshold(self):
        self.db.upsert_material_stock("A", "재고부족", 100.0, 500.0)   # 부족
        self.db.upsert_material_stock("B", "재고충분", 800.0, 500.0)   # 정상
        low = self.db.get_low_stock_materials(default_threshold=0.0)
        codes = [r["material_code"] for r in low]
        self.assertIn("A", codes)
        self.assertNotIn("B", codes)

    def test_low_stock_shortage_and_threshold_fields(self):
        self.db.upsert_material_stock("A", "재고부족", 120.0, 500.0)
        low = self.db.get_low_stock_materials(default_threshold=0.0)
        self.assertEqual(len(low), 1)
        item = low[0]
        self.assertEqual(item["threshold"], 500.0)
        self.assertEqual(item["current_stock"], 120.0)
        self.assertAlmostEqual(item["shortage"], 380.0)

    def test_low_stock_global_default_threshold(self):
        # 자재 임계값 0 → 전역 기본 임계값 적용
        self.db.upsert_material_stock("A", "임계값없음", 50.0, 0.0)
        # 기본 0이면 알림 제외
        self.assertEqual(self.db.get_low_stock_materials(0.0), [])
        # 기본 100이면 50<=100 → 알림
        low = self.db.get_low_stock_materials(100.0)
        self.assertEqual(len(low), 1)
        self.assertEqual(low[0]["threshold"], 100.0)
        self.assertAlmostEqual(low[0]["shortage"], 50.0)

    def test_low_stock_zero_threshold_excluded(self):
        # 자재 임계값 0 + 전역 0 → 알림 대상 없음
        self.db.upsert_material_stock("A", "비활성", 0.0, 0.0)
        self.assertEqual(self.db.get_low_stock_materials(0.0), [])

    def test_low_stock_sorted_by_shortage_desc(self):
        self.db.upsert_material_stock("A", "조금부족", 480.0, 500.0)   # 부족 20
        self.db.upsert_material_stock("B", "많이부족", 50.0, 500.0)    # 부족 450
        low = self.db.get_low_stock_materials(0.0)
        self.assertEqual(low[0]["material_code"], "B")
        self.assertEqual(low[1]["material_code"], "A")

    def test_seed_from_history(self):
        # mixing_records/details에 직접 삽입 후 시드 (save API 시그니처 비의존)
        with self.db.get_connection() as conn:
            conn.execute(
                "INSERT INTO mixing_records "
                "(product_lot, recipe_name, worker, work_date, work_time, total_amount, scale) "
                "VALUES (?,?,?,?,?,?,?)",
                ["LOT-1", "R1", "김작업", "2026-06-01", "09:00:00", 1000.0, "M-65"],
            )
            rec_id = conn.execute("SELECT id FROM mixing_records LIMIT 1").fetchone()[0]
            conn.execute(
                "INSERT INTO mixing_details "
                "(mixing_record_id, material_code, material_name, material_lot, "
                " ratio, theory_amount, actual_amount, sequence_order) "
                "VALUES (?,?,?,?,?,?,?,?)",
                [rec_id, "M-100", "원료A", "L1", 100.0, 1000.0, 1000.0, 1],
            )
            conn.commit()
        inserted = self.db.seed_material_stock_from_history()
        self.assertGreaterEqual(inserted, 1)
        codes = [r["material_code"] for r in self.db.get_all_material_stock()]
        self.assertIn("M-100", codes)


if __name__ == "__main__":
    unittest.main()
