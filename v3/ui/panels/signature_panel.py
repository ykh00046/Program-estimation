from PySide6.QtWidgets import QWidget, QHBoxLayout, QCheckBox

class SignaturePanel(QWidget):
    """서명 옵션을 관리하는 패널"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self):
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0) # 여백 제거
        self.setLayout(layout)

        self.chk_charge = QCheckBox('작업자 서명')
        self.chk_charge.setChecked(True)
        layout.addWidget(self.chk_charge)

        self.chk_review = QCheckBox('검토 서명')
        self.chk_review.setChecked(True)
        layout.addWidget(self.chk_review)

        self.chk_approve = QCheckBox('승인 서명')
        self.chk_approve.setChecked(True)
        layout.addWidget(self.chk_approve)

        layout.addStretch()

    def get_data(self) -> dict:
        """서명 포함 여부 데이터 반환"""
        return {
            'charge': self.chk_charge.isChecked(),
            'review': self.chk_review.isChecked(),
            'approve': self.chk_approve.isChecked(),
        }

    def set_data(self, data: dict) -> None:
        """외부 상태로부터 서명 옵션을 적용합니다."""
        if not data:
            return
        self.chk_charge.setChecked(bool(data.get("charge", self.chk_charge.isChecked())))
        self.chk_review.setChecked(bool(data.get("review", self.chk_review.isChecked())))
        self.chk_approve.setChecked(bool(data.get("approve", self.chk_approve.isChecked())))
