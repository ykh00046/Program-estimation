"""
RecordDetailDialog의 순수-변환 헬퍼 단위 테스트.

PDCA #16 Part C — `save_changes` 분해로 추출된
`_collect_material_updates_from_rows` 의 회귀 안전망.
"""

import importlib
import os
import sys
import unittest


def _ensure_ui_dependencies() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    missing = []
    for name in ("PySide6", "pandas"):
        try:
            importlib.import_module(name)
        except ModuleNotFoundError:
            missing.append(name)
    if missing:
        raise unittest.SkipTest(
            f"RecordDetailDialog helper tests need: {', '.join(missing)}"
        )


_ensure_ui_dependencies()

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))
sys.path.insert(0, project_root)

from ui.record_view_dialog import RecordDetailDialog  # noqa: E402


class CollectMaterialUpdatesFromRowsTest(unittest.TestCase):
    """`_collect_material_updates_from_rows` (staticmethod) 검증."""

    def _row(self, code="M1", name="이름", lot="ML1", ratio="50", theory="50.0", actual="50.5"):
        # 컬럼 순서: [code, name, lot, ratio, theory, actual]
        return [code, name, lot, ratio, theory, actual]

    def test_basic_conversion(self):
        rows = [
            self._row("A1", "재료A", "LOT-A", "50", "50.0", "50.5"),
            self._row("B2", "재료B", "LOT-B", "30", "30.0", "29.7"),
            self._row("C3", "재료C", "LOT-C", "20", "20.0", "20.1"),
        ]
        result = RecordDetailDialog._collect_material_updates_from_rows(rows)
        self.assertEqual(len(result), 3)
        self.assertEqual(result[0], {
            'material_code': 'A1',
            'material_lot': 'LOT-A',
            'ratio': 50.0,
            'theory_amount': 50.0,
            'actual_amount': 50.5,
        })
        # 모든 수치 컬럼은 float 로 변환되어야 한다
        for item in result:
            self.assertIsInstance(item['ratio'], float)
            self.assertIsInstance(item['theory_amount'], float)
            self.assertIsInstance(item['actual_amount'], float)

    def test_empty_strings_become_zero(self):
        """ratio/theory/actual 이 ""인 경우 0.0 으로 변환."""
        rows = [self._row(ratio="", theory="", actual="")]
        result = RecordDetailDialog._collect_material_updates_from_rows(rows)
        self.assertEqual(result[0]['ratio'], 0.0)
        self.assertEqual(result[0]['theory_amount'], 0.0)
        self.assertEqual(result[0]['actual_amount'], 0.0)

    def test_empty_rows_returns_empty_list(self):
        self.assertEqual(
            RecordDetailDialog._collect_material_updates_from_rows([]),
            [],
        )

    def test_material_code_and_lot_passthrough(self):
        """name(컬럼1) 은 결과에 포함되지 않고, code(0)·lot(2) 만 사용."""
        rows = [self._row(code="X9", name="이건무시", lot="LOT-X9")]
        result = RecordDetailDialog._collect_material_updates_from_rows(rows)
        self.assertEqual(result[0]['material_code'], 'X9')
        self.assertEqual(result[0]['material_lot'], 'LOT-X9')
        self.assertNotIn('material_name', result[0])

    def test_invalid_number_raises_value_error(self):
        """save_changes 가 ValueError 분기로 처리하므로 헬퍼에서 그대로 전파."""
        rows = [self._row(ratio="abc")]
        with self.assertRaises(ValueError):
            RecordDetailDialog._collect_material_updates_from_rows(rows)


if __name__ == '__main__':
    unittest.main()
