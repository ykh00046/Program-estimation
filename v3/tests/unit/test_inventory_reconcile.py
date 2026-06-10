"""재고 정합성 검사·보정 단위 테스트 (PDCA #34 inventory_reconcile).

임시 DB + LEGACY_DB_PATH 패치로 운영 데이터 격리(#27/#30/#31 테스트 패턴 준수).
"""
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from models.database import MixingDatabaseManager  # noqa: E402
from models.repositories.material_stock_repository import (  # noqa: E402
    CONSUME_NOTE_FMT, MANUAL_EDIT_NOTE, RECONCILE_NOTE,
)


class _TmpDbTestCase(unittest.TestCase):
    """임시 DB 공통 셋업."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self._legacy_patch = patch(
            "models.database.LEGACY_DB_PATH",
            os.path.join(self.tmpdir.name, "__nonexistent_legacy.db"),
        )
        self._legacy_patch.start()
        db_path = os.path.join(self.tmpdir.name, "test_mixing.db")
        self.db = MixingDatabaseManager(db_path=db_path)

    def tearDown(self):
        self._legacy_patch.stop()
        self.tmpdir.cleanup()

    def _stock(self, code):
        for row in self.db.get_all_material_stock():
            if row["material_code"] == code:
                return row["current_stock"]
        return None

    def _save_record(self, lot, materials):
        """배합 기록 저장 헬퍼. materials: [(code, name, actual)]"""
        record = {
            "product_lot": lot, "recipe_name": "R1", "worker": "W1",
            "work_date": "2026-06-10", "work_time": "10:00:00",
            "total_amount": sum(m[2] for m in materials), "scale": "S",
        }
        details = [
            {"material_code": c, "material_name": n, "material_lot": "ML",
             "ratio": 50.0, "theory_amount": a, "actual_amount": a,
             "sequence_order": i + 1}
            for i, (c, n, a) in enumerate(materials)
        ]
        self.db.save_mixing_record(record, details)


class UpsertHistoryTests(_TmpDbTestCase):
    """upsert 수동 편집 이력화 (log_history opt-in)."""

    def test_default_upsert_records_no_history(self):
        """기본값(log_history=False) — 기존 동작 비트 보존 (회귀 가드)."""
        self.db.upsert_material_stock("M1", "재료A", 70.0, 0.0)
        self.assertEqual(self.db.get_stock_history("M1"), [])

    def test_log_history_records_adjust_with_delta(self):
        self.db.upsert_material_stock("M1", "재료A", 70.0, 0.0)
        self.db.upsert_material_stock("M1", "재료A", 100.0, 0.0, log_history=True)
        hist = self.db.get_stock_history("M1")
        self.assertEqual(len(hist), 1)
        self.assertEqual(hist[0]["change_type"], "ADJUST")
        self.assertEqual(hist[0]["quantity"], 30.0)
        self.assertEqual(hist[0]["stock_after"], 100.0)
        self.assertEqual(hist[0]["note"], MANUAL_EDIT_NOTE)

    def test_log_history_new_material_delta_is_full_amount(self):
        self.db.upsert_material_stock("M2", "재료B", 50.0, 0.0, log_history=True)
        hist = self.db.get_stock_history("M2")
        self.assertEqual(len(hist), 1)
        self.assertEqual(hist[0]["quantity"], 50.0)

    def test_log_history_unchanged_value_records_nothing(self):
        """무변경 일괄 저장(설정 다이얼로그)은 이력을 만들지 않는다."""
        self.db.upsert_material_stock("M1", "재료A", 70.0, 0.0, log_history=True)
        self.db.upsert_material_stock("M1", "재료A", 70.0, 5.0, log_history=True)
        self.assertEqual(len(self.db.get_stock_history("M1")), 1)


class ConsumptionNoteTests(_TmpDbTestCase):
    """apply_consumption note 파라미터 (LOT 마커)."""

    def test_default_note_is_legacy_string(self):
        self.db.upsert_material_stock("M1", "재료A", 100.0, 0.0)
        self.db.apply_consumption([{"material_code": "M1", "actual_amount": 10.0}])
        self.assertEqual(self.db.get_stock_history("M1")[0]["note"], "배합 자동 차감")

    def test_custom_note_carries_lot_marker(self):
        self.db.upsert_material_stock("M1", "재료A", 100.0, 0.0)
        note = CONSUME_NOTE_FMT.format(lot="LOT-X01")
        self.db.apply_consumption([{"material_code": "M1", "actual_amount": 10.0}], note)
        self.assertIn("(LOT LOT-X01)", self.db.get_stock_history("M1")[0]["note"])


class LedgerConsistencyTests(_TmpDbTestCase):
    """검사 1: 현재고 vs 최근 stock_after."""

    def test_normal_flow_is_consistent(self):
        """입고→차감 정상 흐름은 불일치 0건."""
        self.db.add_inbound("M1", "재료A", 100.0)
        self.db.apply_consumption([{"material_code": "M1", "actual_amount": 30.0}])
        self.assertEqual(self.db.check_ledger_consistency(), [])

    def test_unlogged_manual_edit_is_detected(self):
        """이력 없는 수동 편집(log_history=False) → drift 검출."""
        self.db.add_inbound("M1", "재료A", 100.0)
        self.db.upsert_material_stock("M1", "재료A", 80.0, 0.0)  # 이력 없이 변경
        issues = self.db.check_ledger_consistency()
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0]["material_code"], "M1")
        self.assertEqual(issues[0]["current_stock"], 80.0)
        self.assertEqual(issues[0]["ledger_stock"], 100.0)
        self.assertEqual(issues[0]["drift"], -20.0)

    def test_no_history_nonzero_stock_is_detected(self):
        """이력이 전혀 없는 자재의 current>0 → 장부 기준 0과 불일치."""
        self.db.upsert_material_stock("M1", "재료A", 50.0, 0.0)
        issues = self.db.check_ledger_consistency()
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0]["ledger_stock"], 0.0)
        self.assertEqual(issues[0]["drift"], 50.0)

    def test_seeded_zero_stock_is_consistent(self):
        """시드(0/0, 이력 없음)는 불일치 아님."""
        self.db.upsert_material_stock("M1", "재료A", 0.0, 0.0)
        self.assertEqual(self.db.check_ledger_consistency(), [])


class ReconcileEntryTests(_TmpDbTestCase):
    """장부 정렬: 재고 불변 + ADJUST 이력 1건."""

    def test_reconcile_fixes_chain_without_changing_stock(self):
        self.db.add_inbound("M1", "재료A", 100.0)
        self.db.upsert_material_stock("M1", "재료A", 80.0, 0.0)  # drift -20
        self.assertTrue(self.db.record_reconcile_entry("M1"))
        self.assertEqual(self._stock("M1"), 80.0)  # 재고 불변
        hist = self.db.get_stock_history("M1")
        self.assertEqual(hist[0]["change_type"], "ADJUST")
        self.assertEqual(hist[0]["quantity"], -20.0)
        self.assertEqual(hist[0]["stock_after"], 80.0)
        self.assertEqual(hist[0]["note"], RECONCILE_NOTE)
        self.assertEqual(self.db.check_ledger_consistency(), [])

    def test_reconcile_consistent_material_returns_false(self):
        self.db.add_inbound("M1", "재료A", 100.0)
        self.assertFalse(self.db.record_reconcile_entry("M1"))
        self.assertEqual(len(self.db.get_stock_history("M1")), 1)  # INBOUND만

    def test_reconcile_unknown_material_returns_false(self):
        self.assertFalse(self.db.record_reconcile_entry("NOPE"))


class UndeductedLotTests(_TmpDbTestCase):
    """검사 2: 미차감 의심 LOT 검출."""

    def test_lot_without_marker_is_detected(self):
        self.db.upsert_material_stock("M1", "재료A", 100.0, 0.0)
        self._save_record("LOT-A", [("M1", "재료A", 10.0)])
        rows = self.db.find_undeducted_lots("2026-06-01", "2026-06-30")
        self.assertEqual([r["product_lot"] for r in rows], ["LOT-A"])

    def test_lot_with_consume_marker_is_excluded(self):
        self.db.upsert_material_stock("M1", "재료A", 100.0, 0.0)
        self._save_record("LOT-A", [("M1", "재료A", 10.0)])
        self.db.apply_consumption(
            [{"material_code": "M1", "actual_amount": 10.0}],
            CONSUME_NOTE_FMT.format(lot="LOT-A"))
        self.assertEqual(self.db.find_undeducted_lots("2026-06-01", "2026-06-30"), [])

    def test_date_range_filters_records(self):
        self.db.upsert_material_stock("M1", "재료A", 100.0, 0.0)
        self._save_record("LOT-A", [("M1", "재료A", 10.0)])
        self.assertEqual(self.db.find_undeducted_lots("2026-07-01", "2026-07-31"), [])


class RetroDeductTests(_TmpDbTestCase):
    """소급 차감 (DataManager 오케스트레이션)."""

    def _make_dm(self):
        from models.data_manager import DataManager
        dm = DataManager.__new__(DataManager)  # 무거운 협력자 우회 (#29 패턴)
        dm.db_manager = self.db
        return dm

    def test_retro_deduct_applies_adjust_with_lot_marker(self):
        self.db.upsert_material_stock("M1", "재료A", 100.0, 0.0)
        self._save_record("LOT-A", [("M1", "재료A", 30.0)])
        dm = self._make_dm()
        applied = dm.retro_deduct_lots(["LOT-A"])
        self.assertEqual(applied, 1)
        self.assertEqual(self._stock("M1"), 70.0)
        hist = self.db.get_stock_history("M1")
        self.assertEqual(hist[0]["change_type"], "ADJUST")
        self.assertIn("(LOT LOT-A)", hist[0]["note"])

    def test_retro_deducted_lot_no_longer_flagged(self):
        """소급 차감(ADJUST 마커)된 LOT은 재검출에서 제외 — 중복 적용 방지."""
        self.db.upsert_material_stock("M1", "재료A", 100.0, 0.0)
        self._save_record("LOT-A", [("M1", "재료A", 30.0)])
        self._make_dm().retro_deduct_lots(["LOT-A"])
        self.assertEqual(self.db.find_undeducted_lots("2026-06-01", "2026-06-30"), [])

    def test_unknown_lot_is_skipped(self):
        applied = self._make_dm().retro_deduct_lots(["NOPE"])
        self.assertEqual(applied, 0)


if __name__ == "__main__":
    unittest.main()
