"""DataManager 백업 분리(auto_backup / backup_lot_to_sheets) 테스트 (PDCA #33)."""
import os
import sys
import unittest
from unittest.mock import MagicMock, patch

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))
sys.path.insert(0, project_root)

from models.data_manager import DataManager


def _materials_data():
    return {
        'MatA': {'품목코드': 'M1', '품목명': 'MatA', 'LOT': 'L1',
                 '배합비율': 50.0, '이론계량': 10.0, '실제배합': 10.0},
    }


class BackupSeparationTests(unittest.TestCase):

    def setUp(self):
        self.patcher_db = patch('models.data_manager.MixingDatabaseManager')
        self.db_manager_mock = self.patcher_db.start().return_value
        self.patcher_lot = patch('models.data_manager.LotManager')
        self.patcher_lot.start()
        self.patcher_pd = patch('pandas.read_excel')
        self.patcher_pd.start()
        self.patcher_exists = patch('os.path.exists', return_value=False)
        self.patcher_exists.start()

        self.dm = DataManager()
        # 백업 설정/백엔드를 mock으로 교체 (백업 활성 상태 시뮬레이션)
        self.dm.google_sheets_config = MagicMock()
        self.dm.google_sheets_config.is_backup_enabled.return_value = True
        self.dm.google_sheets_config.is_auto_backup_on_save.return_value = True
        self.dm.google_sheets_backup = MagicMock()
        self.dm.google_sheets_backup.backup_records.return_value = (True, "ok")

        self.db_manager_mock.get_mixing_records.return_value = []
        self.db_manager_mock.get_auto_deduct_on_save.return_value = False

    def tearDown(self):
        self.patcher_db.stop()
        self.patcher_lot.stop()
        self.patcher_pd.stop()
        self.patcher_exists.stop()

    def _save(self, **kwargs) -> str:
        return self.dm.save_record(
            worker_name="W", recipe_name="R", mixing_amount=20.0,
            materials_data=_materials_data(),
            work_date="2026-06-10", work_time="10:00:00", **kwargs)

    def test_save_record_default_backs_up_synchronously(self):
        """기본값(auto_backup=True)은 기존처럼 동기 백업 — 회귀 가드."""
        self._save()
        self.dm.google_sheets_backup.backup_records.assert_called_once()

    def test_save_record_auto_backup_false_skips_backup(self):
        self._save(auto_backup=False)
        self.dm.google_sheets_backup.backup_records.assert_not_called()

    def test_backup_lot_to_sheets_builds_payload_from_db(self):
        self.db_manager_mock.get_mixing_record_by_lot.return_value = {
            'id': 7, 'product_lot': 'LOTX', 'recipe_name': 'R', 'worker': 'W',
            'work_date': '2026-06-10', 'work_time': '10:00:00',
            'total_amount': 100.0, 'scale': 'S1',
        }
        self.db_manager_mock.get_mixing_details.return_value = [{
            'material_code': 'M1', 'material_name': 'MatA', 'material_lot': 'L1',
            'ratio': 50.0, 'theory_amount': 10.0, 'actual_amount': 10.0,
            'sequence_order': 1,
        }]
        success, msg = self.dm.backup_lot_to_sheets('LOTX')
        self.assertTrue(success)
        rows = self.dm.google_sheets_backup.backup_records.call_args[0][0]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['제품LOT'], 'LOTX')
        self.assertEqual(rows[0]['품목코드'], 'M1')
        self.assertEqual(rows[0]['실제량'], 10.0)

    def test_backup_lot_to_sheets_missing_record_fails(self):
        self.db_manager_mock.get_mixing_record_by_lot.return_value = None
        success, msg = self.dm.backup_lot_to_sheets('NOPE')
        self.assertFalse(success)
        self.dm.google_sheets_backup.backup_records.assert_not_called()

    def test_backup_lot_to_sheets_disabled_returns_false(self):
        self.dm.google_sheets_config.is_backup_enabled.return_value = False
        success, msg = self.dm.backup_lot_to_sheets('LOTX')
        self.assertFalse(success)
        self.dm.google_sheets_backup.backup_records.assert_not_called()


if __name__ == "__main__":
    unittest.main()
