
import unittest
from unittest.mock import MagicMock, patch
import os
import sys

# Ensure project root is in path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))
sys.path.insert(0, project_root)

from models.data_manager import DataManager

class TestDataManager(unittest.TestCase):

    def setUp(self):
        # Mock MixingDatabaseManager
        self.patcher_db = patch('models.data_manager.MixingDatabaseManager')
        self.MockDatabaseManager = self.patcher_db.start()
        self.db_manager_mock = self.MockDatabaseManager.return_value

        # Mock LotManager
        self.patcher_lot = patch('models.data_manager.LotManager')
        self.MockLotManager = self.patcher_lot.start()
        self.lot_manager_mock = self.MockLotManager.return_value
        
        # Mock pandas read_excel for _load_recipes_from_excel
        self.patcher_pd = patch('pandas.read_excel')
        self.mock_read_excel = self.patcher_pd.start()

        # Mock os.path.exists to simulate RECIPE_FILE existing
        self.patcher_exists = patch('os.path.exists')
        self.mock_exists = self.patcher_exists.start()
        self.mock_exists.return_value = True

        # PDCA #37: 레시피 SSOT = DB. 기본은 빈 DB(시드 경로, Excel mock은 빈 df)
        self.db_manager_mock.get_recipes.return_value = {}

    def tearDown(self):
        self.patcher_db.stop()
        self.patcher_lot.stop()
        self.patcher_pd.stop()
        self.patcher_exists.stop()

    def test_load_recipes_seeds_db_from_excel_when_empty(self):
        """빈 DB → Excel 시드 → DB 재조회가 SSOT (PDCA #37 마이그레이션 경로)."""
        # Setup mock dataframe (Excel 시드 소스)
        mock_df = MagicMock()
        mock_df.iterrows.return_value = [
            (0, {'레시피': 'RecipeA', '품목코드': 'M001', '품목명': 'Material1', '배합비율': 50.0}),
            (1, {'레시피': 'RecipeA', '품목코드': 'M002', '품목명': 'Material2', '배합비율': 50.0}),
            (2, {'레시피': 'RecipeB', '품목코드': 'M003', '품목명': 'Material3', '배합비율': 100.0}),
        ]
        self.mock_read_excel.return_value = mock_df

        seeded_db = {
            'RecipeA': [{'품목코드': 'M001', '품목명': 'Material1', '배합비율': 50.0, '순서': 1},
                        {'품목코드': 'M002', '품목명': 'Material2', '배합비율': 50.0, '순서': 2}],
            'RecipeB': [{'품목코드': 'M003', '품목명': 'Material3', '배합비율': 100.0, '순서': 1}],
        }
        # 1차 조회 = 빈 DB(시드 트리거), 2차 조회 = 시드 결과
        self.db_manager_mock.get_recipes.side_effect = [{}, seeded_db]

        dm = DataManager()

        # Excel 레시피가 DB로 시드됨
        self.assertEqual(self.db_manager_mock.save_recipe.call_count, 2)
        seeded_names = [c[0][0] for c in self.db_manager_mock.save_recipe.call_args_list]
        self.assertEqual(sorted(seeded_names), ['RecipeA', 'RecipeB'])
        # 런타임 진실은 DB 재조회 결과
        self.assertIn('RecipeA', dm.recipes)
        self.assertEqual(len(dm.recipes['RecipeA']), 2)
        self.assertEqual(dm.recipes['RecipeA'][0]['품목코드'], 'M001')

    def test_load_recipes_uses_db_without_excel_when_populated(self):
        """DB에 레시피가 있으면 Excel을 읽지 않는다 (DB = SSOT)."""
        self.db_manager_mock.get_recipes.return_value = {
            'FromDB': [{'품목코드': 'M9', '품목명': 'X', '배합비율': 100.0, '순서': 1}],
        }
        dm = DataManager()
        self.db_manager_mock.save_recipe.assert_not_called()
        self.assertEqual(dm.get_recipe_names(), ['FromDB'])

    def test_generate_product_lot_first_of_day(self):
        """Test LOT generation for the first record of the day"""
        dm = DataManager()
        
        # Mock DB returning no records for the day
        self.db_manager_mock.get_mixing_records.return_value = []
        
        recipe_name = "TestRecipe"
        work_date = "2023-10-27"
        
        # Expected: RecipeName + YYMMDD + 01
        expected_lot = "TestRecipe23102701"
        
        lot = dm.generate_product_lot(recipe_name, work_date)
        self.assertEqual(lot, expected_lot)

    def test_generate_product_lot_increment(self):
        """Test LOT generation increments correctly"""
        dm = DataManager()
        
        # Mock DB returning existing records
        self.db_manager_mock.get_mixing_records.return_value = [
            {'product_lot': 'TestRecipe23102701'},
            {'product_lot': 'TestRecipe23102702'},
        ]
        
        recipe_name = "TestRecipe"
        work_date = "2023-10-27"
        
        # Expected: 03
        expected_lot = "TestRecipe23102703"
        
        lot = dm.generate_product_lot(recipe_name, work_date)
        self.assertEqual(lot, expected_lot)

    def test_validate_record_inputs_success(self):
        """Test record input validation success"""
        dm = DataManager()
        materials = {
            "M001": {"LOT": "LOT-001", "실제배합": 5.0}
        }
        ok, msg = dm.validate_record_inputs("Worker", "Recipe", 10.0, materials)
        self.assertTrue(ok)
        self.assertEqual(msg, "")

    def test_validate_record_inputs_missing_worker(self):
        """Test record input validation missing worker"""
        dm = DataManager()
        materials = {
            "M001": {"LOT": "LOT-001"}
        }
        ok, msg = dm.validate_record_inputs("", "Recipe", 10.0, materials)
        self.assertFalse(ok)
        self.assertIn("\uc791\uc5c5\uc790", msg)  # 작업자

    def test_validate_record_inputs_missing_lot(self):
        """Test record input validation missing material lot"""
        dm = DataManager()
        materials = {
            "M001": {"LOT": ""}
        }
        ok, msg = dm.validate_record_inputs("Worker", "Recipe", 10.0, materials)
        self.assertFalse(ok)
        self.assertIn("LOT", msg)

if __name__ == '__main__':
    unittest.main()
