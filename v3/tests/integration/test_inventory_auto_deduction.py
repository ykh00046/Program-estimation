"""배합 저장 시 자재 재고 자동 차감 오케스트레이션 테스트 (PDCA #29).

DataManager 는 GoogleSheets/Excel 등 무거운 의존이 있어 전체 생성 대신
``__new__`` 로 인스턴스만 만들고 db_manager 만 임시 DB로 주입해
``_deduct_inventory`` 와 설정 토글 경로를 격리 검증한다.
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
from models.data_manager import DataManager  # noqa: E402


class InventoryAutoDeductionTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self._legacy_patch = patch(
            "models.database.LEGACY_DB_PATH",
            os.path.join(self.tmpdir.name, "__nonexistent_legacy.db"),
        )
        self._legacy_patch.start()
        db_path = os.path.join(self.tmpdir.name, "test_mixing.db")
        self.db = MixingDatabaseManager(db_path=db_path)
        # DataManager 의 무거운 __init__ 우회, db_manager 만 주입
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

    def test_deduct_inventory_reduces_stock_when_enabled(self):
        self.db.upsert_material_stock("M1", "재료A", 100.0, 0.0)
        self.db.upsert_material_stock("M2", "재료B", 50.0, 0.0)
        details = [
            {"material_code": "M1", "material_name": "재료A", "actual_amount": 30.0},
            {"material_code": "M2", "material_name": "재료B", "actual_amount": 20.0},
        ]
        with patch("models.data_manager.config.get", return_value=True):
            self.dm._deduct_inventory(details)
        self.assertEqual(self._stock("M1"), 70.0)
        self.assertEqual(self._stock("M2"), 30.0)

    def test_toggle_off_skips_deduction(self):
        self.db.upsert_material_stock("M1", "재료A", 100.0, 0.0)
        details = [{"material_code": "M1", "material_name": "재료A", "actual_amount": 30.0}]
        with patch("models.data_manager.config.get", return_value=False):
            self.dm._deduct_inventory(details)
        self.assertEqual(self._stock("M1"), 100.0)  # 불변

    def test_blank_code_falls_back_to_material_name(self):
        # 마스터는 material_name 으로 키된 자재(코드 빈 값 → 이름 폴백, seed 규칙과 정합)
        self.db.upsert_material_stock("재료C", "재료C", 100.0, 0.0)
        details = [{"material_code": "", "material_name": "재료C", "actual_amount": 40.0}]
        with patch("models.data_manager.config.get", return_value=True):
            self.dm._deduct_inventory(details)
        self.assertEqual(self._stock("재료C"), 60.0)

    def test_deduction_failure_is_swallowed(self):
        # apply_consumption 이 예외를 던져도 _deduct_inventory 는 전파하지 않음(저장 우선)
        details = [{"material_code": "M1", "material_name": "재료A", "actual_amount": 10.0}]
        with patch("models.data_manager.config.get", return_value=True), \
                patch.object(self.db, "apply_consumption", side_effect=RuntimeError("boom")):
            try:
                self.dm._deduct_inventory(details)  # 예외 전파 없어야 함
            except Exception as e:  # noqa: BLE001
                self.fail(f"_deduct_inventory 가 예외를 전파함: {e}")

    def test_get_set_auto_deduct_toggle_roundtrip(self):
        store = {}
        with patch("models.data_manager.config.set_value",
                   side_effect=lambda k, v: store.__setitem__(k, v) or True), \
                patch("models.data_manager.config.get",
                      side_effect=lambda k, d=None: store.get(k, d)):
            self.assertTrue(self.dm.get_auto_deduct_on_save())  # 기본 True
            self.dm.set_auto_deduct_on_save(False)
            self.assertFalse(self.dm.get_auto_deduct_on_save())
            self.dm.set_auto_deduct_on_save(True)
            self.assertTrue(self.dm.get_auto_deduct_on_save())


if __name__ == "__main__":
    unittest.main()
