"""RecipeEditDialog 스모크 (PDCA #37). offscreen Qt + mock dm + QMessageBox patch."""
import importlib
import os
import sys
import unittest
from unittest.mock import MagicMock, patch


def _ensure_ui_test_dependencies() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    missing = []
    for name in ("PySide6", "qfluentwidgets"):
        try:
            importlib.import_module(name)
        except ModuleNotFoundError:
            missing.append(name)
    if missing:
        raise unittest.SkipTest(f"requires GUI deps: {', '.join(missing)}")


_ensure_ui_test_dependencies()

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from PySide6.QtWidgets import QApplication

from ui.dialogs.recipe_edit_dialog import RecipeEditDialog

app = QApplication.instance() or QApplication(sys.argv)

_ITEMS = [
    {"품목코드": "M1", "품목명": "Mat1", "배합비율": 40.0, "순서": 1},
    {"품목코드": "M2", "품목명": "Mat2", "배합비율": 60.0, "순서": 2},
]


def _make_dm(names=("R1", "R2"), items=_ITEMS):
    dm = MagicMock()
    dm.get_recipe_names.return_value = list(names)
    dm.get_recipe_items.return_value = list(items)
    dm.deactivate_recipe.return_value = True
    dm.seed_recipes_from_excel.return_value = 2
    return dm


class RecipeEditDialogSmokeTests(unittest.TestCase):

    @staticmethod
    def _edit_name(dlg, value="changed"):
        dlg.name_edit.setText(value)

    def test_empty_list_no_crash(self):
        dlg = RecipeEditDialog(_make_dm(names=()))
        self.assertEqual(dlg.recipe_list.count(), 0)

    def test_loads_names_and_selection_fills_form(self):
        dlg = RecipeEditDialog(_make_dm())
        self.assertEqual(dlg.recipe_list.count(), 2)
        dlg.recipe_list.setCurrentRow(0)
        self.assertEqual(dlg.name_edit.text(), "R1")
        self.assertEqual(dlg.table.rowCount(), 2)
        self.assertEqual(dlg.table.item(0, 0).text(), "M1")
        self.assertIn("100", dlg.ratio_sum_label.text())

    def test_save_delegates_with_collected_materials(self):
        dm = _make_dm()
        with patch("ui.dialogs.recipe_edit_dialog.QMessageBox") as MB:
            dlg = RecipeEditDialog(dm)
            dlg.recipe_list.setCurrentRow(0)
            dlg._on_save()
        name, materials = dm.save_recipe.call_args[0]
        self.assertEqual(name, "R1")
        self.assertEqual([m["품목코드"] for m in materials], ["M1", "M2"])
        MB.information.assert_called_once()

    def test_save_ratio_not_100_asks_confirmation(self):
        dm = _make_dm(items=[{"품목코드": "M1", "품목명": "A", "배합비율": 80.0, "순서": 1}])
        with patch("ui.dialogs.recipe_edit_dialog.QMessageBox") as MB:
            MB.Yes, MB.No = 1, 0
            MB.question.return_value = 0  # No → 저장 취소
            dlg = RecipeEditDialog(dm)
            dlg.recipe_list.setCurrentRow(0)
            dlg._on_save()
        MB.question.assert_called_once()
        dm.save_recipe.assert_not_called()

    def test_save_without_name_warns(self):
        dm = _make_dm()
        with patch("ui.dialogs.recipe_edit_dialog.QMessageBox") as MB:
            dlg = RecipeEditDialog(dm)
            dlg._on_new_recipe()
            dlg._on_save()
        MB.warning.assert_called_once()
        dm.save_recipe.assert_not_called()

    def test_delete_confirmed_delegates(self):
        dm = _make_dm()
        with patch("ui.dialogs.recipe_edit_dialog.QMessageBox") as MB:
            MB.Yes, MB.No = 1, 0
            MB.question.return_value = 1
            dlg = RecipeEditDialog(dm)
            dlg.recipe_list.setCurrentRow(0)
            dlg._on_delete()
        dm.deactivate_recipe.assert_called_once_with("R1")

    def test_import_excel_confirmed_delegates(self):
        dm = _make_dm()
        with patch("ui.dialogs.recipe_edit_dialog.QMessageBox") as MB:
            MB.Yes, MB.No = 1, 0
            MB.question.return_value = 1
            dlg = RecipeEditDialog(dm)
            dlg._on_import_excel()
        dm.seed_recipes_from_excel.assert_called_once()

    def test_import_excel_declined_does_nothing(self):
        dm = _make_dm()
        with patch("ui.dialogs.recipe_edit_dialog.QMessageBox") as MB:
            MB.Yes, MB.No = 1, 0
            MB.question.return_value = 0
            dlg = RecipeEditDialog(dm)
            dlg._on_import_excel()
        dm.seed_recipes_from_excel.assert_not_called()

    def test_recipe_switch_cancel_preserves_current_edits_and_selection(self):
        dm = _make_dm()
        with patch("ui.dialogs.recipe_edit_dialog.QMessageBox") as MB:
            MB.Discard, MB.Cancel = 1, 0
            MB.question.return_value = MB.Cancel
            dlg = RecipeEditDialog(dm)
            dlg.recipe_list.setCurrentRow(0)
            self._edit_name(dlg)
            dlg.recipe_list.setCurrentRow(1)
        self.assertEqual(dlg.recipe_list.currentItem().text(), "R1")
        self.assertEqual(dlg.name_edit.text(), "changed")

    def test_recipe_switch_discard_loads_new_selection(self):
        dm = _make_dm()
        with patch("ui.dialogs.recipe_edit_dialog.QMessageBox") as MB:
            MB.Discard, MB.Cancel = 1, 0
            MB.question.return_value = MB.Discard
            dlg = RecipeEditDialog(dm)
            dlg.recipe_list.setCurrentRow(0)
            self._edit_name(dlg)
            dlg.recipe_list.setCurrentRow(1)
        self.assertEqual(dlg.recipe_list.currentItem().text(), "R2")
        self.assertEqual(dlg.name_edit.text(), "R2")

    def test_new_recipe_cancel_preserves_edits(self):
        dm = _make_dm()
        with patch("ui.dialogs.recipe_edit_dialog.QMessageBox") as MB:
            MB.Discard, MB.Cancel = 1, 0
            MB.question.return_value = MB.Cancel
            dlg = RecipeEditDialog(dm)
            dlg.recipe_list.setCurrentRow(0)
            self._edit_name(dlg)
            dlg._on_new_recipe()
        self.assertEqual(dlg.name_edit.text(), "changed")

    def test_reject_cancel_keeps_dialog_open(self):
        dm = _make_dm()
        with patch("ui.dialogs.recipe_edit_dialog.QMessageBox") as MB:
            MB.Discard, MB.Cancel = 1, 0
            MB.question.return_value = MB.Cancel
            dlg = RecipeEditDialog(dm)
            dlg.recipe_list.setCurrentRow(0)
            self._edit_name(dlg)
            with patch.object(RecipeEditDialog.__mro__[1], "reject") as base_reject:
                dlg.reject()
        base_reject.assert_not_called()

    def test_saved_form_is_clean(self):
        dm = _make_dm()
        with patch("ui.dialogs.recipe_edit_dialog.QMessageBox") as MB:
            dlg = RecipeEditDialog(dm)
            dlg.recipe_list.setCurrentRow(0)
            dlg._on_save()
            self.assertFalse(dlg._has_unsaved_changes())


if __name__ == "__main__":
    unittest.main()
