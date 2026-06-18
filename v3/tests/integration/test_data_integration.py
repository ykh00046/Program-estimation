
import unittest
import os
import sys
import shutil
import tempfile
from datetime import datetime

# Ensure project root is in path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))
sys.path.insert(0, project_root)

from models.data_manager import DataManager
from models.database import MixingDatabaseManager

class TestDataIntegration(unittest.TestCase):

    def setUp(self):
        # Create a temporary directory for the test DB
        self.test_dir = tempfile.mkdtemp()
        self.test_db_path = os.path.join(self.test_dir, 'test_mixing.db')

        # Initialize DataManager with test DB
        # DataManager creates MixingDatabaseManager internally, so we patch its __init__
        # to inject a MixingDatabaseManager pointed at the test_db_path.
        self._original_init = DataManager.__init__

        def test_init(instance):
            instance.db_manager = MixingDatabaseManager(self.test_db_path)
            from models.lot_manager import LotManager
            instance.lot_manager = LotManager(os.path.join(self.test_dir, 'lots.xlsx'))
            instance.recipes = {}
            # Stub Google Sheets backup to avoid external dependencies
            instance.google_sheets_config = type('Stub', (), {
                'is_backup_enabled': lambda self: False,
                'is_auto_backup_on_save': lambda self: False,
            })()
            instance.google_sheets_backup = None
            
        DataManager.__init__ = test_init
        self.dm = DataManager()

    def tearDown(self):
        # Restore original init
        DataManager.__init__ = self._original_init
        
        # Cleanup temp dir
        shutil.rmtree(self.test_dir)

    def test_save_and_retrieve_record(self):
        """Test saving a full record and retrieving it from DB"""
        worker = "Tester"
        recipe = "TestRecipe"
        today = datetime.now().strftime("%Y-%m-%d")
        amount = 100.0
        
        materials = {
            "Material A": {"품목코드": "M001", "LOT": "L1", "배합비율": 50.0, "실제배합": 50.0},
            "Material B": {"품목코드": "M002", "LOT": "L2", "배합비율": 50.0, "실제배합": 50.0}
        }
        
        # Save
        lot = self.dm.save_record(worker, recipe, amount, materials, today, "12:00:00")
        
        # Retrieve
        record = self.dm.db_manager.get_mixing_record_by_lot(lot)
        self.assertIsNotNone(record)
        self.assertEqual(record['worker'], worker)
        self.assertEqual(record['total_amount'], amount)
        
        # Check details
        details = self.dm.db_manager.get_mixing_details(record['id'])
        self.assertEqual(len(details), 2)
        self.assertEqual(details[0]['material_name'], "Material A")

    def test_delete_record(self):
        """Test deleting a record"""
        # Create a record first
        lot = self.dm.save_record("User", "Recipe", 10.0, {}, "2023-01-01", "09:00:00")
        
        # Delete
        success = self.dm.delete_record(lot)
        self.assertTrue(success)
        
        # Verify gone
        record = self.dm.db_manager.get_mixing_record_by_lot(lot)
        self.assertIsNone(record)

if __name__ == '__main__':
    unittest.main()
