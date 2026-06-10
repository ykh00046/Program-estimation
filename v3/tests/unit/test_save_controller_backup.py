"""SaveController 백업 위임(backup_runner) 테스트 (PDCA #33). Qt 비의존."""
import os
import sys
import unittest
from unittest.mock import MagicMock

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))
sys.path.insert(0, project_root)

from ui.controllers import SaveController


def _make_controller(backup_runner=None):
    dm = MagicMock()
    dm.save_record.return_value = "LOT1"
    work_info_panel = MagicMock()
    work_info_panel.get_data.return_value = {
        "worker_name": "W", "work_date": "2026-06-10",
        "work_time": "10:00:00", "include_time": True,
    }
    on_success = MagicMock()
    controller = SaveController(
        data_manager=dm,
        recipe_panel=MagicMock(),
        work_info_panel=work_info_panel,
        material_panel=MagicMock(),
        signature_panel=MagicMock(),
        scan_effects_panel=MagicMock(),
        validate_inputs=lambda: (True, ""),
        on_validation_error=MagicMock(),
        on_success=on_success,
        backup_runner=backup_runner,
    )
    return controller, dm, on_success


class SaveControllerBackupTests(unittest.TestCase):

    def test_without_runner_uses_sync_backup(self):
        """backup_runner 미주입 시 기존 동작 — auto_backup=True (회귀 가드)."""
        controller, dm, on_success = _make_controller()
        controller.save_record()
        self.assertIs(dm.save_record.call_args.kwargs.get("auto_backup"), True)
        on_success.assert_called_once_with("LOT1")

    def test_with_runner_defers_backup_to_runner(self):
        runner = MagicMock()
        controller, dm, on_success = _make_controller(backup_runner=runner)
        controller.save_record()
        self.assertIs(dm.save_record.call_args.kwargs.get("auto_backup"), False)
        on_success.assert_called_once_with("LOT1")
        runner.assert_called_once_with("LOT1")

    def test_validation_failure_skips_save_and_runner(self):
        runner = MagicMock()
        controller, dm, _ = _make_controller(backup_runner=runner)
        controller.validate_inputs = lambda: (False, "에러")
        controller.on_validation_error = MagicMock()
        controller.save_record()
        dm.save_record.assert_not_called()
        runner.assert_not_called()
        controller.on_validation_error.assert_called_once_with("에러")


if __name__ == "__main__":
    unittest.main()
