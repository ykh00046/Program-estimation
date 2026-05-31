"""순수 평가 로직 `evaluate_inventory_alerts` 단위 테스트 (PDCA #27).

Qt·DB 무의존. 경계값/제외/정렬/안전 변환 검증.
"""
import os
import sys
import unittest


current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from models.inventory_alert import (  # noqa: E402
    LEVEL_LOW,
    LEVEL_OUT,
    MaterialAlert,
    evaluate_inventory_alerts,
)


def _row(code, name, current, threshold):
    return {
        "material_code": code,
        "material_name": name,
        "current_stock": current,
        "min_stock_threshold": threshold,
    }


class EvaluateInventoryAlertsTests(unittest.TestCase):
    def test_empty_input_returns_empty(self):
        self.assertEqual(evaluate_inventory_alerts([]), [])
        self.assertEqual(evaluate_inventory_alerts(None), [])

    def test_unset_threshold_excluded(self):
        # 임계값 0/음수는 미설정 → 제외
        rows = [_row("A", "재료A", 0, 0), _row("B", "재료B", 5, -1)]
        self.assertEqual(evaluate_inventory_alerts(rows), [])

    def test_ok_when_stock_above_threshold(self):
        rows = [_row("A", "재료A", 100, 50)]
        self.assertEqual(evaluate_inventory_alerts(rows), [])

    def test_boundary_equal_threshold_is_low_stock(self):
        # current == threshold → 알림(LOW_STOCK)
        rows = [_row("A", "재료A", 50, 50)]
        alerts = evaluate_inventory_alerts(rows)
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0].level, LEVEL_LOW)
        self.assertEqual(alerts[0].shortfall, 0.0)

    def test_low_stock_shortfall(self):
        rows = [_row("A", "재료A", 30, 100)]
        alert = evaluate_inventory_alerts(rows)[0]
        self.assertEqual(alert.level, LEVEL_LOW)
        self.assertEqual(alert.shortfall, 70.0)

    def test_out_of_stock_when_zero_or_negative(self):
        rows = [_row("A", "재료A", 0, 100), _row("B", "재료B", -5, 100)]
        alerts = {a.material_code: a for a in evaluate_inventory_alerts(rows)}
        self.assertEqual({a.level for a in alerts.values()}, {LEVEL_OUT})
        self.assertEqual(alerts["A"].shortfall, 100.0)   # 0 → 100-0
        self.assertEqual(alerts["B"].shortfall, 105.0)   # -5 → 100-(-5)

    def test_sorted_by_shortfall_desc(self):
        rows = [
            _row("A", "소부족", 90, 100),   # shortfall 10
            _row("B", "대부족", 10, 100),   # shortfall 90
            _row("C", "중부족", 60, 100),   # shortfall 40
        ]
        codes = [a.material_code for a in evaluate_inventory_alerts(rows)]
        self.assertEqual(codes, ["B", "C", "A"])

    def test_missing_or_string_values_are_safe(self):
        rows = [
            {"material_code": "A", "material_name": "재료A",
             "current_stock": None, "min_stock_threshold": "100"},
            {"material_code": "B", "min_stock_threshold": "abc"},  # 변환 실패→0→제외
        ]
        alerts = evaluate_inventory_alerts(rows)
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0].material_code, "A")
        self.assertEqual(alerts[0].level, LEVEL_OUT)  # None→0.0

    def test_row_without_code_skipped(self):
        rows = [{"material_name": "이름만", "current_stock": 1, "min_stock_threshold": 100}]
        self.assertEqual(evaluate_inventory_alerts(rows), [])

    def test_default_threshold_applied_when_unset(self):
        # 자재별 임계값 0 → 전역 기본 임계값으로 평가
        rows = [_row("A", "재료A", 20, 0)]
        self.assertEqual(evaluate_inventory_alerts(rows, default_threshold=0), [])
        alerts = evaluate_inventory_alerts(rows, default_threshold=50)
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0].threshold, 50.0)
        self.assertEqual(alerts[0].shortfall, 30.0)

    def test_per_material_threshold_overrides_default(self):
        # 자재별 임계값>0이면 전역 기본보다 우선
        rows = [_row("A", "재료A", 80, 100)]
        alert = evaluate_inventory_alerts(rows, default_threshold=10)[0]
        self.assertEqual(alert.threshold, 100.0)

    def test_returns_material_alert_namedtuple(self):
        alert = evaluate_inventory_alerts([_row("A", "재료A", 1, 10)])[0]
        self.assertIsInstance(alert, MaterialAlert)
        self.assertEqual(alert.material_name, "재료A")
        self.assertEqual(alert.threshold, 10.0)


if __name__ == "__main__":
    unittest.main()
