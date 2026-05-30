"""RecordOpsController 단위 테스트 (PDCA #23). Qt 비의존, mock data_manager."""
import os
import sys
import unittest
from unittest.mock import MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from ui.record_ops_controller import RecordOpsController, BatchResult


class TestBatchResultDefaults(unittest.TestCase):
    def test_defaults(self):
        r = BatchResult(total=3)
        self.assertEqual((r.success_count, r.fail_count, r.failed_lots), (0, 0, []))


class TestExportRecords(unittest.TestCase):
    def _ctrl(self, side_effect):
        dm = MagicMock()
        dm.export_existing_record.side_effect = side_effect
        return RecordOpsController(dm), dm

    def test_all_success(self):
        ctrl, _ = self._ctrl(lambda lot, params, include_work_time=True: f"/out/{lot}.pdf")
        r = ctrl.export_records(["A", "B"], {"dpi": 250})
        self.assertEqual((r.total, r.success_count, r.fail_count), (2, 2, 0))
        self.assertEqual(r.failed_lots, [])

    def test_partial_failure(self):
        ctrl, _ = self._ctrl(lambda lot, params, include_work_time=True: None if lot == "B" else "/out.pdf")
        r = ctrl.export_records(["A", "B", "C"], {})
        self.assertEqual((r.success_count, r.fail_count), (2, 1))
        self.assertEqual(r.failed_lots, ["B"])

    def test_exception_is_absorbed_as_failure(self):
        def se(lot, params, include_work_time=True):
            if lot == "B":
                raise RuntimeError("boom")
            return "/out.pdf"
        ctrl, _ = self._ctrl(se)
        r = ctrl.export_records(["A", "B"], {})  # 예외 전파 안 함
        self.assertEqual((r.success_count, r.fail_count), (1, 1))
        self.assertEqual(r.failed_lots, ["B"])

    def test_passes_params_and_include_time(self):
        ctrl, dm = self._ctrl(lambda *a, **k: "/out.pdf")
        ctrl.export_records(["A"], {"dpi": 300}, include_work_time=False)
        dm.export_existing_record.assert_called_once_with("A", {"dpi": 300}, include_work_time=False)


class TestDeleteRecords(unittest.TestCase):
    def _ctrl(self, side_effect):
        dm = MagicMock()
        dm.delete_record.side_effect = side_effect
        return RecordOpsController(dm), dm

    def test_all_success(self):
        ctrl, _ = self._ctrl(lambda lot: True)
        r = ctrl.delete_records(["A", "B"])
        self.assertEqual((r.total, r.success_count, r.fail_count), (2, 2, 0))

    def test_partial_failure(self):
        ctrl, _ = self._ctrl(lambda lot: lot != "B")
        r = ctrl.delete_records(["A", "B"])
        self.assertEqual((r.success_count, r.fail_count), (1, 1))
        self.assertEqual(r.failed_lots, ["B"])

    def test_exception_is_absorbed_as_failure(self):
        def se(lot):
            if lot == "B":
                raise RuntimeError("boom")
            return True
        ctrl, _ = self._ctrl(se)
        r = ctrl.delete_records(["A", "B", "C"])
        self.assertEqual((r.success_count, r.fail_count), (2, 1))
        self.assertEqual(r.failed_lots, ["B"])


if __name__ == "__main__":
    unittest.main()
