"""GoogleSheetsBackup 견고화 단위 테스트 (PDCA #35).

gc/worksheet는 MagicMock 주입 — gspread 실 API 호출 없음.
"""
import os
import sys
import tempfile
import unittest
from unittest.mock import MagicMock

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from models.backup.backup_queue import BackupQueue
from models.backup.google_sheets_backup import BACKUP_COLUMNS, GoogleSheetsBackup


def _record(lot="LOT-A", **overrides):
    base = {col: "" for col in BACKUP_COLUMNS}
    base["제품LOT"] = lot
    base["품목코드"] = "M1"
    base["실제량"] = 10.0
    base.update(overrides)
    return base


class _BackupTestCase(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.queue = BackupQueue(
            path=os.path.join(self.tmpdir.name, "pending.jsonl"))
        self.config = MagicMock()
        self.config.is_backup_enabled.return_value = True
        self.config.is_configured.return_value = True
        self.backup = GoogleSheetsBackup(self.config, queue=self.queue)
        # 인증 우회: gc가 설정돼 있으면 _authenticate는 True를 반환
        self.backup.gc = MagicMock()
        self.ws = MagicMock()
        self.ws.row_values.return_value = list(BACKUP_COLUMNS)
        self.backup.gc.open_by_url.return_value.worksheet.return_value = self.ws

    def tearDown(self):
        self.tmpdir.cleanup()


class ColumnSchemaTests(_BackupTestCase):
    """V1: dict 순서 무관 명시적 컬럼 변환 + parity."""

    def test_parity_build_backup_records_keys_match_schema(self):
        """DataManager 페이로드 키 == BACKUP_COLUMNS (#27 parity 교훈)."""
        from models.data_manager import DataManager
        rows = DataManager._build_backup_records(
            {"product_lot": "L", "recipe_name": "R", "worker": "W",
             "work_date": "D", "work_time": "T", "total_amount": 1.0, "scale": "S"},
            [{"material_code": "M", "material_name": "N", "material_lot": "ML",
              "ratio": 1.0, "theory_amount": 1.0, "actual_amount": 1.0,
              "sequence_order": 1}],
        )
        self.assertEqual(list(rows[0].keys()), BACKUP_COLUMNS)

    def test_rows_follow_schema_order_not_dict_order(self):
        record = _record()
        shuffled = dict(reversed(list(record.items())))  # dict 순서 뒤섞기
        success, _ = self.backup.backup_records([shuffled])
        self.assertTrue(success)
        sent = self.ws.append_rows.call_args[0][0]
        self.assertEqual(sent[0][BACKUP_COLUMNS.index("제품LOT")], "LOT-A")
        self.assertEqual(sent[0][BACKUP_COLUMNS.index("품목코드")], "M1")


class HeaderResolutionTests(_BackupTestCase):
    """V2: 헤더 3분기."""

    def test_empty_sheet_inserts_standard_header(self):
        self.ws.row_values.return_value = []
        success, _ = self.backup.backup_records([_record()])
        self.assertTrue(success)
        self.ws.insert_row.assert_called_once_with(BACKUP_COLUMNS, 1)

    def test_exact_match_appends_without_insert(self):
        success, _ = self.backup.backup_records([_record()])
        self.assertTrue(success)
        self.ws.insert_row.assert_not_called()

    def test_reordered_header_remaps_to_sheet_order(self):
        sheet_order = list(reversed(BACKUP_COLUMNS))
        self.ws.row_values.return_value = sheet_order
        success, _ = self.backup.backup_records([_record()])
        self.assertTrue(success)
        sent = self.ws.append_rows.call_args[0][0]
        self.assertEqual(sent[0][sheet_order.index("제품LOT")], "LOT-A")

    def test_mismatched_column_set_fails_and_enqueues(self):
        self.ws.row_values.return_value = ["엉뚱한컬럼"] + BACKUP_COLUMNS[1:]
        success, msg = self.backup.backup_records([_record()])
        self.assertFalse(success)
        self.assertIn("누락", msg)
        self.assertIn("대기 적재", msg)
        self.assertEqual(self.queue.count(), 1)
        self.ws.append_rows.assert_not_called()


class QueueIntegrationTests(_BackupTestCase):
    """V3: 실패 적재 + 성공 flush."""

    def test_transport_failure_enqueues_new_records(self):
        self.ws.append_rows.side_effect = RuntimeError("network down")
        success, msg = self.backup.backup_records([_record("LOT-A"), _record("LOT-B")])
        self.assertFalse(success)
        self.assertIn("신규 2건 대기 적재", msg)
        self.assertEqual(self.queue.count(), 2)
        self.config.increment_backup_failure.assert_called_once()

    def test_success_flushes_pending_before_new(self):
        self.queue.enqueue([_record("LOT-OLD")])
        success, msg = self.backup.backup_records([_record("LOT-NEW")])
        self.assertTrue(success)
        self.assertIn("대기 1건 포함", msg)
        sent = self.ws.append_rows.call_args[0][0]
        lot_idx = BACKUP_COLUMNS.index("제품LOT")
        self.assertEqual([row[lot_idx] for row in sent], ["LOT-OLD", "LOT-NEW"])
        self.assertEqual(self.queue.count(), 0)  # flush 후 clear

    def test_failure_keeps_pending_and_adds_new_once(self):
        """실패 시 pending 중복 적재 금지 — 신규분만 추가."""
        self.queue.enqueue([_record("LOT-OLD")])
        self.ws.append_rows.side_effect = RuntimeError("boom")
        self.backup.backup_records([_record("LOT-NEW")])
        lots = [r["제품LOT"] for r in self.queue.load()]
        self.assertEqual(lots, ["LOT-OLD", "LOT-NEW"])

    def test_empty_records_with_pending_retries_flush(self):
        """신규분이 없어도 대기분이 있으면 flush를 시도한다."""
        self.queue.enqueue([_record("LOT-OLD")])
        success, _ = self.backup.backup_records([])
        self.assertTrue(success)
        self.assertEqual(self.queue.count(), 0)

    def test_disabled_backup_does_not_touch_queue(self):
        self.config.is_backup_enabled.return_value = False
        success, _ = self.backup.backup_records([_record()])
        self.assertFalse(success)
        self.assertEqual(self.queue.count(), 0)

    def test_auth_failure_does_not_enqueue(self):
        """설정 문제(인증)는 재시도 무의미 — 큐 미적재."""
        self.backup.gc = None
        self.config.get_credentials_file.return_value = ""
        success, msg = self.backup.backup_records([_record()])
        self.assertFalse(success)
        self.assertIn("인증", msg)
        self.assertEqual(self.queue.count(), 0)


if __name__ == "__main__":
    unittest.main()
