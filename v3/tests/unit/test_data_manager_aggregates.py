"""대시보드용 집계 쿼리 단위 테스트 (PDCA #17).

`DatabaseManager` 신규 메서드 4종 (get_monthly_production_stats,
get_top_materials, get_worker_stats, get_recipe_frequency) 회귀 안전망.
"""
import os
import sys
import tempfile
import unittest
from datetime import date, timedelta
from unittest.mock import patch


current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))
if project_root not in sys.path:
    sys.path.insert(0, project_root)


from models.database import DatabaseManager  # noqa: E402


def _make_record(
    db: DatabaseManager,
    *,
    product_lot: str,
    recipe_name: str,
    worker: str,
    work_date: str,
    total_amount: float,
    details,
) -> int:
    record_data = {
        "product_lot": product_lot,
        "recipe_name": recipe_name,
        "worker": worker,
        "work_date": work_date,
        "work_time": "09:00:00",
        "total_amount": total_amount,
        "scale": "S1",
    }
    return db.save_mixing_record(record_data, details)


def _detail(code: str, name: str, ratio: float, actual: float, order: int = 1):
    return {
        "material_code": code,
        "material_name": name,
        "material_lot": "L1",
        "ratio": ratio,
        "theory_amount": actual,
        "actual_amount": actual,
        "sequence_order": order,
    }


class AggregateQueryTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        # 레거시 DB 자동 마이그레이션이 운영 데이터를 임시 DB에 복사하는 것을 차단
        self._legacy_patch = patch(
            "models.database.LEGACY_DB_PATH",
            os.path.join(self.tmpdir.name, "__nonexistent_legacy.db"),
        )
        self._legacy_patch.start()
        db_path = os.path.join(self.tmpdir.name, "test_mixing.db")
        self.db = DatabaseManager(db_path=db_path)

    def tearDown(self):
        self._legacy_patch.stop()
        self.tmpdir.cleanup()

    # ------------------ 월별 ------------------

    def test_monthly_stats_empty_db_returns_empty_list(self):
        self.assertEqual(self.db.get_monthly_production_stats(months=6), [])

    def test_monthly_stats_invalid_months_returns_empty(self):
        self.assertEqual(self.db.get_monthly_production_stats(months=0), [])
        self.assertEqual(self.db.get_monthly_production_stats(months=-3), [])

    def test_monthly_stats_aggregates_within_range(self):
        today = date.today()
        _make_record(
            self.db,
            product_lot="L1",
            recipe_name="R1",
            worker="W1",
            work_date=today.isoformat(),
            total_amount=100.0,
            details=[_detail("M1", "재료A", 100, 100.0)],
        )
        rows = self.db.get_monthly_production_stats(months=1)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["year_month"], today.strftime("%Y-%m"))
        self.assertEqual(rows[0]["record_count"], 1)
        self.assertEqual(rows[0]["total_amount"], 100.0)

    # ------------------ 자재 TOP ------------------

    def test_top_materials_orders_desc_by_actual(self):
        today = date.today().isoformat()
        _make_record(
            self.db, product_lot="L1", recipe_name="R1", worker="W1",
            work_date=today, total_amount=300.0,
            details=[
                _detail("A", "재료A", 50, 150.0, 1),
                _detail("B", "재료B", 50, 50.0, 2),
            ],
        )
        _make_record(
            self.db, product_lot="L2", recipe_name="R1", worker="W1",
            work_date=today, total_amount=200.0,
            details=[_detail("B", "재료B", 100, 200.0, 1)],
        )
        rows = self.db.get_top_materials(limit=10)
        codes = [row["material_code"] for row in rows]
        self.assertEqual(codes, ["B", "A"])
        b_row = next(row for row in rows if row["material_code"] == "B")
        self.assertEqual(b_row["total_actual"], 250.0)
        self.assertEqual(b_row["use_count"], 2)

    def test_top_materials_respects_limit(self):
        today = date.today().isoformat()
        details = [
            _detail(f"M{i}", f"재료{i}", 10, float(i * 10), i)
            for i in range(1, 6)
        ]
        _make_record(
            self.db, product_lot="L1", recipe_name="R1", worker="W1",
            work_date=today, total_amount=150.0, details=details,
        )
        rows = self.db.get_top_materials(limit=2)
        self.assertEqual(len(rows), 2)

    def test_top_materials_date_filter_excludes_out_of_range(self):
        in_range = date.today().isoformat()
        out_range = (date.today() - timedelta(days=400)).isoformat()
        _make_record(
            self.db, product_lot="LIN", recipe_name="R1", worker="W1",
            work_date=in_range, total_amount=100.0,
            details=[_detail("INRANGE", "안쪽", 100, 100.0)],
        )
        _make_record(
            self.db, product_lot="LOUT", recipe_name="R1", worker="W1",
            work_date=out_range, total_amount=100.0,
            details=[_detail("OUTOFRANGE", "바깥", 100, 100.0)],
        )
        start = (date.today() - timedelta(days=30)).isoformat()
        rows = self.db.get_top_materials(limit=10, start_date=start)
        codes = {row["material_code"] for row in rows}
        self.assertIn("INRANGE", codes)
        self.assertNotIn("OUTOFRANGE", codes)

    # ------------------ 작업자 ------------------

    def test_worker_stats_avg_calculation(self):
        today = date.today().isoformat()
        _make_record(
            self.db, product_lot="LA", recipe_name="R1", worker="홍길동",
            work_date=today, total_amount=100.0,
            details=[_detail("M1", "재료", 100, 100.0)],
        )
        _make_record(
            self.db, product_lot="LB", recipe_name="R1", worker="홍길동",
            work_date=today, total_amount=200.0,
            details=[_detail("M1", "재료", 100, 200.0)],
        )
        rows = self.db.get_worker_stats()
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["worker"], "홍길동")
        self.assertEqual(row["record_count"], 2)
        self.assertEqual(row["total_amount"], 300.0)
        self.assertAlmostEqual(row["avg_amount"], 150.0)

    def test_worker_stats_orders_by_record_count_desc(self):
        today = date.today().isoformat()
        for i, worker in enumerate(["A", "B", "C"], start=1):
            for _ in range(i):
                _make_record(
                    self.db,
                    product_lot=f"L-{worker}-{_}",
                    recipe_name="R1",
                    worker=worker,
                    work_date=today,
                    total_amount=10.0,
                    details=[_detail("M1", "재료", 100, 10.0)],
                )
        rows = self.db.get_worker_stats()
        names = [row["worker"] for row in rows]
        self.assertEqual(names, ["C", "B", "A"])

    # ------------------ 레시피 빈도 ------------------

    def test_recipe_frequency_counts_and_limits(self):
        today = date.today().isoformat()
        for _ in range(3):
            _make_record(
                self.db,
                product_lot=f"LX-{_}",
                recipe_name="레시피X",
                worker="W1",
                work_date=today,
                total_amount=10.0,
                details=[_detail("M1", "재료", 100, 10.0)],
            )
        _make_record(
            self.db, product_lot="LY", recipe_name="레시피Y", worker="W1",
            work_date=today, total_amount=50.0,
            details=[_detail("M1", "재료", 100, 50.0)],
        )
        rows = self.db.get_recipe_frequency(limit=10)
        self.assertEqual(rows[0]["recipe_name"], "레시피X")
        self.assertEqual(rows[0]["run_count"], 3)
        self.assertEqual(rows[1]["recipe_name"], "레시피Y")

        limited = self.db.get_recipe_frequency(limit=1)
        self.assertEqual(len(limited), 1)


if __name__ == "__main__":
    unittest.main()
