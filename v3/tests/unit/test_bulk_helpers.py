import os
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch


current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))
sys.path.insert(0, project_root)

from utils.bulk_helpers import get_materials_from_table
from models.dhr_database import DhrDatabaseManager


class FakeItem:
    def __init__(self, value: str):
        self._value = value

    def text(self) -> str:
        return self._value


class FakeTable:
    def __init__(self, rows):
        self._rows = rows

    def rowCount(self) -> int:
        return len(self._rows)

    def item(self, row: int, col: int):
        value = self._rows[row][col]
        if value is None:
            return None
        return FakeItem(value)


class TestBulkHelpers(unittest.TestCase):
    def test_get_materials_from_table_requires_ratio(self):
        table = FakeTable([["M001", "원료A", ""]])

        with self.assertRaises(ValueError) as ctx:
            get_materials_from_table(table)

        self.assertEqual(str(ctx.exception), "자재 1행: 배합비율을 입력하세요.")

    def test_get_materials_from_table_requires_numeric_ratio(self):
        table = FakeTable([["M001", "원료A", "abc"]])

        with self.assertRaises(ValueError) as ctx:
            get_materials_from_table(table)

        self.assertEqual(str(ctx.exception), "자재 1행: 배합비율은 숫자로 입력하세요.")

    def test_get_materials_from_table_requires_positive_ratio(self):
        table = FakeTable([["M001", "원료A", "0"]])

        with self.assertRaises(ValueError) as ctx:
            get_materials_from_table(table)

        self.assertEqual(str(ctx.exception), "자재 1행: 배합비율은 0보다 커야 합니다.")


class TestDhrDatabaseMessages(unittest.TestCase):
    @patch("models.dhr_database.logger")
    @patch.object(DhrDatabaseManager, "_generate_product_lot_with_conn", side_effect=sqlite3.OperationalError("boom"))
    def test_generate_product_lot_logs_korean_fallback_message(self, _mock_generate, mock_logger):
        with tempfile.TemporaryDirectory() as tmp:
            manager = DhrDatabaseManager(db_path=os.path.join(tmp, "dhr.db"))

            lot = manager.generate_product_lot("TEST", "2026-03-31")

            self.assertEqual(lot, "TEST26033101")
            # get_connection이 sqlite3.Error를 DatabaseError(접두 메시지 포함)로 변환한 뒤
            # generate_product_lot이 이를 포착해 fallback LOT을 반환한다.
            mock_logger.error.assert_called_once_with(
                "DHR LOT 생성 중 오류: DHR 데이터베이스 연결 오류: boom. 기본 LOT를 사용합니다."
            )


if __name__ == "__main__":
    unittest.main()
