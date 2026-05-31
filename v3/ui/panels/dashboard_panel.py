"""배합 이력 대시보드 패널 (PDCA #17).

mixing_records / mixing_details에 누적된 데이터를 KPI 카드 + 월별 차트 +
자재 TOP-N / 작업자 통계 테이블로 시각화한다.

집계 로직은 모두 DataManager에 위임. 본 패널은 표현만 담당.
"""
import os
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple

from PySide6.QtCore import Qt
from PySide6.QtGui import QShowEvent
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QSizePolicy, QFrame,
    QStackedWidget, QGridLayout, QGroupBox, QMessageBox,
)

from utils.logger import logger
from ui.styles import UIStyles, UITheme
from models.dashboard_exporter import DashboardExporter

try:
    from PySide6.QtCharts import (
        QChart, QChartView, QBarSeries, QBarSet, QBarCategoryAxis, QValueAxis,
    )
    from PySide6.QtGui import QPainter, QColor
    _CHARTS_AVAILABLE = True
except ImportError:  # 빌드 환경에서 QtCharts 누락된 경우
    _CHARTS_AVAILABLE = False
    logger.warning("PySide6.QtCharts 모듈을 불러올 수 없습니다. 차트는 placeholder로 표시됩니다.")


PERIOD_OPTIONS: List[Tuple[str, Optional[int]]] = [
    ("최근 30일", 30),
    ("최근 90일", 90),
    ("최근 6개월", 180),
    ("전체", None),
]


class DashboardPanel(QWidget):
    """배합 이력 대시보드 패널."""

    def __init__(self, data_manager, parent=None):
        super().__init__(parent)
        self.setObjectName("DashboardPage")
        self.data_manager = data_manager
        self._exporter = DashboardExporter(data_manager)
        self._has_initial_loaded = False
        self._init_ui()

    # ------------------------------------------------------------------
    # UI 빌더
    # ------------------------------------------------------------------

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(14)

        layout.addWidget(self._build_period_bar())
        layout.addWidget(self._build_kpi_row())
        layout.addWidget(self._build_monthly_chart(), stretch=2)

        bottom_row = QHBoxLayout()
        bottom_row.setSpacing(14)
        bottom_row.addWidget(self._build_top_materials_card(), stretch=1)
        bottom_row.addWidget(self._build_worker_stats_card(), stretch=1)
        layout.addLayout(bottom_row, stretch=3)

    def _build_period_bar(self) -> QWidget:
        bar = QWidget()
        row = QHBoxLayout(bar)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(10)

        title = QLabel("배합 이력 대시보드")
        title.setStyleSheet(
            f"color: {UITheme.TEXT_PRIMARY}; font-size: 20px; font-weight: 700;"
        )
        row.addWidget(title)
        row.addStretch(1)

        period_label = QLabel("기간:")
        period_label.setStyleSheet(f"color: {UITheme.TEXT_SECONDARY};")
        row.addWidget(period_label)

        self.period_combo = QComboBox()
        for label, _ in PERIOD_OPTIONS:
            self.period_combo.addItem(label)
        self.period_combo.setCurrentIndex(2)  # 기본: 최근 6개월
        self.period_combo.currentIndexChanged.connect(self._on_period_changed)
        self.period_combo.setFixedWidth(140)
        row.addWidget(self.period_combo)

        self.refresh_btn = QPushButton("새로고침")
        self.refresh_btn.setStyleSheet(UIStyles.get_secondary_button_style())
        self.refresh_btn.clicked.connect(self.refresh)
        row.addWidget(self.refresh_btn)

        self.export_excel_btn = QPushButton("Excel 내보내기")
        self.export_excel_btn.setStyleSheet(UIStyles.get_secondary_button_style())
        self.export_excel_btn.clicked.connect(self._export_excel)
        row.addWidget(self.export_excel_btn)

        self.export_pdf_btn = QPushButton("PDF 내보내기")
        self.export_pdf_btn.setStyleSheet(UIStyles.get_secondary_button_style())
        self.export_pdf_btn.clicked.connect(self._export_pdf)
        row.addWidget(self.export_pdf_btn)

        return bar

    # ------------------------------------------------------------------
    # 내보내기 (PDCA #25)
    # ------------------------------------------------------------------

    def _export_excel(self) -> None:
        start, end = self._current_date_range()
        self._notify_export(self._exporter.export_excel(start, end))

    def _export_pdf(self) -> None:
        start, end = self._current_date_range()
        self._notify_export(self._exporter.export_pdf(start, end))

    def _notify_export(self, path: Optional[str]) -> None:
        if path:
            reply = QMessageBox.question(
                self, "내보내기 완료",
                f"파일이 생성되었습니다.\n{path}\n\n폴더를 여시겠습니까?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes,
            )
            if reply == QMessageBox.Yes:
                os.startfile(os.path.dirname(path))  # noqa: S606 — Windows 전용 앱
        else:
            QMessageBox.warning(self, "내보내기 실패", "파일 생성에 실패했습니다.")

    def _build_kpi_row(self) -> QWidget:
        container = QWidget()
        row = QHBoxLayout(container)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(12)

        self.kpi_records_label = QLabel("0")
        self.kpi_amount_label = QLabel("0 g")
        self.kpi_workers_label = QLabel("0")
        self.kpi_recipes_label = QLabel("0")

        row.addWidget(self._make_kpi_card("당월 생산 건수", self.kpi_records_label))
        row.addWidget(self._make_kpi_card("당월 총 배합량", self.kpi_amount_label))
        row.addWidget(self._make_kpi_card("당월 활성 작업자", self.kpi_workers_label))
        row.addWidget(self._make_kpi_card("누적 레시피 종류", self.kpi_recipes_label))
        return container

    def _make_kpi_card(self, title: str, value_label: QLabel) -> QWidget:
        card = QFrame()
        card.setObjectName("KpiCard")
        card.setStyleSheet(
            f"""
            QFrame#KpiCard {{
                background-color: {UITheme.SURFACE_ALT};
                border: 1px solid {UITheme.BORDER_SUBTLE};
                border-radius: {UITheme.CARD_BORDER_RADIUS}px;
                padding: 14px;
            }}
            """
        )
        card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(6)

        title_label = QLabel(title)
        title_label.setStyleSheet(
            f"color: {UITheme.TEXT_SECONDARY}; font-size: 13px;"
        )
        layout.addWidget(title_label)

        value_label.setStyleSheet(
            f"color: {UITheme.MINT_ACCENT}; font-size: 26px; font-weight: 700;"
        )
        layout.addWidget(value_label)
        return card

    def _build_monthly_chart(self) -> QWidget:
        card = QFrame()
        card.setStyleSheet(UIStyles.get_card_style())
        outer = QVBoxLayout(card)
        outer.setContentsMargins(16, 14, 16, 14)
        outer.setSpacing(8)

        title = QLabel("월별 생산량 (최근 6개월)")
        title.setStyleSheet(
            f"color: {UITheme.TEXT_PRIMARY}; font-size: 15px; font-weight: 600;"
        )
        outer.addWidget(title)

        self.chart_stack = QStackedWidget()
        self.chart_stack.setMinimumHeight(220)

        empty = QLabel("아직 기록이 없습니다.")
        empty.setAlignment(Qt.AlignCenter)
        empty.setStyleSheet(f"color: {UITheme.TEXT_SECONDARY}; font-size: 14px;")
        self.chart_stack.addWidget(empty)  # index 0

        if _CHARTS_AVAILABLE:
            self.chart_view = QChartView()
            self.chart_view.setRenderHint(QPainter.Antialiasing)
            self.chart_stack.addWidget(self.chart_view)  # index 1
        else:
            fallback = QLabel("차트 모듈을 사용할 수 없습니다 (PySide6.QtCharts 누락).")
            fallback.setAlignment(Qt.AlignCenter)
            fallback.setStyleSheet(f"color: {UITheme.TEXT_SECONDARY};")
            self.chart_stack.addWidget(fallback)

        outer.addWidget(self.chart_stack)
        return card

    def _build_top_materials_card(self) -> QWidget:
        card = QFrame()
        card.setStyleSheet(UIStyles.get_card_style())
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(8)

        title = QLabel("자재 사용량 TOP 10")
        title.setStyleSheet(
            f"color: {UITheme.TEXT_PRIMARY}; font-size: 15px; font-weight: 600;"
        )
        layout.addWidget(title)

        self.materials_table = QTableWidget(0, 5)
        self.materials_table.setHorizontalHeaderLabels(
            ["#", "자재코드", "자재명", "총 사용량", "횟수"]
        )
        self.materials_table.verticalHeader().setVisible(False)
        self.materials_table.setSelectionMode(QTableWidget.NoSelection)
        self.materials_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.materials_table.setStyleSheet(UIStyles.get_table_style())
        header = self.materials_table.horizontalHeader()
        header.setSectionResizeMode(2, QHeaderView.Stretch)
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        layout.addWidget(self.materials_table)
        return card

    def _build_worker_stats_card(self) -> QWidget:
        card = QFrame()
        card.setStyleSheet(UIStyles.get_card_style())
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(8)

        title = QLabel("작업자별 통계")
        title.setStyleSheet(
            f"color: {UITheme.TEXT_PRIMARY}; font-size: 15px; font-weight: 600;"
        )
        layout.addWidget(title)

        self.workers_table = QTableWidget(0, 4)
        self.workers_table.setHorizontalHeaderLabels(
            ["작업자", "건수", "총량", "평균"]
        )
        self.workers_table.verticalHeader().setVisible(False)
        self.workers_table.setSelectionMode(QTableWidget.NoSelection)
        self.workers_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.workers_table.setStyleSheet(UIStyles.get_table_style())
        header = self.workers_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        layout.addWidget(self.workers_table)
        return card

    # ------------------------------------------------------------------
    # 데이터 바인딩
    # ------------------------------------------------------------------

    def showEvent(self, event: QShowEvent) -> None:  # noqa: N802 (Qt API)
        super().showEvent(event)
        if not self._has_initial_loaded:
            self._has_initial_loaded = True
            self.refresh()

    def _on_period_changed(self, _index: int) -> None:
        self.refresh()

    def refresh(self) -> None:
        """모든 섹션 데이터 재로드 (public)."""
        try:
            self._refresh_kpis()
            self._refresh_chart()
            self._refresh_top_materials()
            self._refresh_worker_stats()
        except Exception as e:  # noqa: BLE001 — UI 안정성 우선
            logger.error(f"대시보드 새로고침 실패: {e}", exc_info=True)

    def _refresh_kpis(self) -> None:
        current_month = self._current_month_start()
        monthly_rows = self.data_manager.get_monthly_production_stats(months=1)
        record_count, amount = 0, 0.0
        for row in monthly_rows:
            if row.get("year_month") == current_month[:7]:
                record_count = int(row.get("record_count") or 0)
                amount = float(row.get("total_amount") or 0)
                break
        self.kpi_records_label.setText(f"{record_count:,}")
        self.kpi_amount_label.setText(self._format_amount(amount))

        worker_rows = self.data_manager.get_worker_stats(start_date=current_month)
        self.kpi_workers_label.setText(f"{len(worker_rows):,}")

        recipe_rows = self.data_manager.get_recipe_frequency(limit=10000)
        self.kpi_recipes_label.setText(f"{len(recipe_rows):,}")

    def _refresh_chart(self) -> None:
        rows = self.data_manager.get_monthly_production_stats(months=6)
        if not rows or not _CHARTS_AVAILABLE:
            self.chart_stack.setCurrentIndex(0)
            return
        self.chart_stack.setCurrentIndex(1)
        self._render_bar_chart(rows)

    def _render_bar_chart(self, rows: List[Dict]) -> None:
        bar_set = QBarSet("총 배합량 (g)")
        bar_set.setColor(QColor(UITheme.MINT_ACCENT))
        categories: List[str] = []
        for row in rows:
            bar_set.append(float(row.get("total_amount") or 0))
            categories.append(str(row.get("year_month") or ""))

        series = QBarSeries()
        series.append(bar_set)

        chart = QChart()
        chart.addSeries(series)
        chart.setTitle("")
        chart.legend().setVisible(False)
        chart.setBackgroundBrush(QColor(UITheme.SURFACE_ALT))
        chart.setBackgroundRoundness(0)

        axis_x = QBarCategoryAxis()
        axis_x.append(categories)
        axis_x.setLabelsColor(QColor(UITheme.TEXT_SECONDARY))
        chart.addAxis(axis_x, Qt.AlignBottom)
        series.attachAxis(axis_x)

        axis_y = QValueAxis()
        axis_y.setLabelFormat("%d")
        axis_y.setLabelsColor(QColor(UITheme.TEXT_SECONDARY))
        chart.addAxis(axis_y, Qt.AlignLeft)
        series.attachAxis(axis_y)

        self.chart_view.setChart(chart)

    def _refresh_top_materials(self) -> None:
        start, end = self._current_date_range()
        rows = self.data_manager.get_top_materials(limit=10, start_date=start, end_date=end)
        self._fill_top_materials_table(rows)

    def _fill_top_materials_table(self, rows: List[Dict]) -> None:
        self.materials_table.setRowCount(len(rows))
        for idx, row in enumerate(rows):
            self.materials_table.setItem(idx, 0, _make_item(str(idx + 1), align_right=True))
            self.materials_table.setItem(idx, 1, _make_item(str(row.get("material_code") or "")))
            self.materials_table.setItem(idx, 2, _make_item(str(row.get("material_name") or "")))
            self.materials_table.setItem(
                idx, 3,
                _make_item(self._format_amount(float(row.get("total_actual") or 0)), align_right=True),
            )
            self.materials_table.setItem(
                idx, 4,
                _make_item(f"{int(row.get('use_count') or 0):,}", align_right=True),
            )

    def _refresh_worker_stats(self) -> None:
        start, end = self._current_date_range()
        rows = self.data_manager.get_worker_stats(start_date=start, end_date=end)
        self._fill_worker_stats_table(rows)

    def _fill_worker_stats_table(self, rows: List[Dict]) -> None:
        self.workers_table.setRowCount(len(rows))
        for idx, row in enumerate(rows):
            self.workers_table.setItem(idx, 0, _make_item(str(row.get("worker") or "")))
            self.workers_table.setItem(
                idx, 1, _make_item(f"{int(row.get('record_count') or 0):,}", align_right=True)
            )
            self.workers_table.setItem(
                idx, 2,
                _make_item(self._format_amount(float(row.get("total_amount") or 0)), align_right=True),
            )
            self.workers_table.setItem(
                idx, 3,
                _make_item(self._format_amount(float(row.get("avg_amount") or 0)), align_right=True),
            )

    # ------------------------------------------------------------------
    # 헬퍼 (순수 함수)
    # ------------------------------------------------------------------

    def _current_date_range(self) -> Tuple[Optional[str], Optional[str]]:
        idx = self.period_combo.currentIndex()
        if idx < 0 or idx >= len(PERIOD_OPTIONS):
            return None, None
        days = PERIOD_OPTIONS[idx][1]
        if days is None:
            return None, None
        end = datetime.now().date()
        start = end - timedelta(days=days)
        return start.isoformat(), end.isoformat()

    @staticmethod
    def _current_month_start() -> str:
        today = datetime.now().date()
        return today.replace(day=1).isoformat()

    @staticmethod
    def _format_amount(grams: float) -> str:
        """g 단위 수치를 사람이 읽기 좋은 문자열로 변환."""
        if grams is None:
            return "0 g"
        try:
            value = float(grams)
        except (TypeError, ValueError):
            return "0 g"
        if value < 1000:
            return f"{value:,.0f} g"
        return f"{value / 1000:,.2f} kg"


def _make_item(text: str, align_right: bool = False) -> QTableWidgetItem:
    item = QTableWidgetItem(text)
    if align_right:
        item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
    item.setFlags(item.flags() & ~Qt.ItemIsEditable)
    return item
