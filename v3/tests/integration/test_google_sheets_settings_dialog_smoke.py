"""Google Sheets 백업 대기 상태/수동 재시도 UI smoke tests (PDCA #41)."""
import os
import sys
import unittest
from unittest.mock import MagicMock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from PySide6.QtWidgets import QApplication

from ui.dialogs.admin_dialog import AdminDialog
from ui.dialogs.google_sheets_settings_dialog import GoogleSheetsSettingsDialog


_app = QApplication.instance() or QApplication([])


def _backup(pending=0):
    backup = MagicMock()
    backup.queue.count.return_value = pending
    return backup


class GoogleSheetsSettingsDialogSmokeTests(unittest.TestCase):

    def test_pending_count_controls_retry_button(self):
        dialog = GoogleSheetsSettingsDialog(backup=_backup(3))
        self.assertEqual(dialog.pending_label.text(), "전송 대기: 3건")
        self.assertTrue(dialog.retry_btn.isEnabled())

        dialog.backup.queue.count.return_value = 0
        dialog._refresh_queue_status()
        self.assertEqual(dialog.pending_label.text(), "전송 대기: 0건")
        self.assertFalse(dialog.retry_btn.isEnabled())

    @patch("ui.dialogs.google_sheets_settings_dialog.start_worker")
    def test_retry_delegates_empty_records_to_background_worker(self, worker):
        backup = _backup(2)
        dialog = GoogleSheetsSettingsDialog(backup=backup)

        dialog._retry_pending()

        args, kwargs = worker.call_args
        self.assertIs(args[0], dialog)
        self.assertIs(args[1], backup.backup_records)
        self.assertEqual(kwargs["args"], ([],))
        self.assertFalse(dialog.retry_btn.isEnabled())
        self.assertIn(dialog.button_box, kwargs["busy_widgets"])
        worker.return_value.finished.connect.assert_called_once_with(
            dialog._refresh_queue_status)

    @patch("ui.dialogs.google_sheets_settings_dialog.QMessageBox.information")
    def test_success_refreshes_queue_status(self, info):
        backup = _backup(0)
        dialog = GoogleSheetsSettingsDialog(backup=backup)
        dialog._on_retry_result((True, "2개의 기록을 백업했습니다."))
        self.assertEqual(dialog.pending_label.text(), "전송 대기: 0건")
        info.assert_called_once()

    @patch("ui.dialogs.google_sheets_settings_dialog.QMessageBox.warning")
    def test_failure_keeps_pending_count_visible(self, warning):
        backup = _backup(2)
        dialog = GoogleSheetsSettingsDialog(backup=backup)
        dialog._on_retry_result((False, "네트워크 오류"))
        self.assertEqual(dialog.pending_label.text(), "전송 대기: 2건")
        self.assertIn("전송 대기: 2건", warning.call_args.args[2])


class AdminBackupSettingsWiringTests(unittest.TestCase):

    @patch("ui.dialogs.admin_dialog.GoogleSheetsSettingsDialog")
    def test_admin_button_opens_backup_settings(self, dialog_cls):
        dialog_cls.return_value.exec.return_value = 0
        admin = AdminDialog()
        admin.google_sheets_btn.click()
        dialog_cls.assert_called_once_with(admin)
        dialog_cls.return_value.exec.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
