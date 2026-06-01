"""자재 입출고 이력 조회 다이얼로그 (PDCA #30 inventory_inbound_history).

`material_stock_history`의 이동 내역을 최신순으로 표시한다. 읽기 전용 뷰이며
데이터 조회는 DataManager에 위임한다.
"""
from typing import List, Dict

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox,
    QTableWidget, QTableWidgetItem, QHeaderView,
)
from PySide6.QtGui import QColor

from utils.logger import logger
from ui.styles import UIStyles, UITheme
from models.repositories.material_stock_repository import (
    MOVE_INBOUND, MOVE_CONSUME, MOVE_ADJUST,
)

# 이동 유형 표시 라벨
_TYPE_LABELS = {
    MOVE_INBOUND: "입고",
    MOVE_CONSUME: "차감",
    MOVE_ADJUST: "조정",
}

_COL_DATE = 0
_COL_NAME = 1
_COL_TYPE = 2
_COL_QTY = 3
_COL_AFTER = 4
_COL_NOTE = 5


class StockHistoryDialog(QDialog):
    """자재 입출고 이력 다이얼로그."""

    def __init__(self, data_manager, parent=None):
        super().__init__(parent)
        self.data_manager = data_manager
        self._stock_rows: List[Dict] = []
        self.setWindowTitle("입출고 이력")
        self.setMinimumSize(720, 480)
        try:
            self.setStyleSheet(UIStyles.get_dialog_style())
        except Exception:  # noqa: BLE001 — 스타일 누락 시 기본 스타일로 표시
            pass
        self._init_ui()
        self._load_filter_materials()
        self._refresh()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(12)

        title = QLabel("자재 입출고 이력")
        title.setStyleSheet(f"color: {UITheme.TEXT_PRIMARY}; font-size: 16px; font-weight: 700;")
        layout.addWidget(title)

        layout.addLayout(self._build_filter_row())

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(
            ["일시", "자재명", "유형", "증감", "이동 후 재고", "메모"]
        )
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setStyleSheet(UIStyles.get_table_style())
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(_COL_NOTE, QHeaderView.Stretch)
        for col in (_COL_DATE, _COL_NAME, _COL_TYPE, _COL_QTY, _COL_AFTER):
            header.setSectionResizeMode(col, QHeaderView.ResizeToContents)
        layout.addWidget(self.table)

    def _build_filter_row(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(8)

        label = QLabel("자재 필터:")
        label.setStyleSheet(f"color: {UITheme.TEXT_SECONDARY};")
        row.addWidget(label)

        self.filter_combo = QComboBox()
        self.filter_combo.currentIndexChanged.connect(self._refresh)
        row.addWidget(self.filter_combo)
        row.addStretch(1)

        self.refresh_btn = QPushButton("새로고침")
        self.refresh_btn.setStyleSheet(UIStyles.get_secondary_button_style())
        self.refresh_btn.clicked.connect(self._refresh)
        row.addWidget(self.refresh_btn)
        return row

    # ------------------------------------------------------------------
    # 데이터
    # ------------------------------------------------------------------

    def _load_filter_materials(self) -> None:
        try:
            self._stock_rows = self.data_manager.get_all_material_stock() or []
        except Exception as e:  # noqa: BLE001
            logger.error(f"이력 필터 자재 로드 실패: {e}", exc_info=True)
            self._stock_rows = []
        self.filter_combo.blockSignals(True)
        self.filter_combo.clear()
        self.filter_combo.addItem("전체", "")
        for row in self._stock_rows:
            code = str(row.get("material_code") or "")
            name = str(row.get("material_name") or "")
            label = f"{code} · {name}" if name and name != code else code
            self.filter_combo.addItem(label, code)
        self.filter_combo.blockSignals(False)

    def _refresh(self) -> None:
        code = self.filter_combo.currentData() if self.filter_combo.count() else ""
        try:
            rows = self.data_manager.get_stock_history(code or None, limit=200) or []
        except Exception as e:  # noqa: BLE001
            logger.error(f"입출고 이력 조회 실패: {e}", exc_info=True)
            rows = []
        self._fill_table(rows)

    def _fill_table(self, rows: List[Dict]) -> None:
        self.table.setRowCount(len(rows))
        for idx, row in enumerate(rows):
            change_type = str(row.get("change_type") or "")
            qty = self._to_float(row.get("quantity"))
            unit = str(row.get("unit") or "")

            date_item = QTableWidgetItem(str(row.get("created_at") or ""))
            name_item = QTableWidgetItem(str(row.get("material_name") or row.get("material_code") or ""))
            type_item = QTableWidgetItem(_TYPE_LABELS.get(change_type, change_type))
            qty_item = QTableWidgetItem(self._fmt_signed(qty, unit))
            after_item = QTableWidgetItem(self._fmt_num(row.get("stock_after")) + (f" {unit}" if unit else ""))
            note_item = QTableWidgetItem(str(row.get("note") or ""))

            qty_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            after_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            type_item.setTextAlignment(Qt.AlignCenter)

            color = self._type_color(change_type, qty)
            if color is not None:
                qty_item.setForeground(QColor(color))
                type_item.setForeground(QColor(color))

            self.table.setItem(idx, _COL_DATE, date_item)
            self.table.setItem(idx, _COL_NAME, name_item)
            self.table.setItem(idx, _COL_TYPE, type_item)
            self.table.setItem(idx, _COL_QTY, qty_item)
            self.table.setItem(idx, _COL_AFTER, after_item)
            self.table.setItem(idx, _COL_NOTE, note_item)

    # ------------------------------------------------------------------
    # 헬퍼
    # ------------------------------------------------------------------

    @staticmethod
    def _type_color(change_type: str, qty: float):
        if change_type == MOVE_INBOUND or qty > 0:
            return UITheme.SUCCESS_COLOR
        if change_type == MOVE_CONSUME or qty < 0:
            return UITheme.ERROR_COLOR
        return None

    @staticmethod
    def _to_float(value) -> float:
        try:
            return float(value or 0.0)
        except (TypeError, ValueError):
            return 0.0

    @classmethod
    def _fmt_signed(cls, value: float, unit: str) -> str:
        sign = "+" if value > 0 else ""
        return f"{sign}{cls._fmt_num(value)}" + (f" {unit}" if unit else "")

    @staticmethod
    def _fmt_num(value) -> str:
        try:
            num = float(value or 0.0)
        except (TypeError, ValueError):
            num = 0.0
        if num == int(num):
            return str(int(num))
        return f"{num:g}"
