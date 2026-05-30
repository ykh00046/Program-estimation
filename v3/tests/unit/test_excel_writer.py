"""ExcelWriter 단독 단위 테스트 (PDCA #22).

win32com/fitz 없이 Excel 작성 책임만 검증한다(실 template.xlsx + tempfile 격리).
"""
import importlib
import os
import sys
import tempfile
import unittest


def _ensure_dependencies() -> None:
    try:
        importlib.import_module("openpyxl")
    except ModuleNotFoundError:
        raise unittest.SkipTest("ExcelWriter tests require openpyxl")


_ensure_dependencies()

current_dir = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(current_dir))
sys.path.insert(0, PROJECT_ROOT)

from models.excel_writer import ExcelWriter

REAL_CELL_MAPPING = {
    "date": "A3", "scale": "A4", "worker": "C3", "work_time": "E3",
    "product_lot": "A6", "total_amount": "B6", "data_start_row": 6,
    "material_name_col": "C", "material_lot_col": "D", "ratio_col": "E",
    "theory_amount_col": "F", "actual_amount_col": "G",
}


def _make_data(product_lot="LOT-WRITER-01"):
    return {
        "product_lot": product_lot, "recipe_name": "TEST", "work_date": "2026-04-17",
        "work_time": "09:00:00", "worker": "tester", "total_amount": 500.0, "scale": "M-65",
        "materials": [
            {"material_name": "Mat1", "material_lot": "L1", "ratio": 40,
             "theory_amount": 200, "actual_amount": 199.5},
        ],
    }


class TestExcelWriter(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.template = os.path.join(PROJECT_ROOT, "resources", "template.xlsx")
        if not os.path.exists(cls.template):
            raise unittest.SkipTest(f"resources/template.xlsx not found: {cls.template}")

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.excel_folder = os.path.join(self._tmp.name, "excel")
        os.makedirs(self.excel_folder, exist_ok=True)

    def tearDown(self):
        self._tmp.cleanup()

    def test_creates_file_with_product_lot_name(self):
        writer = ExcelWriter(self.excel_folder, self.template, REAL_CELL_MAPPING)
        path = writer.export_to_excel(_make_data("LOT-WRITER-FILE"), include_work_time=True)
        self.assertIsNotNone(path)
        self.assertTrue(os.path.exists(path))
        self.assertTrue(path.endswith("LOT-WRITER-FILE.xlsx"))

    def test_returns_none_when_template_missing(self):
        missing = os.path.join(self._tmp.name, "nope.xlsx")
        writer = ExcelWriter(self.excel_folder, missing, REAL_CELL_MAPPING)
        self.assertIsNone(writer.export_to_excel(_make_data(), include_work_time=True))


if __name__ == "__main__":
    unittest.main()
