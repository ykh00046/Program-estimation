"""배합 레시피 SSOT 일원화 단위 테스트 (PDCA #37).

임시 DB + LEGACY_DB_PATH 패치 (#27/#30 테스트 패턴 준수).
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


def _mat(code, name, ratio):
    return {"품목코드": code, "품목명": name, "배합비율": ratio}


class _TmpDbTestCase(unittest.TestCase):

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


class RecipeRepositoryTests(_TmpDbTestCase):

    def test_get_recipes_includes_sequence_key_in_order(self):
        """'순서' 키 노출 + sequence_order 순서 보존 (UI load_items 호환)."""
        self.db.save_recipe("R1", [_mat("M1", "A", 40.0), _mat("M2", "B", 60.0)])
        items = self.db.get_recipes()["R1"]
        self.assertEqual([m["순서"] for m in items], [1, 2])
        self.assertEqual([m["품목코드"] for m in items], ["M1", "M2"])

    def test_material_shrink_leaves_no_ghosts(self):
        """자재 축소 재저장 시 빠진 자재가 조회에 남지 않음 (Plan 리스크 1 고정)."""
        self.db.save_recipe("R1", [_mat("M1", "A", 30.0), _mat("M2", "B", 30.0),
                                   _mat("M3", "C", 40.0)])
        self.db.save_recipe("R1", [_mat("M1", "A", 50.0), _mat("M2", "B", 50.0)])
        items = self.db.get_recipes()["R1"]
        self.assertEqual([m["품목코드"] for m in items], ["M1", "M2"])

    def test_removed_material_revives_on_readd(self):
        self.db.save_recipe("R1", [_mat("M1", "A", 50.0), _mat("M2", "B", 50.0)])
        self.db.save_recipe("R1", [_mat("M1", "A", 100.0)])
        self.db.save_recipe("R1", [_mat("M1", "A", 50.0), _mat("M2", "B", 50.0)])
        items = self.db.get_recipes()["R1"]
        self.assertEqual([m["품목코드"] for m in items], ["M1", "M2"])

    def test_deactivate_removes_from_listing(self):
        self.db.save_recipe("R1", [_mat("M1", "A", 100.0)])
        self.db.save_recipe("R2", [_mat("M2", "B", 100.0)])
        self.assertTrue(self.db.deactivate_recipe("R1"))
        recipes = self.db.get_recipes()
        self.assertNotIn("R1", recipes)
        self.assertIn("R2", recipes)

    def test_deactivate_unknown_or_twice_returns_false(self):
        self.assertFalse(self.db.deactivate_recipe("NOPE"))
        self.db.save_recipe("R1", [_mat("M1", "A", 100.0)])
        self.assertTrue(self.db.deactivate_recipe("R1"))
        self.assertFalse(self.db.deactivate_recipe("R1"))  # 이미 비활성


class DataManagerSeedTests(_TmpDbTestCase):
    """load_recipes의 시드 분기 (DataManager.__new__ + 실제 tmp Facade, #29 패턴)."""

    _EXCEL = {
        "RecipeA": [_mat("M1", "Mat1", 50.0), _mat("M2", "Mat2", 50.0)],
        "RecipeB": [_mat("M3", "Mat3", 100.0)],
    }

    def _make_dm(self, excel_recipes):
        from models.data_manager import DataManager
        dm = DataManager.__new__(DataManager)
        dm.db_manager = self.db
        dm.recipes = {}
        dm._load_recipes_from_excel = lambda: dict(excel_recipes)
        return dm

    def test_empty_table_seeds_from_excel_then_reads_db(self):
        dm = self._make_dm(self._EXCEL)
        dm.load_recipes()
        self.assertEqual(sorted(dm.get_recipe_names()), ["RecipeA", "RecipeB"])
        self.assertEqual(len(dm.get_recipe_items("RecipeA")), 2)
        # DB에 실제로 영속화됨
        self.assertIn("RecipeA", self.db.get_recipes())

    def test_nonempty_table_skips_excel(self):
        self.db.save_recipe("FromDB", [_mat("M9", "X", 100.0)])
        called = []
        dm = self._make_dm({})
        dm._load_recipes_from_excel = lambda: called.append(1) or {}
        dm.load_recipes()
        self.assertEqual(called, [])  # Excel 로더 미호출 — DB가 SSOT
        self.assertEqual(dm.get_recipe_names(), ["FromDB"])

    def test_explicit_seed_overwrites_by_name(self):
        """명시적 가져오기(다이얼로그 버튼)는 기존 DB 레시피를 이름 기준 덮어씀."""
        self.db.save_recipe("RecipeA", [_mat("OLD", "Old", 100.0)])
        dm = self._make_dm(self._EXCEL)
        imported = dm.seed_recipes_from_excel()
        self.assertEqual(imported, 2)
        items = self.db.get_recipes()["RecipeA"]
        self.assertEqual([m["품목코드"] for m in items], ["M1", "M2"])

    def test_save_and_deactivate_delegations(self):
        dm = self._make_dm({})
        dm.save_recipe("R1", [_mat("M1", "A", 100.0)])
        dm.load_recipes()
        self.assertEqual(dm.get_recipe_names(), ["R1"])
        self.assertTrue(dm.deactivate_recipe("R1"))
        dm.load_recipes()
        self.assertEqual(dm.get_recipe_names(), [])


if __name__ == "__main__":
    unittest.main()
