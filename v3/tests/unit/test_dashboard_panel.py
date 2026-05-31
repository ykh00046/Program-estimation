"""DashboardPanel 단위 테스트 (PDCA #17).

순수 헬퍼 (`_format_amount`) 및 패널 스모크 검증.
"""
import importlib
import os
import sys
import unittest
from unittest.mock import MagicMock


def _ensure_ui_dependencies() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    missing = []
    for name in ("PySide6", "qfluentwidgets"):
        try:
            importlib.import_module(name)
        except ModuleNotFoundError:
            missing.append(name)
    if missing:
        raise unittest.SkipTest(
            f"Dashboard panel tests need: {', '.join(missing)}"
        )


_ensure_ui_dependencies()

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from PySide6.QtWidgets import QApplication  # noqa: E402

_app = QApplication.instance() or QApplication(sys.argv)

from ui.panels.dashboard_panel import DashboardPanel  # noqa: E402


class FormatAmountTests(unittest.TestCase):
    """`_format_amount` 순수 함수 검증."""

    def test_zero(self):
        self.assertEqual(DashboardPanel._format_amount(0), "0 g")

    def test_under_1000(self):
        self.assertEqual(DashboardPanel._format_amount(999), "999 g")

    def test_exact_1000(self):
        self.assertEqual(DashboardPanel._format_amount(1000), "1.00 kg")

    def test_large_value(self):
        self.assertEqual(DashboardPanel._format_amount(1234567), "1,234.57 kg")

    def test_none_returns_zero(self):
        self.assertEqual(DashboardPanel._format_amount(None), "0 g")

    def test_string_invalid_returns_zero(self):
        self.assertEqual(DashboardPanel._format_amount("abc"), "0 g")


class DashboardPanelSmokeTests(unittest.TestCase):
    """빈 DB / 정상 DB 모킹 환경에서 refresh 안정성 검증."""

    def _make_mock_dm(self, monthly=None, top=None, workers=None, recipes=None,
                      low_stock=None):
        dm = MagicMock()
        dm.get_monthly_production_stats.return_value = monthly or []
        dm.get_top_materials.return_value = top or []
        dm.get_worker_stats.return_value = workers or []
        dm.get_recipe_frequency.return_value = recipes or []
        dm.get_low_stock_materials.return_value = low_stock or []
        return dm

    def test_refresh_empty_data_no_exception(self):
        dm = self._make_mock_dm()
        panel = DashboardPanel(dm)
        panel.refresh()
        self.assertEqual(panel.kpi_records_label.text(), "0")
        self.assertEqual(panel.kpi_amount_label.text(), "0 g")
        self.assertEqual(panel.materials_table.rowCount(), 0)
        self.assertEqual(panel.workers_table.rowCount(), 0)

    def test_refresh_with_sample_data(self):
        from datetime import datetime
        current_month = datetime.now().strftime("%Y-%m")
        dm = self._make_mock_dm(
            monthly=[{"year_month": current_month, "record_count": 5, "total_amount": 2500.0}],
            top=[
                {"material_code": "M1", "material_name": "재료A",
                 "total_actual": 1500.0, "use_count": 3},
                {"material_code": "M2", "material_name": "재료B",
                 "total_actual": 1000.0, "use_count": 2},
            ],
            workers=[
                {"worker": "홍길동", "record_count": 3,
                 "total_amount": 1500.0, "avg_amount": 500.0},
            ],
            recipes=[{"recipe_name": "R1", "run_count": 5, "total_amount": 2500.0}],
        )
        panel = DashboardPanel(dm)
        panel.refresh()
        self.assertEqual(panel.kpi_records_label.text(), "5")
        self.assertEqual(panel.kpi_amount_label.text(), "2.50 kg")
        self.assertEqual(panel.materials_table.rowCount(), 2)
        self.assertEqual(panel.workers_table.rowCount(), 1)
        self.assertEqual(panel.materials_table.item(0, 1).text(), "M1")
        self.assertEqual(panel.workers_table.item(0, 0).text(), "홍길동")

    def test_period_combo_default_is_six_months(self):
        dm = self._make_mock_dm()
        panel = DashboardPanel(dm)
        self.assertEqual(panel.period_combo.currentText(), "최근 6개월")
        start, end = panel._current_date_range()
        self.assertIsNotNone(start)
        self.assertIsNotNone(end)

    def test_period_combo_all_returns_none_range(self):
        dm = self._make_mock_dm()
        panel = DashboardPanel(dm)
        panel.period_combo.setCurrentIndex(3)  # "전체"
        start, end = panel._current_date_range()
        self.assertIsNone(start)
        self.assertIsNone(end)


class LowStockAlertBannerTests(unittest.TestCase):
    """재고 부족 알림 배너 표시/숨김 검증 (PDCA #27)."""

    def _make_dm(self, low_stock):
        dm = MagicMock()
        for m in ("get_monthly_production_stats", "get_top_materials",
                  "get_worker_stats", "get_recipe_frequency"):
            getattr(dm, m).return_value = []
        dm.get_low_stock_materials.return_value = low_stock
        return dm

    def test_no_alerts_hides_cards_shows_ok_label(self):
        panel = DashboardPanel(self._make_dm([]))
        panel.refresh()
        # offscreen: isVisible()는 부모 미표시로 항상 False → isHidden()로 명시 상태 검증
        self.assertTrue(panel.low_stock_container.isHidden())
        self.assertFalse(panel.low_stock_empty_label.isHidden())

    def test_alerts_show_cards(self):
        low = [
            {"material_code": "M1", "material_name": "재료A",
             "current_stock": 10.0, "threshold": 100.0, "shortage": 90.0, "unit": "g"},
            {"material_code": "M2", "material_name": "재료B",
             "current_stock": 0.0, "threshold": 50.0, "shortage": 50.0, "unit": "g"},
        ]
        panel = DashboardPanel(self._make_dm(low))
        panel.refresh()
        self.assertFalse(panel.low_stock_container.isHidden())
        self.assertTrue(panel.low_stock_empty_label.isHidden())
        # 카드 수 = 항목 수 + stretch(1)
        self.assertEqual(panel.low_stock_layout.count(), len(low) + 1)

    def test_more_label_when_exceeding_max_cards(self):
        many = [
            {"material_code": f"M{i}", "material_name": f"재료{i}",
             "current_stock": 1.0, "threshold": 100.0, "shortage": 99.0, "unit": "g"}
            for i in range(DashboardPanel._MAX_ALERT_CARDS + 3)
        ]
        panel = DashboardPanel(self._make_dm(many))
        panel.refresh()
        self.assertFalse(panel.low_stock_more_label.isHidden())
        self.assertIn("3", panel.low_stock_more_label.text())
        self.assertEqual(
            panel.low_stock_layout.count(), DashboardPanel._MAX_ALERT_CARDS + 1
        )

    def test_refresh_twice_does_not_accumulate_cards(self):
        low = [{"material_code": "M1", "material_name": "재료A",
                "current_stock": 10.0, "threshold": 100.0, "shortage": 90.0, "unit": "g"}]
        panel = DashboardPanel(self._make_dm(low))
        panel.refresh()
        panel.refresh()
        self.assertEqual(panel.low_stock_layout.count(), len(low) + 1)


if __name__ == "__main__":
    unittest.main()
