"""자재 발주(PO) 관리 다이얼로그 (PDCA #32 purchase_order_management).

발주 목록 조회/상태 필터 + 신규 발주 등록 + 발주 입고 처리 + 발주 취소를 제공한다.
표현/입력만 담당하고 영속화(발주 생성·입고 연동·취소)는 DataManager에 위임한다.
신규 발주 입력은 같은 파일의 보조 모달 `_NewOrderDialog`가 담당한다.
"""
from typing import List, Dict, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QPushButton,
    QLineEdit, QComboBox, QTableWidget, QTableWidgetItem, QHeaderView,
    QMessageBox, QInputDialog,
)
from PySide6.QtGui import QDoubleValidator, QColor

from utils.logger import logger
from ui.styles import UIStyles, UITheme
from models.repositories.purchase_order_repository import (
    PO_PENDING, PO_PARTIAL, PO_RECEIVED, PO_CANCELLED,
)

# 상태 표시 라벨
_STATUS_LABELS = {
    PO_PENDING: "대기",
    PO_PARTIAL: "부분입고",
    PO_RECEIVED: "입고완료",
    PO_CANCELLED: "취소",
}
# 필터 콤보 (라벨, status 값). 빈 값 = 전체
_FILTER_OPTIONS = [
    ("전체", ""),
    ("대기", PO_PENDING),
    ("부분입고", PO_PARTIAL),
    ("입고완료", PO_RECEIVED),
    ("취소", PO_CANCELLED),
]

_COL_PO = 0
_COL_MATERIAL = 1
_COL_SUPPLIER = 2
_COL_ORDERED = 3
_COL_RECEIVED = 4
_COL_REMAINING = 5
_COL_STATUS = 6


class PurchaseOrderDialog(QDialog):
    """자재 발주 관리 허브 다이얼로그."""

    def __init__(self, data_manager, parent=None):
        super().__init__(parent)
        self.data_manager = data_manager
        self._rows: List[Dict] = []
        self.setWindowTitle("발주 관리")
        self.setMinimumSize(820, 520)
        try:
            self.setStyleSheet(UIStyles.get_dialog_style())
        except Exception:  # noqa: BLE001 — 스타일 누락 시 기본 스타일로 표시
            pass
        self._init_ui()
        self._refresh()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(12)

        title = QLabel("자재 발주(PO) 관리")
        title.setStyleSheet(f"color: {UITheme.TEXT_PRIMARY}; font-size: 16px; font-weight: 700;")
        layout.addWidget(title)

        layout.addLayout(self._build_filter_row())

        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(
            ["발주번호", "자재", "매입처", "발주량", "입고량", "잔량", "상태"]
        )
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.setStyleSheet(UIStyles.get_table_style())
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(_COL_MATERIAL, QHeaderView.Stretch)
        for col in (_COL_PO, _COL_SUPPLIER, _COL_ORDERED, _COL_RECEIVED, _COL_REMAINING, _COL_STATUS):
            header.setSectionResizeMode(col, QHeaderView.ResizeToContents)
        layout.addWidget(self.table)

        layout.addLayout(self._build_button_row())

    def _build_filter_row(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(8)

        label = QLabel("상태 필터:")
        label.setStyleSheet(f"color: {UITheme.TEXT_SECONDARY};")
        row.addWidget(label)

        self.filter_combo = QComboBox()
        for text, value in _FILTER_OPTIONS:
            self.filter_combo.addItem(text, value)
        self.filter_combo.currentIndexChanged.connect(self._refresh)
        row.addWidget(self.filter_combo)
        row.addStretch(1)

        self.refresh_btn = QPushButton("새로고침")
        self.refresh_btn.setStyleSheet(UIStyles.get_secondary_button_style())
        self.refresh_btn.clicked.connect(self._refresh)
        row.addWidget(self.refresh_btn)
        return row

    def _build_button_row(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(8)

        self.new_btn = QPushButton("신규 발주")
        self.new_btn.setStyleSheet(UIStyles.get_primary_button_style())
        self.new_btn.clicked.connect(self._on_new_order)
        row.addWidget(self.new_btn)

        self.receive_btn = QPushButton("입고 처리")
        self.receive_btn.setStyleSheet(UIStyles.get_secondary_button_style())
        self.receive_btn.clicked.connect(self._on_receive)
        row.addWidget(self.receive_btn)

        self.cancel_order_btn = QPushButton("발주 취소")
        self.cancel_order_btn.setStyleSheet(UIStyles.get_secondary_button_style())
        self.cancel_order_btn.clicked.connect(self._on_cancel_order)
        row.addWidget(self.cancel_order_btn)

        row.addStretch(1)

        self.close_btn = QPushButton("닫기")
        self.close_btn.setStyleSheet(UIStyles.get_secondary_button_style())
        self.close_btn.clicked.connect(self.accept)
        row.addWidget(self.close_btn)
        return row

    # ------------------------------------------------------------------
    # 데이터
    # ------------------------------------------------------------------

    def _refresh(self) -> None:
        status = self.filter_combo.currentData() if self.filter_combo.count() else ""
        try:
            self._rows = self.data_manager.get_purchase_orders(status or None, limit=300) or []
        except Exception as e:  # noqa: BLE001 — 다이얼로그 안정성 우선
            logger.error(f"발주 목록 조회 실패: {e}", exc_info=True)
            self._rows = []
        self._fill_table(self._rows)

    def _fill_table(self, rows: List[Dict]) -> None:
        self.table.setRowCount(len(rows))
        for idx, row in enumerate(rows):
            unit = str(row.get("unit") or "")
            status = str(row.get("status") or "")
            code = str(row.get("material_code") or "")
            name = str(row.get("material_name") or code)
            material = f"{code} · {name}" if name and name != code else code

            po_item = QTableWidgetItem(str(row.get("po_number") or ""))
            material_item = QTableWidgetItem(material)
            supplier_item = QTableWidgetItem(str(row.get("supplier") or ""))
            ordered_item = QTableWidgetItem(self._fmt_qty(row.get("ordered_qty"), unit))
            received_item = QTableWidgetItem(self._fmt_qty(row.get("received_qty"), unit))
            remaining_item = QTableWidgetItem(self._fmt_qty(row.get("remaining_qty"), unit))
            status_item = QTableWidgetItem(_STATUS_LABELS.get(status, status))

            for it in (ordered_item, received_item, remaining_item):
                it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            status_item.setTextAlignment(Qt.AlignCenter)

            color = self._status_color(status)
            if color is not None:
                status_item.setForeground(QColor(color))

            self.table.setItem(idx, _COL_PO, po_item)
            self.table.setItem(idx, _COL_MATERIAL, material_item)
            self.table.setItem(idx, _COL_SUPPLIER, supplier_item)
            self.table.setItem(idx, _COL_ORDERED, ordered_item)
            self.table.setItem(idx, _COL_RECEIVED, received_item)
            self.table.setItem(idx, _COL_REMAINING, remaining_item)
            self.table.setItem(idx, _COL_STATUS, status_item)

    # ------------------------------------------------------------------
    # 액션
    # ------------------------------------------------------------------

    def _selected_row(self) -> Optional[Dict]:
        idx = self.table.currentRow()
        if idx < 0 or idx >= len(self._rows):
            return None
        return self._rows[idx]

    def _on_new_order(self) -> None:
        dialog = _NewOrderDialog(self.data_manager, self)
        if dialog.exec():
            self._refresh()

    def _on_receive(self) -> None:
        row = self._selected_row()
        if row is None:
            QMessageBox.information(self, "선택 필요", "입고 처리할 발주를 선택하세요.")
            return
        if str(row.get("status")) not in (PO_PENDING, PO_PARTIAL):
            QMessageBox.information(self, "처리 불가", "대기/부분입고 상태의 발주만 입고할 수 있습니다.")
            return
        remaining = self._to_float(row.get("remaining_qty"))
        unit = str(row.get("unit") or "")
        qty, ok = QInputDialog.getDouble(
            self, "입고 처리",
            f"{row.get('po_number')} · {row.get('material_name')}\n입고 수량 (잔량 {self._fmt_qty(remaining, unit)}):",
            remaining, 0.0, 1e12, 3,
        )
        if not ok:
            return
        if qty <= 0:
            QMessageBox.warning(self, "입력 확인", "입고 수량은 0보다 커야 합니다.")
            return
        try:
            done = self.data_manager.receive_purchase_order(int(row.get("id")), qty)
        except Exception as e:  # noqa: BLE001
            logger.error(f"발주 입고 처리 실패: {e}", exc_info=True)
            done = False
        if not done:
            QMessageBox.warning(self, "처리 실패", "발주 입고 처리 중 오류가 발생했습니다.")
            return
        QMessageBox.information(self, "입고 완료", f"{self._fmt_qty(qty, unit)} 입고를 처리했습니다.")
        self._refresh()

    def _on_cancel_order(self) -> None:
        row = self._selected_row()
        if row is None:
            QMessageBox.information(self, "선택 필요", "취소할 발주를 선택하세요.")
            return
        if str(row.get("status")) not in (PO_PENDING, PO_PARTIAL):
            QMessageBox.information(self, "취소 불가", "대기/부분입고 상태의 발주만 취소할 수 있습니다.")
            return
        confirm = QMessageBox.question(
            self, "발주 취소",
            f"{row.get('po_number')} 발주를 취소하시겠습니까?\n(이미 입고된 재고는 원복되지 않습니다.)",
        )
        if confirm != QMessageBox.Yes:
            return
        try:
            done = self.data_manager.cancel_purchase_order(int(row.get("id")))
        except Exception as e:  # noqa: BLE001
            logger.error(f"발주 취소 실패: {e}", exc_info=True)
            done = False
        if not done:
            QMessageBox.warning(self, "취소 실패", "발주 취소 중 오류가 발생했습니다.")
            return
        self._refresh()

    # ------------------------------------------------------------------
    # 헬퍼
    # ------------------------------------------------------------------

    @staticmethod
    def _status_color(status: str):
        return {
            PO_PENDING: UITheme.TEXT_SECONDARY,
            PO_PARTIAL: UITheme.WARNING_COLOR,
            PO_RECEIVED: UITheme.SUCCESS_COLOR,
            PO_CANCELLED: UITheme.ERROR_COLOR,
        }.get(status)

    @staticmethod
    def _to_float(value) -> float:
        try:
            return float(value or 0.0)
        except (TypeError, ValueError):
            return 0.0

    @classmethod
    def _fmt_qty(cls, value, unit: str) -> str:
        num = cls._to_float(value)
        text = str(int(num)) if num == int(num) else f"{num:g}"
        return text + (f" {unit}" if unit else "")


class _NewOrderDialog(QDialog):
    """신규 발주 입력 보조 모달."""

    def __init__(self, data_manager, parent=None):
        super().__init__(parent)
        self.data_manager = data_manager
        self._stock_rows: List[Dict] = []
        self.setWindowTitle("신규 발주")
        self.setMinimumWidth(440)
        try:
            self.setStyleSheet(UIStyles.get_dialog_style())
        except Exception:  # noqa: BLE001
            pass
        self._init_ui()
        self._load_materials()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(12)

        title = QLabel("자재 발주 등록")
        title.setStyleSheet(f"color: {UITheme.TEXT_PRIMARY}; font-size: 16px; font-weight: 700;")
        layout.addWidget(title)

        form = QFormLayout()
        form.setSpacing(10)

        self.material_combo = QComboBox()
        self.material_combo.setEditable(True)
        self.material_combo.currentIndexChanged.connect(self._on_material_selected)
        form.addRow(self._label("자재 코드/선택"), self.material_combo)

        self.name_edit = QLineEdit()
        self._apply_input_style(self.name_edit)
        form.addRow(self._label("자재명"), self.name_edit)

        self.supplier_edit = QLineEdit()
        self.supplier_edit.setPlaceholderText("매입처 (선택)")
        self._apply_input_style(self.supplier_edit)
        form.addRow(self._label("매입처"), self.supplier_edit)

        self.qty_edit = QLineEdit()
        self.qty_edit.setValidator(QDoubleValidator(0.0, 1e12, 3, self))
        self._apply_input_style(self.qty_edit)
        form.addRow(self._label("발주 수량"), self.qty_edit)

        self.unit_edit = QLineEdit("g")
        self._apply_input_style(self.unit_edit)
        form.addRow(self._label("단위"), self.unit_edit)

        self.note_edit = QLineEdit()
        self.note_edit.setPlaceholderText("납기 / 단가 / 사유 등 (선택)")
        self._apply_input_style(self.note_edit)
        form.addRow(self._label("메모"), self.note_edit)

        layout.addLayout(form)
        layout.addLayout(self._build_button_row())

    def _build_button_row(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(8)
        row.addStretch(1)

        self.cancel_btn = QPushButton("취소")
        self.cancel_btn.setStyleSheet(UIStyles.get_secondary_button_style())
        self.cancel_btn.clicked.connect(self.reject)
        row.addWidget(self.cancel_btn)

        self.submit_btn = QPushButton("등록")
        self.submit_btn.setStyleSheet(UIStyles.get_primary_button_style())
        self.submit_btn.clicked.connect(self._on_submit)
        row.addWidget(self.submit_btn)
        return row

    @staticmethod
    def _label(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(f"color: {UITheme.TEXT_SECONDARY};")
        return lbl

    @staticmethod
    def _apply_input_style(widget: QLineEdit) -> None:
        try:
            widget.setStyleSheet(UIStyles.get_input_field_style())
        except Exception:  # noqa: BLE001
            pass

    def _load_materials(self) -> None:
        try:
            self._stock_rows = self.data_manager.get_all_material_stock() or []
        except Exception as e:  # noqa: BLE001
            logger.error(f"발주 다이얼로그 자재 로드 실패: {e}", exc_info=True)
            self._stock_rows = []
        self.material_combo.blockSignals(True)
        self.material_combo.clear()
        self.material_combo.addItem("", "")  # 신규 입력용 빈 항목
        for row in self._stock_rows:
            code = str(row.get("material_code") or "")
            name = str(row.get("material_name") or "")
            label = f"{code} · {name}" if name and name != code else code
            self.material_combo.addItem(label, code)
        self.material_combo.setCurrentIndex(0)
        self.material_combo.blockSignals(False)

    def _on_material_selected(self, index: int) -> None:
        if index <= 0 or index - 1 >= len(self._stock_rows):
            return
        row = self._stock_rows[index - 1]
        self.material_combo.setEditText(str(row.get("material_code") or ""))
        self.name_edit.setText(str(row.get("material_name") or ""))
        self.unit_edit.setText(str(row.get("unit") or "g"))

    def _on_submit(self) -> None:
        code = self.material_combo.currentText().strip()
        name = self.name_edit.text().strip() or code
        supplier = self.supplier_edit.text().strip()
        unit = self.unit_edit.text().strip() or "g"
        note = self.note_edit.text().strip()
        qty = self._parse_num(self.qty_edit.text())
        if not code:
            QMessageBox.warning(self, "입력 확인", "자재 코드(또는 자재명)를 입력하세요.")
            return
        if qty <= 0:
            QMessageBox.warning(self, "입력 확인", "발주 수량은 0보다 커야 합니다.")
            return
        try:
            po_id = self.data_manager.create_purchase_order(code, name, supplier, qty, unit, note)
        except Exception as e:  # noqa: BLE001
            logger.error(f"발주 등록 실패: {e}", exc_info=True)
            po_id = None
        if not po_id:
            QMessageBox.warning(self, "등록 실패", "발주 등록 중 오류가 발생했습니다.")
            return
        logger.info(f"발주 등록 완료: {code} {qty}{unit}")
        QMessageBox.information(self, "등록 완료", f"{name} {qty}{unit} 발주를 등록했습니다.")
        self.accept()

    @staticmethod
    def _parse_num(text: str) -> float:
        try:
            value = float(str(text).replace(",", "").strip())
        except (TypeError, ValueError):
            return 0.0
        return max(0.0, value)
