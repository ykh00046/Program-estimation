"""RecordViewDialog 통합 스모크 (PDCA #23 §4.2).

offscreen Qt + mock data_manager로 다이얼로그 인스턴스화와 RecordOpsController
위임 경로를 검증한다(QMessageBox는 patch하여 모달 블록 방지).
"""
import importlib
import os
import sys
import unittest
from unittest.mock import MagicMock, patch


def _ensure_ui_test_dependencies() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    missing = []
    for name in ("PySide6", "qfluentwidgets", "pandas"):
        try:
            importlib.import_module(name)
        except ModuleNotFoundError:
            missing.append(name)
    if missing:
        raise unittest.SkipTest(f"requires GUI deps: {', '.join(missing)}")


_ensure_ui_test_dependencies()

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from PySide6.QtWidgets import QApplication

from ui.record_view_dialog import RecordViewDialog
from ui.record_ops_controller import RecordOpsController

app = QApplication.instance() or QApplication(sys.argv)


def _make_dm():
    dm = MagicMock()
    dm.get_mixing_records.return_value = []
    dm.get_all_material_names.return_value = []
    dm.export_existing_record.return_value = "/out.pdf"
    dm.delete_record.return_value = True
    return dm


class TestRecordViewDialogSmoke(unittest.TestCase):
    def test_constructs_and_wires_ops_controller(self):
        dlg = RecordViewDialog(_make_dm(), {"dpi": 250})
        self.assertIsInstance(dlg._ops, RecordOpsController)

    def test_export_and_delete_delegate_to_controller(self):
        dm = _make_dm()
        with patch("ui.record_view_dialog.QMessageBox") as MB:
            MB.Yes, MB.No = 1, 0
            MB.question.return_value = 1  # Yes (삭제 확인/폴더 질문)
            dlg = RecordViewDialog(dm, {"dpi": 250})
            dlg._open_output_folder = lambda: None
            dlg._get_checked_lots = lambda: ["A", "B"]
            dlg.chk_include_time_export.setChecked(True)
            dlg.export_selected_record()
            dlg.delete_selected_record()
        self.assertEqual(dm.export_existing_record.call_count, 2)
        self.assertEqual(dm.delete_record.call_count, 2)
        _, kw = dm.export_existing_record.call_args
        self.assertIs(kw.get("include_work_time"), True)

    def test_export_empty_selection_warns_without_calling_dm(self):
        dm = _make_dm()
        with patch("ui.record_view_dialog.QMessageBox") as MB:
            dlg = RecordViewDialog(dm, {"dpi": 250})
            dlg._get_checked_lots = lambda: []
            dlg.export_selected_record()
            dlg.delete_selected_record()
        dm.export_existing_record.assert_not_called()
        dm.delete_record.assert_not_called()


if __name__ == "__main__":
    unittest.main()
