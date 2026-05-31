"""대시보드 재고 부족 알림 통합 테스트 (PDCA: material-stock-threshold-alert).

DataManager(임시 DB)를 주입해 DashboardPanel의 알림 섹션이 저재고 자재를
카드로 렌더링하는지, 정상 시 빈 상태를 표시하는지 검증한다.
"""
import os
import sys
import tempfile
import unittest

_V3_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _V3_ROOT not in sys.path:
    sys.path.insert(0, _V3_ROOT)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from models.database import MixingDatabaseManager
from ui.panels.dashboard_panel import DashboardPanel


class _FakeDataManager:
    """DashboardPanel이 호출하는 메서드만 제공하는 경량 스텁 + 실제 재고 DB."""

    def __init__(self, db: MixingDatabaseManager):
        self.db_manager = db
        self._default_threshold = 0.0

    # 재고 관련 (실제 DB 위임)
    def get_low_stock_materials(self):
        return self.db_manager.get_low_stock_materials(self._default_threshold)

    def get_all_material_stock(self):
        return self.db_manager.get_all_material_stock()

    def get_default_min_threshold(self):
        return self._default_threshold

    def set_default_min_threshold(self, value):
        self._default_threshold = max(0.0, float(value or 0.0))
        return True

    def upsert_material_stock(self, code, name, current, threshold, unit="g"):
        return self.db_manager.upsert_material_stock(code, name, current, threshold, unit)

    def seed_material_stock_from_history(self):
        return self.db_manager.seed_material_stock_from_history()

    # 대시보드 기타 섹션 (빈 데이터)
    def get_monthly_production_stats(self, months=6):
        return []

    def get_top_materials(self, limit=10, start_date=None, end_date=None):
        return []

    def get_worker_stats(self, start_date=None, end_date=None):
        return []

    def get_recipe_frequency(self, limit=10):
        return []


class TestStockAlertDashboard(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def setUp(self):
        fd, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.db = MixingDatabaseManager(db_path=self.db_path)
        self.dm = _FakeDataManager(self.db)

    def tearDown(self):
        try:
            os.remove(self.db_path)
        except OSError:
            pass

    def test_settings_button_exists(self):
        panel = DashboardPanel(self.dm)
        self.assertTrue(hasattr(panel, "stock_settings_btn"))
        self.assertEqual(panel.stock_settings_btn.text(), "재고 설정")

    def test_empty_state_when_no_low_stock(self):
        self.db.upsert_material_stock("A", "정상자재", 800.0, 500.0)
        panel = DashboardPanel(self.dm)
        panel.refresh()
        self.assertTrue(panel.low_stock_empty_label.isVisible() or
                        not panel.low_stock_container.isVisible())
        # 카드 컨테이너에 stretch만 존재 (카드 위젯 없음)
        widget_count = sum(
            1 for i in range(panel.low_stock_layout.count())
            if panel.low_stock_layout.itemAt(i).widget() is not None
        )
        self.assertEqual(widget_count, 0)

    def test_alert_card_rendered_for_low_stock(self):
        self.db.upsert_material_stock("A", "부족자재", 120.0, 500.0)
        panel = DashboardPanel(self.dm)
        panel.refresh()
        widget_count = sum(
            1 for i in range(panel.low_stock_layout.count())
            if panel.low_stock_layout.itemAt(i).widget() is not None
        )
        self.assertEqual(widget_count, 1)

    def test_make_alert_card_shows_all_fields(self):
        panel = DashboardPanel(self.dm)
        item = {
            "material_name": "탄산칼슘", "current_stock": 120.0,
            "threshold": 500.0, "shortage": 380.0, "unit": "g",
        }
        card = panel._make_alert_card(item)
        from PySide6.QtWidgets import QLabel
        texts = [w.text() for w in card.findChildren(QLabel)]
        joined = " ".join(texts)
        self.assertIn("탄산칼슘", joined)
        self.assertIn("현재 재고", joined)
        self.assertIn("임계값", joined)
        self.assertIn("부족분", joined)

    def test_global_default_threshold_triggers_alert(self):
        # 자재 임계값 0 → 전역 기본값 적용
        self.db.upsert_material_stock("A", "임계값없음", 50.0, 0.0)
        panel = DashboardPanel(self.dm)
        panel.refresh()
        self.assertEqual(self._card_count(panel), 0)  # 기본 0 → 알림 없음
        self.dm.set_default_min_threshold(100.0)
        panel.refresh()
        self.assertEqual(self._card_count(panel), 1)  # 50<=100 → 알림

    @staticmethod
    def _card_count(panel):
        return sum(
            1 for i in range(panel.low_stock_layout.count())
            if panel.low_stock_layout.itemAt(i).widget() is not None
        )


if __name__ == "__main__":
    unittest.main()
