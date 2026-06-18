# -*- coding: utf-8 -*-
"""
PDF 프로세서 메인 윈도우
"""
import os
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QLabel, QLineEdit, QPushButton, QFileDialog, QDoubleSpinBox,
    QSpinBox, QProgressBar, QTextEdit, QMessageBox
)
import sys
# 상위 디렉토리 경로 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from worker import ConversionWorker
from config.config_manager import config


class MainWindow(QMainWindow):
    """PDF 프로세서 메인 윈도우"""

    def __init__(self):
        super().__init__()
        self.worker = None
        self.init_ui()

    def init_ui(self):
        """UI 초기화"""
        self.setWindowTitle("PDF 프로세서 - 스캔 효과 적용")
        self.setGeometry(200, 200, 800, 700)

        # 중앙 위젯
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # 1. 입력 섹션
        input_group = QGroupBox("입력 파일")
        input_layout = QHBoxLayout()

        input_layout.addWidget(QLabel("엑셀 파일:"))
        self.input_path_edit = QLineEdit()
        self.input_path_edit.setReadOnly(True)
        self.input_path_edit.setPlaceholderText("변환할 엑셀 파일을 선택하세요...")
        input_layout.addWidget(self.input_path_edit)

        self.select_input_btn = QPushButton("파일 선택...")
        self.select_input_btn.clicked.connect(self.select_input_file)
        input_layout.addWidget(self.select_input_btn)

        input_group.setLayout(input_layout)
        main_layout.addWidget(input_group)

        # 2. 효과 제어 섹션
        effects_group = QGroupBox("스캔 효과 제어")
        effects_layout = QVBoxLayout()

        # DPI
        dpi_layout = QHBoxLayout()
        dpi_layout.addWidget(QLabel("해상도 (DPI):"))
        self.dpi_spin = QSpinBox()
        self.dpi_spin.setRange(100, 600)
        self.dpi_spin.setSingleStep(50)
        self.dpi_spin.setSuffix(" dpi")
        dpi_layout.addWidget(self.dpi_spin)
        dpi_layout.addStretch()
        effects_layout.addLayout(dpi_layout)
        
        # 블러
        blur_layout = QHBoxLayout()
        blur_layout.addWidget(QLabel("블러 (흐림):"))
        self.blur_spin = QDoubleSpinBox()
        self.blur_spin.setRange(0.0, 5.0)
        self.blur_spin.setSingleStep(0.1)
        self.blur_spin.setToolTip("값이 클수록 이미지가 더 흐릿해집니다")
        blur_layout.addWidget(self.blur_spin)
        blur_layout.addStretch()
        effects_layout.addLayout(blur_layout)

        # 노이즈
        noise_layout = QHBoxLayout()
        noise_layout.addWidget(QLabel("노이즈 (잡음):"))
        self.noise_spin = QSpinBox()
        self.noise_spin.setRange(0, 100)
        self.noise_spin.setToolTip("값이 클수록 더 많은 잡음이 추가됩니다")
        noise_layout.addWidget(self.noise_spin)
        noise_layout.addStretch()
        effects_layout.addLayout(noise_layout)

        # 대비
        contrast_layout = QHBoxLayout()
        contrast_layout.addWidget(QLabel("대비:"))
        self.contrast_spin = QDoubleSpinBox()
        self.contrast_spin.setRange(0.5, 2.0)
        self.contrast_spin.setSingleStep(0.01)
        self.contrast_spin.setToolTip("1.0 = 원본, 1.0 초과 = 대비 증가, 1.0 미만 = 대비 감소")
        contrast_layout.addWidget(self.contrast_spin)
        contrast_layout.addStretch()
        effects_layout.addLayout(contrast_layout)

        # 밝기
        brightness_layout = QHBoxLayout()
        brightness_layout.addWidget(QLabel("밝기:"))
        self.brightness_spin = QDoubleSpinBox()
        self.brightness_spin.setRange(0.5, 2.0)
        self.brightness_spin.setSingleStep(0.01)
        self.brightness_spin.setToolTip("1.0 = 원본, 1.0 초과 = 밝게, 1.0 미만 = 어둡게")
        brightness_layout.addWidget(self.brightness_spin)
        brightness_layout.addStretch()
        effects_layout.addLayout(brightness_layout)

        # 기본값 복원 버튼
        reset_btn = QPushButton("기본값 복원")
        reset_btn.clicked.connect(self.reset_defaults)
        effects_layout.addWidget(reset_btn)

        effects_group.setLayout(effects_layout)
        main_layout.addWidget(effects_group)

        # 3. 출력 섹션
        output_group = QGroupBox("출력 파일")
        output_layout = QHBoxLayout()

        output_layout.addWidget(QLabel("저장 위치:"))
        self.output_path_edit = QLineEdit()
        self.output_path_edit.setReadOnly(True)
        self.output_path_edit.setPlaceholderText("PDF 저장 위치를 선택하세요...")
        output_layout.addWidget(self.output_path_edit)

        self.select_output_btn = QPushButton("저장 위치...")
        self.select_output_btn.clicked.connect(self.select_output_file)
        output_layout.addWidget(self.select_output_btn)

        output_group.setLayout(output_layout)
        main_layout.addWidget(output_group)

        # 4. 실행 및 상태 섹션
        action_group = QGroupBox("실행")
        action_layout = QVBoxLayout()

        # 시작 버튼
        self.start_btn = QPushButton("PDF 생성 시작")
        self.start_btn.setMinimumHeight(40)
        self.start_btn.clicked.connect(self.start_conversion)
        self.start_btn.setEnabled(False)
        action_layout.addWidget(self.start_btn)

        # 진행률 표시
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        action_layout.addWidget(self.progress_bar)

        # 로그 메시지
        log_label = QLabel("작업 로그:")
        action_layout.addWidget(log_label)

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(150)
        action_layout.addWidget(self.log_text)

        action_group.setLayout(action_layout)
        main_layout.addWidget(action_group)

        # 상태바
        self.statusBar().showMessage("준비")
        self.reset_defaults()

    def select_input_file(self):
        """입력 엑셀 파일 선택"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "엑셀 파일 선택",
            "",
            "Excel Files (*.xlsx *.xls);;All Files (*)"
        )

        if file_path:
            self.input_path_edit.setText(file_path)
            self.log(f"입력 파일 선택됨: {os.path.basename(file_path)}")

            # 자동으로 출력 경로 제안
            if not self.output_path_edit.text():
                base_name = os.path.splitext(os.path.basename(file_path))[0]
                output_dir = os.path.dirname(file_path)
                suggested_path = os.path.join(output_dir, f"{base_name}_scanned.pdf")
                self.output_path_edit.setText(suggested_path)

            self.check_ready()

    def select_output_file(self):
        """출력 PDF 파일 위치 선택"""
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "PDF 저장 위치 선택",
            "",
            "PDF Files (*.pdf);;All Files (*)"
        )

        if file_path:
            if not file_path.endswith('.pdf'):
                file_path += '.pdf'
            self.output_path_edit.setText(file_path)
            self.log(f"출력 파일 경로 설정됨: {os.path.basename(file_path)}")
            self.check_ready()

    def reset_defaults(self):
        """기본값 복원"""
        defaults = config.scan_effects
        self.dpi_spin.setValue(defaults.get("dpi", 250))
        self.blur_spin.setValue(defaults.get("blur_radius", 1.3))
        self.noise_spin.setValue(defaults.get("noise_range", 30))
        self.contrast_spin.setValue(defaults.get("contrast_factor", 1.4))
        self.brightness_spin.setValue(defaults.get("brightness_factor", 0.95))
        self.log("효과 파라미터가 기본값으로 복원되었습니다.")

    def check_ready(self):
        """시작 버튼 활성화 여부 확인"""
        input_ready = bool(self.input_path_edit.text())
        output_ready = bool(self.output_path_edit.text())
        self.start_btn.setEnabled(input_ready and output_ready)

    def start_conversion(self):
        """변환 시작"""
        # UI 비활성화
        self.set_ui_enabled(False)
        self.progress_bar.setValue(0)
        self.log("=" * 50)
        self.log("PDF 변환 작업을 시작합니다...")

        # 워커 스레드 생성 및 시작
        self.worker = ConversionWorker(
            self.input_path_edit.text(),
            self.output_path_edit.text(),
            self.blur_spin.value(),
            self.noise_spin.value(),
            self.contrast_spin.value(),
            self.brightness_spin.value(),
            dpi=self.dpi_spin.value()
        )

        # 시그널 연결
        self.worker.progress_updated.connect(self.on_progress_updated)
        self.worker.finished.connect(self.on_conversion_finished)

        # 워커 시작
        self.worker.start()
        self.statusBar().showMessage("변환 중...")

    def on_progress_updated(self, progress, message):
        """진행 상황 업데이트"""
        self.progress_bar.setValue(progress)
        self.log(message)

    def on_conversion_finished(self, success, message):
        """변환 완료"""
        self.log(message)
        self.log("=" * 50)

        # UI 재활성화
        self.set_ui_enabled(True)

        if success:
            self.statusBar().showMessage("변환 완료!")
            QMessageBox.information(
                self,
                "변환 완료",
                f"PDF 변환이 성공적으로 완료되었습니다!\n\n{message}"
            )
        else:
            self.statusBar().showMessage("변환 실패")
            QMessageBox.critical(
                self,
                "변환 실패",
                f"PDF 변환 중 오류가 발생했습니다:\n\n{message}"
            )

    def set_ui_enabled(self, enabled):
        """UI 활성화/비활성화"""
        self.select_input_btn.setEnabled(enabled)
        self.select_output_btn.setEnabled(enabled)
        self.start_btn.setEnabled(enabled)
        self.dpi_spin.setEnabled(enabled)
        self.blur_spin.setEnabled(enabled)
        self.noise_spin.setEnabled(enabled)
        self.contrast_spin.setEnabled(enabled)
        self.brightness_spin.setEnabled(enabled)

    def log(self, message):
        """로그 메시지 추가"""
        self.log_text.append(message)
        # 자동 스크롤
        self.log_text.verticalScrollBar().setValue(
            self.log_text.verticalScrollBar().maximum()
        )