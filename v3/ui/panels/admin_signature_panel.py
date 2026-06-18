"""
관리자 모드용 서명 품질/위치 설정 패널.
signature_qa_tool의 기능을 이식하여 통합 관리할 수 있도록 함.
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, 
    QSpinBox, QDoubleSpinBox, QPushButton, QComboBox, 
    QScrollArea, QGroupBox, QMessageBox, QProgressBar, QSplitter
)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QPixmap, QImage
import io
import os
from config.config_manager import config
from config.settings import BASE_PATH
from utils.logger import logger
from ui.styles import UITheme

# signature_qa_tool의 Generator 로직 재사용
from signature_qa_tool.processing.generator import SignatureGenerator

class MockQAConfig:
    """QAConfig 의존성 제거를 위한 Mock 클래스"""
    def __init__(self):
        self.default_num_variations = 6
        self.grid_columns = 3
        self.output_directory = os.path.join(BASE_PATH, "signature_qa_tool", "output")
        self.base_document_path = os.path.join(BASE_PATH, "resources", "signature", "image.jpeg")
        os.makedirs(self.output_directory, exist_ok=True)

    def get_signature_config(self):
        """서명 설정 반환"""
        return config.get('signature', {})

    def get_resources_path(self):
        """리소스 경로 반환"""
        return os.path.dirname(self.base_document_path)

    def get_workers(self):
        """작업자 목록 반환"""
        return config.workers

class GenerationWorker(QThread):
    """서명 생성 워커 스레드"""
    finished = Signal(list)
    progress = Signal(int)

    def __init__(self, generator, worker_name, num_variations, params):
        super().__init__()
        self.generator = generator
        self.worker_name = worker_name
        self.num_variations = num_variations
        self.params = params

    def run(self):
        images = []
        for i in range(self.num_variations):
            image = self.generator.generate_composite_image(self.worker_name, self.params)
            images.append(image)
            self.progress.emit(int((i + 1) / self.num_variations * 100))
        self.finished.emit(images)

class SignatureSettingsPanel(QWidget):
    """서명 품질 및 위치 설정을 위한 통합 패널"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.qa_config = MockQAConfig()
        self.generator = SignatureGenerator(self.qa_config)
        self.current_images = []
        self.selected_image_index = None
        
        self._init_ui()
        self._load_current_config()

    def _init_ui(self):
        main_layout = QHBoxLayout(self)
        splitter = QSplitter(Qt.Horizontal)

        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.addWidget(self._build_position_group())
        left_layout.addWidget(self._build_quality_group())
        left_layout.addWidget(self._build_test_group())
        splitter.addWidget(left_panel)

        splitter.addWidget(self._build_preview_panel())
        splitter.setSizes([400, 600])
        main_layout.addWidget(splitter)

    def _build_position_group(self) -> QGroupBox:
        """서명 위치 설정 그룹 (charge/review/approve X·Y)."""
        pos_group = QGroupBox("서명 위치 설정 (좌표: X, Y)")
        pos_layout = QHBoxLayout()

        self.pos_controls = {}
        for key in ['charge', 'review', 'approve']:
            v_box = QVBoxLayout()
            v_box.addWidget(QLabel(key.upper()))

            h_box = QHBoxLayout()
            x_spin = QSpinBox()
            x_spin.setRange(0, 1000)
            x_spin.setToolTip(f"{key} X 좌표")

            y_spin = QSpinBox()
            y_spin.setRange(0, 1000)
            y_spin.setToolTip(f"{key} Y 좌표")

            h_box.addWidget(x_spin)
            h_box.addWidget(y_spin)
            v_box.addLayout(h_box)

            pos_layout.addLayout(v_box)
            self.pos_controls[key] = (x_spin, y_spin)

        pos_group.setLayout(pos_layout)
        return pos_group

    def _build_quality_group(self) -> QGroupBox:
        """서명 품질 파라미터 그룹 (QA Tool 이식 + Randomization)."""
        qa_group = QGroupBox("서명 품질 파라미터")
        qa_scroll = QScrollArea()
        qa_scroll.setWidgetResizable(True)
        qa_widget = QWidget()
        qa_layout = QVBoxLayout(qa_widget)

        self.param_controls = {}
        self.param_controls['gaussian_blur_sigma'] = self._add_double_param(
            qa_layout, "Gaussian Blur:", 0.0, 5.0, 0.1, "흐림 정도 (부드럽게)")
        self.param_controls['pressure_noise_strength'] = self._add_double_param(
            qa_layout, "Pressure Noise:", 0.0, 0.5, 0.01, "필압 노이즈 (거칠게)")
        self.param_controls['ink_alpha_factor'] = self._add_double_param(
            qa_layout, "Ink Alpha:", 1.0, 3.0, 0.1, "잉크 진하기 (불투명도)")
        self.param_controls['signature_brightness_factor'] = self._add_double_param(
            qa_layout, "Brightness:", 0.5, 2.0, 0.05, "밝기 조절")
        self.param_controls['final_contrast_factor'] = self._add_double_param(
            qa_layout, "Contrast:", 0.5, 2.0, 0.1, "대비 조절 (선명하게)")

        rand_group = QGroupBox("Randomization (무작위 변형)")
        rand_layout = QVBoxLayout()
        self.param_controls['rotation_angle'] = self._add_int_param(
            rand_layout, "Rotation (±):", 0, 30, "회전 각도 범위")
        self.param_controls['scale_min'] = self._add_double_param(
            rand_layout, "Scale Min:", 0.5, 1.0, 0.01, "최소 크기 비율")
        self.param_controls['scale_max'] = self._add_double_param(
            rand_layout, "Scale Max:", 0.5, 1.0, 0.01, "최대 크기 비율")
        rand_group.setLayout(rand_layout)
        qa_layout.addWidget(rand_group)

        qa_scroll.setWidget(qa_widget)
        qa_group.setLayout(QVBoxLayout())
        qa_group.layout().addWidget(qa_scroll)
        return qa_group

    def _build_test_group(self) -> QGroupBox:
        """테스트 실행 그룹 (작업자 선택 + 생성/저장 버튼)."""
        test_group = QGroupBox("테스트 실행")
        test_layout = QVBoxLayout()

        worker_layout = QHBoxLayout()
        worker_layout.addWidget(QLabel("작업자:"))
        self.worker_combo = QComboBox()
        self.worker_combo.addItems(config.workers)
        worker_layout.addWidget(self.worker_combo)
        test_layout.addLayout(worker_layout)

        self.generate_btn = QPushButton("설정값으로 테스트 생성")
        self.generate_btn.clicked.connect(self._generate_test)
        test_layout.addWidget(self.generate_btn)

        self.save_config_btn = QPushButton("현재 설정을 저장")
        self.save_config_btn.clicked.connect(self._save_to_config)
        test_layout.addWidget(self.save_config_btn)

        test_group.setLayout(test_layout)
        return test_group

    def _build_preview_panel(self) -> QWidget:
        """우측 미리보기 패널 (이미지 그리드 + 진행바)."""
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.addWidget(QLabel("<b>미리보기 결과</b>"))

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.image_container = QWidget()
        self.image_grid = QGridLayout(self.image_container)
        self.scroll_area.setWidget(self.image_container)
        right_layout.addWidget(self.scroll_area)

        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        right_layout.addWidget(self.progress_bar)
        return right_panel

    def _add_double_param(self, layout, label, min_val, max_val, step, tooltip=""):
        lbl = QLabel(label)
        if tooltip:
            lbl.setToolTip(tooltip)
            lbl.setText(f"{label} <small style='color:gray'>({tooltip})</small>")
        layout.addWidget(lbl)
        
        spin = QDoubleSpinBox()
        spin.setRange(min_val, max_val)
        spin.setSingleStep(step)
        spin.setDecimals(2)
        if tooltip:
            spin.setToolTip(tooltip)
        layout.addWidget(spin)
        return spin

    def _add_int_param(self, layout, label, min_val, max_val, tooltip=""):
        lbl = QLabel(label)
        if tooltip:
            lbl.setToolTip(tooltip)
            lbl.setText(f"{label} <small style='color:gray'>({tooltip})</small>")
        layout.addWidget(lbl)
        
        spin = QSpinBox()
        spin.setRange(min_val, max_val)
        if tooltip:
            spin.setToolTip(tooltip)
        layout.addWidget(spin)
        return spin

    def _load_current_config(self):
        """현재 config.json 값을 로드하여 UI에 반영"""
        # 1. 위치 설정 로드
        positions = config.get('signature', {}).get('positions', {})
        defaults = {'charge': [160, 57], 'review': [222, 54], 'approve': [288, 53]}
        
        for key, (x_spin, y_spin) in self.pos_controls.items():
            pos = positions.get(key, defaults[key])
            x_spin.setValue(pos[0])
            y_spin.setValue(pos[1])
            
        # 2. 품질 파라미터 로드
        sig_cfg = config.get('signature', {})
        self.param_controls['gaussian_blur_sigma'].setValue(sig_cfg.get('gaussian_blur_sigma', 0.7))
        self.param_controls['pressure_noise_strength'].setValue(sig_cfg.get('pressure_noise_strength', 0.0))
        self.param_controls['ink_alpha_factor'].setValue(sig_cfg.get('ink_alpha_factor', 1.5))
        self.param_controls['signature_brightness_factor'].setValue(sig_cfg.get('signature_brightness_factor', 1.25))
        self.param_controls['final_contrast_factor'].setValue(sig_cfg.get('final_contrast_factor', 1.4))
        
        rand_cfg = sig_cfg.get('randomization', {})
        self.param_controls['rotation_angle'].setValue(rand_cfg.get('rotation_angle', 8))
        self.param_controls['scale_min'].setValue(rand_cfg.get('scale_min', 0.95))
        self.param_controls['scale_max'].setValue(rand_cfg.get('scale_max', 0.98))

    def _get_ui_params(self):
        """UI에서 현재 설정값을 읽어옴"""
        params = {
            'gaussian_blur_sigma': self.param_controls['gaussian_blur_sigma'].value(),
            'pressure_noise_strength': self.param_controls['pressure_noise_strength'].value(),
            'ink_alpha_factor': self.param_controls['ink_alpha_factor'].value(),
            'signature_brightness_factor': self.param_controls['signature_brightness_factor'].value(),
            'final_contrast_factor': self.param_controls['final_contrast_factor'].value(),
            'randomization': {
                'rotation_angle': self.param_controls['rotation_angle'].value(),
                'scale_min': self.param_controls['scale_min'].value(),
                'scale_max': self.param_controls['scale_max'].value(),
                # Offset은 UI에서 단순화 위해 생략했으므로 기본값 유지하거나 추가 필요. 여기선 기본값 유지
                'offset_x': 1, 'offset_y': 2 
            },
            # 위치 설정도 포함 (Generator에는 직접 안쓰이지만 config 저장용)
            'positions': {
                key: [spin[0].value(), spin[1].value()] 
                for key, spin in self.pos_controls.items()
            }
        }
        return params

    def _generate_test(self):
        """현재 UI 설정값으로 서명 생성 테스트"""
        worker_name = self.worker_combo.currentText()
        if not worker_name:
            QMessageBox.warning(self, "경고", "작업자를 선택하세요.")
            return

        params = self._get_ui_params()
        
        # 버튼 비활성화
        self.generate_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        
        # 워커 시작 (4개 생성)
        self.worker = GenerationWorker(self.generator, worker_name, 4, params)
        self.worker.progress.connect(self.progress_bar.setValue)
        self.worker.finished.connect(self._on_generation_finished)
        self.worker.start()

    def _on_generation_finished(self, images):
        """생성 완료 처리"""
        self.current_images = images
        self._display_images(images)
        self.generate_btn.setEnabled(True)
        self.progress_bar.setVisible(False)

    def _display_images(self, images):
        """이미지 그리드 표시"""
        # 기존 위젯 제거
        while self.image_grid.count():
            item = self.image_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
                
        # 새 이미지 추가 (2열 배치)
        cols = 2
        for i, pil_image in enumerate(images):
            row = i // cols
            col = i % cols
            
            # PIL -> QPixmap
            buffer = io.BytesIO()
            pil_image.save(buffer, format='PNG')
            buffer.seek(0)
            qimage = QImage()
            qimage.loadFromData(buffer.read())
            pixmap = QPixmap.fromImage(qimage)
            
            lbl = QLabel()
            lbl.setPixmap(pixmap.scaled(250, 200, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            lbl.setFrameStyle(1)
            lbl.setStyleSheet(f"border: 1px solid {UITheme.BORDER_COLOR};")
            
            self.image_grid.addWidget(lbl, row, col)

    def _save_to_config(self):
        """현재 UI 설정값을 config.json에 저장"""
        try:
            params = self._get_ui_params()
            
            # 기존 config 로드
            current_sig_config = config.get('signature', {})
            
            # 값 업데이트
            current_sig_config.update(params)
            current_sig_config['positions'] = params['positions']
            
            # config 객체에 반영 및 저장
            config._data['signature'] = current_sig_config
            config._save_config()
            
            QMessageBox.information(self, "저장 완료", "서명 품질 및 위치 설정이 저장되었습니다.")
            logger.info("관리자 모드: 서명 설정 업데이트 및 저장 완료")
            
        except Exception as e:
            logger.error(f"설정 저장 실패: {e}")
            QMessageBox.critical(self, "저장 실패", f"설정 저장 중 오류가 발생했습니다.\n{e}")
