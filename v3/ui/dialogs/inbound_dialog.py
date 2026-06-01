"""자재 입고(매입) 등록 다이얼로그 (PDCA #30 inventory_inbound_history).

기존 자재 선택 또는 신규 코드 입력 + 수량/단위/메모로 입고를 등록한다.
표현/입력만 담당하고 영속화(누적 가산 + 이력 기록)는 DataManager에 위임한다.
"""
from typing import List, Dict

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QPushButton,
    QLineEdit, QComboBox, QMessageBox,
)
from PySide6.QtGui import QDoubleValidator

from utils.logger import logger
from ui.styles import UIStyles, UITheme


class InboundDialog(QDialog):
    """자재 입고 등록 다이얼로그."""

    def __init__(self, data_manager, parent=None):
        super().__init__(parent)
        self.data_manager = data_manager
        self._stock_rows: List[Dict] = []
        self.setWindowTitle("입고 등록")
        self.setMinimumWidth(420)
        try:
            self.setStyleSheet(UIStyles.get_dialog_style())
        except Exception:  # noqa: BLE001 — 스타일 누락 시 기본 스타일로 표시
            pass
        self._init_ui()
        self._load_materials()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(12)

        title = QLabel("자재 입고(매입) 등록")
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

        self.qty_edit = QLineEdit()
        self.qty_edit.setValidator(QDoubleValidator(0.0, 1e12, 3, self))
        self._apply_input_style(self.qty_edit)
        form.addRow(self._label("입고 수량"), self.qty_edit)

        self.unit_edit = QLineEdit("g")
        self._apply_input_style(self.unit_edit)
        form.addRow(self._label("단위"), self.unit_edit)

        self.note_edit = QLineEdit()
        self.note_edit.setPlaceholderText("매입처 / LOT / 사유 등 (선택)")
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

    # ------------------------------------------------------------------
    # 데이터
    # ------------------------------------------------------------------

    def _load_materials(self) -> None:
        try:
            self._stock_rows = self.data_manager.get_all_material_stock() or []
        except Exception as e:  # noqa: BLE001 — 다이얼로그 안정성 우선
            logger.error(f"입고 다이얼로그 자재 로드 실패: {e}", exc_info=True)
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
        unit = self.unit_edit.text().strip() or "g"
        note = self.note_edit.text().strip()
        qty = self._parse_num(self.qty_edit.text())
        if not code:
            QMessageBox.warning(self, "입력 확인", "자재 코드(또는 자재명)를 입력하세요.")
            return
        if qty <= 0:
            QMessageBox.warning(self, "입력 확인", "입고 수량은 0보다 커야 합니다.")
            return
        try:
            ok = self.data_manager.add_inbound(code, name, qty, unit, note)
        except Exception as e:  # noqa: BLE001
            logger.error(f"입고 등록 실패: {e}", exc_info=True)
            ok = False
        if not ok:
            QMessageBox.warning(self, "등록 실패", "입고 등록 중 오류가 발생했습니다.")
            return
        logger.info(f"입고 등록 완료: {code} +{qty}{unit}")
        QMessageBox.information(self, "등록 완료", f"{name} {qty}{unit} 입고를 등록했습니다.")
        self.accept()

    # ------------------------------------------------------------------
    # 헬퍼
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_num(text: str) -> float:
        try:
            value = float(str(text).replace(",", "").strip())
        except (TypeError, ValueError):
            return 0.0
        return max(0.0, value)
