"""RecordDetailDialog 복구 스모크 (PDCA #24).

복사-붙여넣기 잔재로 생성 시 크래시(AttributeError: load_records)하던 상세
다이얼로그가 기본정보+자재상세+수정/저장 바로 정상 렌더되는지 검증.
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

import pandas as pd
from PySide6.QtWidgets import QApplication

from ui.record_view_dialog import RecordDetailDialog

app = QApplication.instance() or QApplication(sys.argv)

DETAIL_HEADERS = ["품목코드", "품목명", "자재LOT", "배합비율(%)", "이론계량(g)", "실제배합(g)"]


def _make_df():
    return pd.DataFrame([{
        "product_lot": "L1", "worker": "w", "recipe_name": "R", "total_amount": 100,
        "work_date": "2026-05-31", "work_time": "09:00:00",
        "material_code": "C1", "material_name": "M1", "material_lot": "ML1",
        "ratio": 100, "theory_amount": 100, "actual_amount": 100,
    }])


class TestRecordDetailDialogSmoke(unittest.TestCase):
    def test_constructs_without_crash(self):
        d = RecordDetailDialog(_make_df(), MagicMock(), {"dpi": 250})
        self.assertFalse(d.edit_mode)
        for attr in ("worker_edit", "amount_edit", "table"):
            self.assertTrue(hasattr(d, attr), attr)

    def test_detail_table_columns(self):
        d = RecordDetailDialog(_make_df(), MagicMock(), {"dpi": 250})
        headers = [d.table.horizontalHeaderItem(i).text() for i in range(d.table.columnCount())]
        self.assertEqual(headers, DETAIL_HEADERS)

    def test_single_button_bar_definition(self):
        import inspect
        src = inspect.getsource(RecordDetailDialog)
        self.assertEqual(src.count("def _build_button_bar"), 1)

    def test_button_bar_is_detail_variant(self):
        from PySide6.QtWidgets import QAbstractButton
        d = RecordDetailDialog(_make_df(), MagicMock(), {"dpi": 250})
        texts = {b.text() for b in d.findChildren(QAbstractButton)}
        # 상세용 버튼 구성, 목록용(전체 선택/삭제) 부재
        self.assertTrue({"수정 모드", "저장", "실적서 출력", "닫기"} <= texts, texts)
        self.assertNotIn("전체 선택", texts)
        self.assertNotIn("삭제", texts)

    def test_toggle_edit_mode_no_crash(self):
        d = RecordDetailDialog(_make_df(), MagicMock(), {"dpi": 250})
        with patch("ui.record_view_dialog.QMessageBox"):
            d.toggle_edit_mode()
        self.assertTrue(d.edit_mode)
        self.assertFalse(d.worker_edit.isReadOnly())


if __name__ == "__main__":
    unittest.main()
