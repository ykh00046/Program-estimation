"""자재 재고 설정 다이얼로그 (PDCA: material-stock-threshold-alert).

자재별 현재고/임계값과 전역 기본 임계값을 편집한다. 표현/입력만 담당하고
영속화는 DataManager에 위임한다.
"""
from typing import List, Dict

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox, QWidget,
)
from PySide6.QtGui import QDoubleValidator

from utils.logger import logger
from ui.styles import UIStyles, UITheme

# 편집 가능 컬럼 인덱스
_COL_CODE = 0
_COL_NAME = 1
_COL_CURRENT = 2
_COL_THRESHOLD = 3
_COL_UNIT = 4


class StockSettingsDialog(QDialog):
    """자재 재고/임계값 설정 다이얼로그."""

    def __init__(self, data_manager, parent=None):
        super().__init__(parent)
        self.data_manager = data_manager
        self.setWindowTitle("재고 설정")
        self.setMinimumSize(640, 480)
        try:
            self.setStyleSheet(UIStyles.get_dialog_style())
        except Exception:  # noqa: BLE001 — 스타일 누락 시 기본 스타일로 표시
            pass
        self._init_ui()
        self._load_data()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(12)

        title = QLabel("자재 재고 임계값 설정")
        title.setStyleSheet(
            f"color: {UITheme.TEXT_PRIMARY}; font-size: 16px; font-weight: 700;"
        )
        layout.addWidget(title)

        layout.addWidget(self._build_default_threshold_row())

        hint = QLabel(
            "임계값이 0인 자재는 전역 기본 임계값을 적용합니다. "
            "현재 재고가 임계값 이하이면 대시보드에 알림이 표시됩니다."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet(f"color: {UITheme.TEXT_SECONDARY}; font-size: 12px;")
        layout.addWidget(hint)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(
            ["자재코드", "자재명", "현재 재고", "임계값", "단위"]
        )
        self.table.verticalHeader().setVisible(False)
        self.table.setStyleSheet(UIStyles.get_table_style())
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(_COL_NAME, QHeaderView.Stretch)
        for col in (_COL_CODE, _COL_CURRENT, _COL_THRESHOLD, _COL_UNIT):
            header.setSectionResizeMode(col, QHeaderView.ResizeToContents)
        layout.addWidget(self.table)

        layout.addLayout(self._build_button_row())

    def _build_default_threshold_row(self) -> QWidget:
        wrap = QWidget()
        row = QHBoxLayout(wrap)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)

        label = QLabel("전역 기본 임계값 (g):")
        label.setStyleSheet(f"color: {UITheme.TEXT_SECONDARY};")
        row.addWidget(label)

        self.default_threshold_edit = QLineEdit()
        self.default_threshold_edit.setValidator(QDoubleValidator(0.0, 1e12, 2, self))
        self.default_threshold_edit.setFixedWidth(140)
        try:
            self.default_threshold_edit.setStyleSheet(UIStyles.get_input_field_style())
        except Exception:  # noqa: BLE001
            pass
        row.addWidget(self.default_threshold_edit)
        row.addStretch(1)
        return wrap

    def _build_button_row(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(8)

        self.reseed_btn = QPushButton("자재 새로고침(이력에서)")
        self.reseed_btn.setStyleSheet(UIStyles.get_secondary_button_style())
        self.reseed_btn.clicked.connect(self._on_reseed)
        row.addWidget(self.reseed_btn)

        row.addStretch(1)

        self.cancel_btn = QPushButton("취소")
        self.cancel_btn.setStyleSheet(UIStyles.get_secondary_button_style())
        self.cancel_btn.clicked.connect(self.reject)
        row.addWidget(self.cancel_btn)

        self.save_btn = QPushButton("저장")
        self.save_btn.setStyleSheet(UIStyles.get_primary_button_style())
        self.save_btn.clicked.connect(self._on_save)
        row.addWidget(self.save_btn)
        return row

    # ------------------------------------------------------------------
    # 데이터
    # ------------------------------------------------------------------

    def _load_data(self) -> None:
        try:
            self.data_manager.seed_material_stock_from_history()
            default_threshold = self.data_manager.get_default_min_threshold()
            rows = self.data_manager.get_all_material_stock()
        except Exception as e:  # noqa: BLE001 — 다이얼로그 안정성 우선
            logger.error(f"재고 설정 로드 실패: {e}", exc_info=True)
            rows = []
            default_threshold = 0.0
        self.default_threshold_edit.setText(self._fmt_num(default_threshold))
        self._fill_table(rows)

    def _fill_table(self, rows: List[Dict]) -> None:
        self.table.setRowCount(len(rows))
        for idx, row in enumerate(rows):
            code_item = self._readonly_item(str(row.get("material_code") or ""))
            name_item = self._readonly_item(str(row.get("material_name") or ""))
            unit_item = self._readonly_item(str(row.get("unit") or "g"))
            current_item = QTableWidgetItem(self._fmt_num(row.get("current_stock")))
            threshold_item = QTableWidgetItem(self._fmt_num(row.get("min_stock_threshold")))
            current_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            threshold_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.table.setItem(idx, _COL_CODE, code_item)
            self.table.setItem(idx, _COL_NAME, name_item)
            self.table.setItem(idx, _COL_CURRENT, current_item)
            self.table.setItem(idx, _COL_THRESHOLD, threshold_item)
            self.table.setItem(idx, _COL_UNIT, unit_item)

    def _on_reseed(self) -> None:
        try:
            inserted = self.data_manager.seed_material_stock_from_history()
            rows = self.data_manager.get_all_material_stock()
        except Exception as e:  # noqa: BLE001
            logger.error(f"자재 새로고침 실패: {e}", exc_info=True)
            QMessageBox.warning(self, "새로고침 실패", "자재 목록을 불러오지 못했습니다.")
            return
        self._fill_table(rows)
        QMessageBox.information(self, "새로고침 완료", f"신규 {inserted}건이 추가되었습니다.")

    def _on_save(self) -> None:
        try:
            self.data_manager.set_default_min_threshold(
                self._parse_num(self.default_threshold_edit.text())
            )
            saved = 0
            for r in range(self.table.rowCount()):
                code = self._cell_text(r, _COL_CODE)
                name = self._cell_text(r, _COL_NAME)
                if not code and not name:
                    continue
                current = self._parse_num(self._cell_text(r, _COL_CURRENT))
                threshold = self._parse_num(self._cell_text(r, _COL_THRESHOLD))
                unit = self._cell_text(r, _COL_UNIT) or "g"
                if self.data_manager.upsert_material_stock(code, name, current, threshold, unit):
                    saved += 1
        except Exception as e:  # noqa: BLE001
            logger.error(f"재고 설정 저장 실패: {e}", exc_info=True)
            QMessageBox.warning(self, "저장 실패", "재고 설정 저장 중 오류가 발생했습니다.")
            return
        logger.info(f"재고 설정 저장 완료: {saved}건")
        QMessageBox.information(self, "저장 완료", f"{saved}건의 자재 재고를 저장했습니다.")
        self.accept()

    # ------------------------------------------------------------------
    # 헬퍼
    # ------------------------------------------------------------------

    @staticmethod
    def _readonly_item(text: str) -> QTableWidgetItem:
        item = QTableWidgetItem(text)
        item.setFlags(item.flags() & ~Qt.ItemIsEditable)
        return item

    def _cell_text(self, row: int, col: int) -> str:
        item = self.table.item(row, col)
        return item.text().strip() if item is not None else ""

    @staticmethod
    def _parse_num(text: str) -> float:
        try:
            value = float(str(text).replace(",", "").strip())
        except (TypeError, ValueError):
            return 0.0
        return max(0.0, value)

    @staticmethod
    def _fmt_num(value) -> str:
        try:
            num = float(value or 0.0)
        except (TypeError, ValueError):
            num = 0.0
        if num == int(num):
            return str(int(num))
        return f"{num:g}"
