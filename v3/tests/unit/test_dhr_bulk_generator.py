"""Unit tests for DhrBulkGenerator (PDCA #15 Part C-0).

Provides regression coverage for the long methods `generate` and
`_export_record` before they are decomposed in Part C-1/C-2.
"""
import os
import sys
import unittest
from unittest.mock import MagicMock, patch

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))
sys.path.insert(0, project_root)

from models.dhr_bulk_generator import DhrBulkGenerator


def _make_mock_lot_manager(lot_value="LOT001"):
    lm = MagicMock()
    lm.get_lot.return_value = [(lot_value, "2026-05-01")]
    return lm


def _make_mock_dhr_db():
    db = MagicMock()
    db.get_dhr_records.return_value = []
    db.generate_product_lot.return_value = "PROD-2026-001"
    return db


def _make_materials():
    return [
        {"code": "M001", "name": "Material1", "ratio": 50.0},
        {"code": "M002", "name": "Material2", "ratio": 50.0},
    ]


def _entry(date="2026-05-01", amount=1000.0):
    return {"date": date, "amount": amount}


def _generate(gen, entries, **overrides):
    """generate() wrapper supplying sensible defaults."""
    kwargs = dict(
        product_name="ProductA",
        materials=_make_materials(),
        worker="Worker1",
        include_time=False,
        scan_effects={},
        signature_options={},
        export=False,
    )
    kwargs.update(overrides)
    return gen.generate(entries=entries, **kwargs)


class TestDhrBulkGeneratorGenerate(unittest.TestCase):
    """T1~T5 — generate() orchestration."""

    def setUp(self):
        self.dhr_db = _make_mock_dhr_db()
        self.lot_manager = _make_mock_lot_manager()
        self.gen = DhrBulkGenerator(self.dhr_db, self.lot_manager)

    def test_t1_empty_entries_returns_zero(self):
        result = _generate(self.gen, [])
        self.assertEqual(result, 0)
        self.dhr_db.save_dhr_record.assert_not_called()

    def test_t2_single_entry_no_time_no_export(self):
        result = _generate(self.gen, [_entry()])
        self.assertEqual(result, 1)
        self.dhr_db.save_dhr_record.assert_called_once()
        record_data, details_data = self.dhr_db.save_dhr_record.call_args[0]
        self.assertEqual(record_data["work_time"], "")
        self.assertEqual(record_data["product_name"], "ProductA")
        self.assertEqual(len(details_data), 2)
        self.assertEqual(details_data[0]["material_lot"], "LOT001")

    @patch("models.dhr_bulk_generator.random.randint")
    def test_t3_single_entry_with_time_first_date(self, mock_randint):
        mock_randint.return_value = 30  # 09:30:00 base
        result = _generate(self.gen, [_entry()], include_time=True)
        self.assertEqual(result, 1)
        record_data, _ = self.dhr_db.save_dhr_record.call_args[0]
        self.assertEqual(record_data["work_time"], "09:30:00")

    @patch("models.dhr_bulk_generator.random.randint")
    def test_t4_same_date_two_entries_increment(self, mock_randint):
        mock_randint.side_effect = [30, 25]  # base 09:30 + 25min = 09:55
        result = _generate(
            self.gen,
            [_entry(amount=1000.0), _entry(amount=2000.0)],
            include_time=True,
        )
        self.assertEqual(result, 2)
        self.assertEqual(self.dhr_db.save_dhr_record.call_count, 2)
        first_record = self.dhr_db.save_dhr_record.call_args_list[0][0][0]
        second_record = self.dhr_db.save_dhr_record.call_args_list[1][0][0]
        self.assertEqual(first_record["work_time"], "09:30:00")
        self.assertEqual(second_record["work_time"], "09:55:00")

    def test_t5_missing_lot_raises_value_error(self):
        self.lot_manager.get_lot.return_value = []
        with self.assertRaises(ValueError) as ctx:
            _generate(self.gen, [_entry()])
        self.assertIn("M001", str(ctx.exception))
        self.dhr_db.save_dhr_record.assert_not_called()


class TestDhrBulkGeneratorExport(unittest.TestCase):
    """T6~T9 — _export_record() pipeline."""

    def setUp(self):
        self.dhr_db = _make_mock_dhr_db()
        self.lot_manager = _make_mock_lot_manager()
        self.gen = DhrBulkGenerator(self.dhr_db, self.lot_manager)

    @patch("models.image_processor.ImageProcessor")
    @patch("models.excel_exporter.ExcelExporter")
    def test_t6_export_success(self, MockExcelExporter, MockImageProcessor):
        mock_exporter = MockExcelExporter.return_value
        mock_exporter.export_to_excel.return_value = "/path/excel.xlsx"
        mock_exporter.export_to_pdf.return_value = "/path/file.pdf"
        MockImageProcessor.return_value.create_signed_image.return_value = (False, "skip")
        _generate(self.gen, [_entry()], export=True)
        self.assertEqual(self.gen.last_export_failures, [])
        mock_exporter.export_to_excel.assert_called_once()
        mock_exporter.export_to_pdf.assert_called_once()

    @patch("models.image_processor.ImageProcessor")
    @patch("models.excel_exporter.ExcelExporter")
    def test_t7_export_excel_failure(self, MockExcelExporter, MockImageProcessor):
        mock_exporter = MockExcelExporter.return_value
        mock_exporter.export_to_excel.return_value = None  # excel fail
        MockImageProcessor.return_value.create_signed_image.return_value = (False, "")
        _generate(self.gen, [_entry()], export=True)
        self.assertEqual(len(self.gen.last_export_failures), 1)
        self.assertIn("Excel export failed", self.gen.last_export_failures[0])

    @patch("models.image_processor.ImageProcessor")
    @patch("models.excel_exporter.ExcelExporter")
    def test_t8_export_pdf_failure(self, MockExcelExporter, MockImageProcessor):
        mock_exporter = MockExcelExporter.return_value
        mock_exporter.export_to_excel.return_value = "/path/excel.xlsx"
        mock_exporter.export_to_pdf.return_value = None  # pdf fail
        MockImageProcessor.return_value.create_signed_image.return_value = (False, "")
        _generate(self.gen, [_entry()], export=True)
        self.assertEqual(len(self.gen.last_export_failures), 1)
        self.assertIn("PDF export failed", self.gen.last_export_failures[0])

    @patch("os.remove")
    @patch("os.path.exists")
    @patch("models.image_processor.ImageProcessor")
    @patch("models.excel_exporter.ExcelExporter")
    def test_t9_export_cleans_signed_image(
        self, MockExcelExporter, MockImageProcessor, mock_exists, mock_remove
    ):
        mock_exporter = MockExcelExporter.return_value
        mock_exporter.export_to_excel.return_value = "/path/excel.xlsx"
        mock_exporter.export_to_pdf.return_value = "/path/file.pdf"
        mock_exists.return_value = True  # base + signed both exist
        MockImageProcessor.return_value.create_signed_image.return_value = (True, "ok")
        _generate(self.gen, [_entry()], export=True)
        self.assertEqual(self.gen.last_export_failures, [])
        mock_remove.assert_called()


if __name__ == "__main__":
    unittest.main()
