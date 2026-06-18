"""
PDF/서명 설정 다이얼로그
"""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QDialogButtonBox
)
from PySide6.QtCore import Qt
from ui.panels.scan_effects_panel import ScanEffectsPanel
from ui.panels.signature_panel import SignaturePanel
from ui.components import create_group_box


class PdfSignatureSettingsDialog(QDialog):
    """PDF 스캔 효과 및 서명 옵션 설정 다이얼로그"""

    def __init__(self, scan_effects_panel: ScanEffectsPanel, 
                 signature_panel: SignaturePanel, parent=None):
        super().__init__(parent)
        self.setWindowTitle("PDF/서명 설정")
        self.setModal(False)  # 모달리스 (다른 작업 가능)
        self.setMinimumWidth(500)
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)
        
        # 패널 참조 저장 (MainWindow의 패널 재사용)
        self.scan_effects_panel = scan_effects_panel
        self.signature_panel = signature_panel
        
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout()
        
        # 스캔 효과 패널
        scan_group = create_group_box("PDF 스캔 효과", self.scan_effects_panel)
        layout.addWidget(scan_group)
        
        # 서명 옵션 패널
        sig_group = create_group_box("서명 옵션", self.signature_panel)
        layout.addWidget(sig_group)
        
        layout.addStretch()
        
        # 닫기 버튼
        btn_box = QDialogButtonBox(QDialogButtonBox.Close)
        btn_box.rejected.connect(self.close)
        layout.addWidget(btn_box)
        
        self.setLayout(layout)
