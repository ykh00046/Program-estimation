"""BackupQueue 단위 테스트 (PDCA #35 backup_hardening). gspread 무의존."""
import os
import sys
import tempfile
import unittest

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from models.backup.backup_queue import BackupQueue


class BackupQueueTests(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tmpdir.name, "pending.jsonl")
        self.queue = BackupQueue(path=self.path, max_rows=5)

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_empty_queue_loads_empty(self):
        self.assertEqual(self.queue.load(), [])
        self.assertEqual(self.queue.count(), 0)

    def test_enqueue_load_roundtrip_preserves_korean(self):
        records = [{"제품LOT": "LOT-A", "실제량": 10.5}, {"제품LOT": "LOT-B", "실제량": 3}]
        total = self.queue.enqueue(records)
        self.assertEqual(total, 2)
        loaded = self.queue.load()
        self.assertEqual(loaded, records)

    def test_enqueue_appends_in_order(self):
        self.queue.enqueue([{"n": 1}])
        self.queue.enqueue([{"n": 2}])
        self.assertEqual([r["n"] for r in self.queue.load()], [1, 2])

    def test_clear_removes_file(self):
        self.queue.enqueue([{"n": 1}])
        self.queue.clear()
        self.assertEqual(self.queue.load(), [])
        self.assertFalse(os.path.exists(self.path))

    def test_clear_on_missing_file_is_noop(self):
        self.queue.clear()  # 예외 없어야 함

    def test_corrupt_lines_are_skipped(self):
        self.queue.enqueue([{"n": 1}])
        with open(self.path, "a", encoding="utf-8") as f:
            f.write("not-json{{{\n")
            f.write('"문자열이지 dict 아님"\n')
        self.queue.enqueue([{"n": 2}])  # 손상 줄 스킵 후 재기록
        self.assertEqual([r["n"] for r in self.queue.load()], [1, 2])

    def test_cap_drops_oldest_rows(self):
        self.queue.enqueue([{"n": i} for i in range(5)])
        self.queue.enqueue([{"n": 5}, {"n": 6}])  # max_rows=5 초과
        loaded = self.queue.load()
        self.assertEqual(len(loaded), 5)
        self.assertEqual([r["n"] for r in loaded], [2, 3, 4, 5, 6])  # 오래된 0,1 drop

    def test_enqueue_empty_returns_current_count(self):
        self.queue.enqueue([{"n": 1}])
        self.assertEqual(self.queue.enqueue([]), 1)


if __name__ == "__main__":
    unittest.main()
