"""재고 정합성 검사·보정 다이얼로그 (PDCA #34 inventory_reconcile).

검사 1: 장부 일관성 — 현재고 vs 최근 이력 stock_after 불일치 자재.
검사 2: 미차감 의심 — 기간 내 배합 LOT 중 차감 마커가 이력에 없는 기록.
모든 보정 액션은 사용자 확인 후에만 실행한다 (자동 보정 금지).
표현/입력만 담당하고 영속화는 DataManager에 위임한다.
"""
from typing import Dict, List

from PySide6.QtCore import Qt, QDate
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QDateEdit,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox, QGroupBox,
)

from utils.logger import logger
from ui.styles import UIStyles, UITheme


class ReconcileDialog(QDialog):
    """재고 정합성 검사·보정 다이얼로그."""

    def __init__(self, data_manager, parent=None):
        super().__init__(parent)
        self.data_manager = data_manager
        self.setWindowTitle("재고 정합성 검사")
        self.setMinimumSize(720, 560)
        try:
            self.setStyleSheet(UIStyles.get_dialog_style())
        except Exception:  # noqa: BLE001 — 스타일 누락 시 기본 스타일로 표시
            pass
        self._init_ui()
        self._run_ledger_check()
        self._run_undeducted_check()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(12)
        layout.addWidget(self._build_ledger_group(), stretch=1)
        layout.addWidget(self._build_undeducted_group(), stretch=1)
        layout.addLayout(self._build_bottom_row())

    def _build_ledger_group(self) -> QGroupBox:
        group = QGroupBox("장부 일관성 (현재고 vs 최근 이력)")
        box = QVBoxLayout(group)
        box.setSpacing(8)

        self.ledger_status_label = QLabel("")
        self.ledger_status_label.setStyleSheet(
            f"color: {UITheme.TEXT_SECONDARY}; font-size: 12px;")
        box.addWidget(self.ledger_status_label)

        self.ledger_table = QTableWidget(0, 5)
        self.ledger_table.setHorizontalHeaderLabels(
            ["자재코드", "자재명", "현재고", "장부재고", "차이"])
        self.ledger_table.verticalHeader().setVisible(False)
        self.ledger_table.setStyleSheet(UIStyles.get_table_style())
        header = self.ledger_table.horizontalHeader()
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        for col in (0, 2, 3, 4):
            header.setSectionResizeMode(col, QHeaderView.ResizeToContents)
        box.addWidget(self.ledger_table)

        row = QHBoxLayout()
        row.addStretch(1)
        self.reconcile_btn = QPushButton("장부 정렬 (재고 불변)")
        self.reconcile_btn.setStyleSheet(UIStyles.get_secondary_button_style())
        self.reconcile_btn.clicked.connect(self._on_reconcile_ledger)
        row.addWidget(self.reconcile_btn)
        box.addLayout(row)
        return group

    def _build_undeducted_group(self) -> QGroupBox:
        group = QGroupBox("미차감 의심 배합 기록")
        box = QVBoxLayout(group)
        box.setSpacing(8)

        period_row = QHBoxLayout()
        period_label = QLabel("기간:")
        period_label.setStyleSheet(f"color: {UITheme.TEXT_SECONDARY};")
        period_row.addWidget(period_label)
        self.start_date = QDateEdit(calendarPopup=True,
                                    date=QDate.currentDate().addDays(-7))
        self.end_date = QDateEdit(calendarPopup=True, date=QDate.currentDate())
        period_row.addWidget(self.start_date)
        period_row.addWidget(QLabel("~"))
        period_row.addWidget(self.end_date)
        self.check_btn = QPushButton("검사")
        self.check_btn.setStyleSheet(UIStyles.get_secondary_button_style())
        self.check_btn.clicked.connect(self._run_undeducted_check)
        period_row.addWidget(self.check_btn)
        period_row.addStretch(1)
        box.addLayout(period_row)

        self.undeducted_status_label = QLabel("")
        self.undeducted_status_label.setStyleSheet(
            f"color: {UITheme.TEXT_SECONDARY}; font-size: 12px;")
        box.addWidget(self.undeducted_status_label)

        self.lot_table = QTableWidget(0, 4)
        self.lot_table.setHorizontalHeaderLabels(
            ["LOT", "레시피", "작업일", "배합량(g)"])
        self.lot_table.verticalHeader().setVisible(False)
        self.lot_table.setStyleSheet(UIStyles.get_table_style())
        lot_header = self.lot_table.horizontalHeader()
        lot_header.setSectionResizeMode(0, QHeaderView.Stretch)
        for col in (1, 2, 3):
            lot_header.setSectionResizeMode(col, QHeaderView.ResizeToContents)
        box.addWidget(self.lot_table)

        row = QHBoxLayout()
        row.addStretch(1)
        self.retro_btn = QPushButton("선택 LOT 소급 차감")
        self.retro_btn.setStyleSheet(UIStyles.get_secondary_button_style())
        self.retro_btn.clicked.connect(self._on_retro_deduct)
        row.addWidget(self.retro_btn)
        box.addLayout(row)
        return group

    def _build_bottom_row(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.addStretch(1)
        close_btn = QPushButton("닫기")
        close_btn.setStyleSheet(UIStyles.get_primary_button_style())
        close_btn.clicked.connect(self.accept)
        row.addWidget(close_btn)
        return row

    # ------------------------------------------------------------------
    # 검사 1: 장부 일관성
    # ------------------------------------------------------------------

    def _run_ledger_check(self) -> None:
        try:
            issues = self.data_manager.check_ledger_consistency()
        except Exception as e:  # noqa: BLE001 — 다이얼로그 안정성 우선
            logger.error(f"장부 일관성 검사 실패: {e}", exc_info=True)
            issues = []
        self._fill_ledger_table(issues)

    def _fill_ledger_table(self, issues: List[Dict]) -> None:
        self.ledger_table.setRowCount(len(issues))
        for idx, issue in enumerate(issues):
            cells = [
                str(issue.get("material_code") or ""),
                str(issue.get("material_name") or ""),
                f"{float(issue.get('current_stock') or 0.0):g}",
                f"{float(issue.get('ledger_stock') or 0.0):g}",
                f"{float(issue.get('drift') or 0.0):+g}",
            ]
            for col, text in enumerate(cells):
                item = QTableWidgetItem(text)
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                if col >= 2:
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.ledger_table.setItem(idx, col, item)
        ok = not issues
        self.ledger_status_label.setText(
            "모든 자재의 장부가 일치합니다." if ok else f"불일치 {len(issues)}건 — 장부 정렬로 이력 체인을 복구할 수 있습니다.")
        self.reconcile_btn.setEnabled(not ok)

    def _on_reconcile_ledger(self) -> None:
        count = self.ledger_table.rowCount()
        if count == 0:
            return
        reply = QMessageBox.question(
            self, "장부 정렬",
            f"불일치 {count}건의 장부를 현재고 기준으로 정렬합니다.\n"
            "재고 수량은 변경되지 않으며 ADJUST 이력만 기록됩니다.\n진행하시겠습니까?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply != QMessageBox.Yes:
            return
        fixed = 0
        for row in range(count):
            code_item = self.ledger_table.item(row, 0)
            code = code_item.text() if code_item else ""
            if code and self.data_manager.record_reconcile_entry(code):
                fixed += 1
        QMessageBox.information(self, "장부 정렬 완료", f"{fixed}건의 장부를 정렬했습니다.")
        self._run_ledger_check()

    # ------------------------------------------------------------------
    # 검사 2: 미차감 의심 LOT
    # ------------------------------------------------------------------

    def _run_undeducted_check(self) -> None:
        start = self.start_date.date().toString("yyyy-MM-dd")
        end = self.end_date.date().toString("yyyy-MM-dd")
        try:
            rows = self.data_manager.find_undeducted_lots(start, end)
        except Exception as e:  # noqa: BLE001
            logger.error(f"미차감 검사 실패: {e}", exc_info=True)
            rows = []
        self._fill_lot_table(rows)

    def _fill_lot_table(self, rows: List[Dict]) -> None:
        self.lot_table.setRowCount(len(rows))
        for idx, row in enumerate(rows):
            lot_item = QTableWidgetItem(str(row.get("product_lot") or ""))
            lot_item.setFlags((lot_item.flags() | Qt.ItemIsUserCheckable) & ~Qt.ItemIsEditable)
            lot_item.setCheckState(Qt.Unchecked)
            self.lot_table.setItem(idx, 0, lot_item)
            others = [
                str(row.get("recipe_name") or ""),
                str(row.get("work_date") or ""),
                f"{float(row.get('total_amount') or 0.0):g}",
            ]
            for col, text in enumerate(others, start=1):
                item = QTableWidgetItem(text)
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                if col == 3:
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.lot_table.setItem(idx, col, item)
        self.undeducted_status_label.setText(
            "기간 내 미차감 의심 기록이 없습니다." if not rows
            else f"미차감 의심 {len(rows)}건 — 차감할 LOT을 체크 후 소급 차감하세요. "
                 "(토글 OFF 기간의 기록은 의도된 미차감일 수 있습니다)")
        self.retro_btn.setEnabled(bool(rows))

    def _checked_lots(self) -> List[str]:
        lots = []
        for row in range(self.lot_table.rowCount()):
            item = self.lot_table.item(row, 0)
            if item is not None and item.checkState() == Qt.Checked:
                lots.append(item.text())
        return lots

    def _on_retro_deduct(self) -> None:
        lots = self._checked_lots()
        if not lots:
            QMessageBox.warning(self, "선택 없음", "소급 차감할 LOT을 체크하세요.")
            return
        reply = QMessageBox.question(
            self, "소급 차감",
            f"선택한 {len(lots)}건의 배합 사용량을 재고에서 차감합니다.\n"
            "ADJUST 이력에 LOT이 기록되어 중복 적용이 방지됩니다.\n진행하시겠습니까?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply != QMessageBox.Yes:
            return
        try:
            applied = self.data_manager.retro_deduct_lots(lots)
        except Exception as e:  # noqa: BLE001
            logger.error(f"소급 차감 실패: {e}", exc_info=True)
            QMessageBox.warning(self, "소급 차감 실패", "소급 차감 중 오류가 발생했습니다.")
            return
        QMessageBox.information(self, "소급 차감 완료",
                                f"{applied}건의 LOT을 소급 차감했습니다.")
        self._run_undeducted_check()
        self._run_ledger_check()
