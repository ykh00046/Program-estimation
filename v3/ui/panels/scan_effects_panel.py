from PySide6.QtWidgets import (
    QWidget, QGridLayout, QLabel, QSpinBox, 
    QDoubleSpinBox, QPushButton, QHBoxLayout, QMessageBox
)
from config.config_manager import config
from utils.logger import logger

class ScanEffectsPanel(QWidget):
    """PDF 스캔 효과 설정을 담당하는 패널"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()
        self._load_defaults()

    def _init_ui(self):
        layout = QGridLayout()
        self.setLayout(layout)
        
        # 그룹박스 내부가 아닌, 패널 자체가 그룹박스 역할을 하거나
        # 메인윈도우에서 그룹박스를 생성하고 이 패널을 넣을 수 있음.
        # 여기서는 패널이 컨텐츠만 제공하도록 함.

        # DPI
        layout.addWidget(QLabel("해상도 (DPI):"), 0, 0)
        self.dpi_spin = QSpinBox()
        self.dpi_spin.setRange(100, 600)
        self.dpi_spin.setSingleStep(50)
        layout.addWidget(self.dpi_spin, 0, 1)
        
        # 노이즈
        layout.addWidget(QLabel("노이즈 (잡음):"), 0, 2)
        self.noise_spin = QSpinBox()
        self.noise_spin.setRange(0, 100)
        layout.addWidget(self.noise_spin, 0, 3)
        
        # 블러
        layout.addWidget(QLabel("블러 (흐림):"), 1, 0)
        self.blur_spin = QDoubleSpinBox()
        self.blur_spin.setRange(0.0, 5.0)
        self.blur_spin.setSingleStep(0.1)
        layout.addWidget(self.blur_spin, 1, 1)

        # 대비
        layout.addWidget(QLabel("대비:"), 1, 2)
        self.contrast_spin = QDoubleSpinBox()
        self.contrast_spin.setRange(0.5, 2.0)
        self.contrast_spin.setSingleStep(0.01)
        layout.addWidget(self.contrast_spin, 1, 3)

        # 밝기
        layout.addWidget(QLabel("밝기:"), 2, 0)
        self.brightness_spin = QDoubleSpinBox()
        self.brightness_spin.setRange(0.5, 2.0)
        layout.addWidget(self.brightness_spin, 2, 1)
        
        # Buttons layout (Horizontal)
        buttons_row_layout = QHBoxLayout()
        reset_btn = QPushButton("효과 기본값 복원")
        reset_btn.clicked.connect(self.reset_defaults)
        buttons_row_layout.addWidget(reset_btn)

        save_as_default_btn = QPushButton("현재 설정을 기본값으로 저장")
        save_as_default_btn.clicked.connect(self._save_as_default)
        buttons_row_layout.addWidget(save_as_default_btn)
        buttons_row_layout.addStretch() # Push buttons to left
        
        layout.addLayout(buttons_row_layout, 3, 0, 1, 4)

    def _load_defaults(self):
        """초기 로드 시 기본값 적용"""
        self.reset_defaults()

    def reset_defaults(self):
        """스캔 효과 파라미터를 config.json의 기본값으로 리셋합니다."""
        defaults = config.scan_effects
        self.dpi_spin.setValue(defaults.get("dpi", 250))
        self.blur_spin.setValue(defaults.get("blur_radius", 0.3))
        self.noise_spin.setValue(defaults.get("noise_range", 25))
        self.contrast_spin.setValue(defaults.get("contrast_factor", 1.4))
        self.brightness_spin.setValue(defaults.get("brightness_factor", 1.10))
        logger.info("PDF 스캔 효과가 기본값으로 복원되었습니다.")

    def get_data(self) -> dict:
        """현재 설정된 파라미터 반환"""
        return {
            "dpi": self.dpi_spin.value(),
            "blur_radius": self.blur_spin.value(),
            "noise_range": self.noise_spin.value(),
            "contrast_factor": self.contrast_spin.value(),
            "brightness_factor": self.brightness_spin.value()
        }

    def set_data(self, data: dict) -> None:
        """외부 상태로부터 파라미터를 적용합니다."""
        if not data:
            return
        self.dpi_spin.setValue(int(data.get("dpi", self.dpi_spin.value())))
        self.blur_spin.setValue(float(data.get("blur_radius", self.blur_spin.value())))
        self.noise_spin.setValue(int(data.get("noise_range", self.noise_spin.value())))
        self.contrast_spin.setValue(float(data.get("contrast_factor", self.contrast_spin.value())))
        self.brightness_spin.setValue(float(data.get("brightness_factor", self.brightness_spin.value())))

    def _save_as_default(self):
        """현재 설정을 기본값으로 저장"""
        try:
            reply = QMessageBox.question(self, "기본값 저장 확인",
                                       "현재 스캔 효과 설정을 새로운 기본값으로 저장하시겠습니까?\n"
                                       "프로그램을 다시 시작하면 이 설정이 기본으로 적용됩니다.",
                                       QMessageBox.Yes | QMessageBox.No, QMessageBox.No)

            if reply == QMessageBox.Yes:
                current_effects = self.get_data()
                
                if config.save_scan_effects(current_effects):
                    # MainWindow의 statusBar에 접근할 수 없으므로 메시지박스로 대체하거나 
                    # signal을 통해 부모에게 알릴 수 있음. 여기선 메시지박스 사용.
                    QMessageBox.information(self, "저장 완료", "새로운 스캔 효과 설정이 기본값으로 저장되었습니다.")
                    logger.info(f"스캔 효과 기본값 업데이트 성공: {current_effects}")
                else:
                    raise IOError("config.json 파일 쓰기에 실패했습니다.")
        except Exception as e:
            logger.error(f"스캔 효과 기본값 저장 오류: {e}")
            QMessageBox.critical(self, "저장 실패", f"설정을 저장하는 중 오류가 발생했습니다.\n{e}")

