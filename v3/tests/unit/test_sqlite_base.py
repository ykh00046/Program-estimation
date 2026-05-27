"""SqliteManagerBase 단위 테스트 (PDCA #18 Part A)."""
import os
import sqlite3
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from models._sqlite_base import SqliteManagerBase  # noqa: E402
from utils.error_handler import DatabaseError  # noqa: E402


class TestSqliteManagerBase(unittest.TestCase):
    """SqliteManagerBase의 공통 인프라 동작 검증."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)

    def _new_path(self, sub: str = "nested/x.db") -> str:
        return os.path.join(self._tmp.name, sub)

    def test_init_creates_parent_dir(self):
        path = self._new_path("a/b/c/x.db")
        SqliteManagerBase(path)
        self.assertTrue(os.path.isdir(os.path.dirname(path)))

    def test_init_handles_filename_only(self):
        """dirname이 빈 문자열일 때 OSError가 나지 않아야 한다."""
        # 작업 디렉토리 의존 회피: tmpdir로 cwd 이동.
        orig_cwd = os.getcwd()
        try:
            os.chdir(self._tmp.name)
            SqliteManagerBase("standalone.db")
        finally:
            os.chdir(orig_cwd)

    def test_connection_enables_foreign_keys_and_row_factory(self):
        path = self._new_path()
        mgr = SqliteManagerBase(path)
        with mgr.get_connection() as conn:
            cur = conn.execute("PRAGMA foreign_keys")
            self.assertEqual(cur.fetchone()[0], 1)
            self.assertIs(conn.row_factory, sqlite3.Row)

    def test_connection_wraps_sqlite_error(self):
        path = self._new_path()
        mgr = SqliteManagerBase(path)
        with self.assertRaises(DatabaseError):
            with mgr.get_connection() as conn:
                conn.execute("CREATE TABLE t (id INTEGER PRIMARY KEY)")
                conn.execute("INSERT INTO t (id) VALUES (1)")
                # PRIMARY KEY 중복 → IntegrityError → DatabaseError로 변환되어야 함.
                conn.execute("INSERT INTO t (id) VALUES (1)")

    def test_log_prefix_appears_in_error(self):
        path = self._new_path()
        mgr = SqliteManagerBase(path, log_prefix="DHR 데이터베이스")
        try:
            with mgr.get_connection() as conn:
                conn.execute("SELECT * FROM nonexistent_table")
        except DatabaseError as e:
            self.assertIn("DHR 데이터베이스", str(e))
        else:
            self.fail("DatabaseError가 발생해야 합니다.")


if __name__ == "__main__":
    unittest.main()
