"""
Main GUI window for the Signature QA Tool.

Provides parameter controls, image display, and action buttons for
signature generation and evaluation.
"""
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QSpinBox, QDoubleSpinBox, QPushButton, QComboBox,
    QScrollArea, QGroupBox, QMessageBox, QProgressBar
)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QPixmap, QImage
import io


class GenerationWorker(QThread):
    """Worker thread for signature generation to prevent UI freezing."""

    finished = Signal(list)
    progress = Signal(int)

    def __init__(self, generator, worker_name, num_variations, params):
        super().__init__()
        self.generator = generator
        self.worker_name = worker_name
        self.num_variations = num_variations
        self.params = params

    def run(self):
        """Run the generation process."""
        images = []
        for i in range(self.num_variations):
            image = self.generator.generate_composite_image(self.worker_name, self.params)
            images.append(image)
            self.progress.emit(int((i + 1) / self.num_variations * 100))

        self.finished.emit(images)


class MainWindow(QMainWindow):
    """Main window for the Signature QA Tool."""

    def __init__(self, qa_config):
        super().__init__()
        self.qa_config = qa_config

        # Import generator
        from signature_qa_tool.processing.generator import SignatureGenerator
        self.generator = SignatureGenerator(qa_config)

        # Store generated images
        self.current_images = []
        self.selected_image_index = None

        self.init_ui()

    def init_ui(self):
        """Initialize the user interface."""
        self.setWindowTitle("Signature QA Tool")
        self.setGeometry(100, 100, 1400, 900)

        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)

        # Left panel: Parameter controls
        left_panel = self.create_control_panel()
        main_layout.addWidget(left_panel, stretch=1)

        # Right panel: Image display
        right_panel = self.create_display_panel()
        main_layout.addWidget(right_panel, stretch=3)

    def create_control_panel(self):
        """Create the left control panel with parameter controls."""
        panel = QWidget()
        layout = QVBoxLayout(panel)

        # Worker selection
        worker_group = QGroupBox("Worker Selection")
        worker_layout = QVBoxLayout()
        self.worker_combo = QComboBox()
        self.worker_combo.addItems(self.qa_config.get_workers())
        worker_layout.addWidget(QLabel("Select Worker:"))
        worker_layout.addWidget(self.worker_combo)
        worker_group.setLayout(worker_layout)
        layout.addWidget(worker_group)

        # Number of variations
        variation_group = QGroupBox("Generation Settings")
        variation_layout = QVBoxLayout()
        self.num_variations_spin = QSpinBox()
        self.num_variations_spin.setRange(1, 12)
        self.num_variations_spin.setValue(self.qa_config.default_num_variations)
        variation_layout.addWidget(QLabel("Number of Variations:"))
        variation_layout.addWidget(self.num_variations_spin)
        variation_group.setLayout(variation_layout)
        layout.addWidget(variation_group)

        # ImageProcessor Parameters
        params_group = QGroupBox("ImageProcessor Parameters")
        params_layout = QVBoxLayout()

        # Scroll area for parameters
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)

        # Get default config
        sig_config = self.qa_config.get_signature_config()

        # Create parameter controls
        self.param_controls = {}

        # Gaussian Blur Sigma
        self.param_controls['gaussian_blur_sigma'] = self.add_double_param(
            scroll_layout, "Gaussian Blur Sigma:",
            sig_config.get('gaussian_blur_sigma', 0.7), 0.0, 5.0, 0.1
        )

        # Pressure Noise Strength
        self.param_controls['pressure_noise_strength'] = self.add_double_param(
            scroll_layout, "Pressure Noise Strength:",
            sig_config.get('pressure_noise_strength', 0.0), 0.0, 0.5, 0.01
        )

        # Ink Alpha Factor
        self.param_controls['ink_alpha_factor'] = self.add_double_param(
            scroll_layout, "Ink Alpha Factor:",
            sig_config.get('ink_alpha_factor', 1.5), 1.0, 3.0, 0.1
        )

        # Signature Brightness Factor
        self.param_controls['signature_brightness_factor'] = self.add_double_param(
            scroll_layout, "Brightness Factor:",
            sig_config.get('signature_brightness_factor', 1.25), 0.5, 2.0, 0.05
        )

        # Final Contrast Factor
        self.param_controls['final_contrast_factor'] = self.add_double_param(
            scroll_layout, "Final Contrast Factor:",
            sig_config.get('final_contrast_factor', 1.4), 0.5, 2.0, 0.1
        )

        # Randomization - Rotation Angle
        rand_config = sig_config.get('randomization', {})
        self.param_controls['rotation_angle'] = self.add_int_param(
            scroll_layout, "Rotation Angle Range (±):",
            rand_config.get('rotation_angle', 8), 0, 30
        )

        # Randomization - Offset X
        self.param_controls['offset_x'] = self.add_int_param(
            scroll_layout, "Offset X Range (±):",
            rand_config.get('offset_x', 1), 0, 20
        )

        # Randomization - Offset Y
        self.param_controls['offset_y'] = self.add_int_param(
            scroll_layout, "Offset Y Range (±):",
            rand_config.get('offset_y', 2), 0, 20
        )

        # Scale Min/Max
        self.param_controls['scale_min'] = self.add_double_param(
            scroll_layout, "Scale Min:",
            rand_config.get('scale_min', 0.95), 0.5, 1.0, 0.01
        )

        self.param_controls['scale_max'] = self.add_double_param(
            scroll_layout, "Scale Max:",
            rand_config.get('scale_max', 0.98), 0.5, 1.0, 0.01
        )

        # Mesh Warp Jitter
        mesh_config = sig_config.get('mesh_warp', {})
        self.param_controls['mesh_warp_jitter'] = self.add_int_param(
            scroll_layout, "Mesh Warp Jitter:",
            mesh_config.get('jitter_amount', 1), 0, 10
        )

        scroll.setWidget(scroll_widget)
        params_layout.addWidget(scroll)
        params_group.setLayout(params_layout)
        layout.addWidget(params_group, stretch=1)

        # Action buttons
        button_layout = QVBoxLayout()

        self.generate_btn = QPushButton("Generate Signatures")
        self.generate_btn.clicked.connect(self.generate_signatures)
        button_layout.addWidget(self.generate_btn)

        self.save_btn = QPushButton("Save Selected")
        self.save_btn.clicked.connect(self.save_selected)
        self.save_btn.setEnabled(False)
        button_layout.addWidget(self.save_btn)

        self.save_all_btn = QPushButton("Save All")
        self.save_all_btn.clicked.connect(self.save_all)
        self.save_all_btn.setEnabled(False)
        button_layout.addWidget(self.save_all_btn)

        self.reset_btn = QPushButton("Reset Parameters")
        self.reset_btn.clicked.connect(self.reset_parameters)
        button_layout.addWidget(self.reset_btn)

        layout.addLayout(button_layout)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        return panel

    def add_double_param(self, layout, label, default_value, min_val, max_val, step):
        """Add a double spinbox parameter control."""
        layout.addWidget(QLabel(label))
        spinbox = QDoubleSpinBox()
        spinbox.setRange(min_val, max_val)
        spinbox.setSingleStep(step)
        spinbox.setValue(default_value)
        spinbox.setDecimals(2)
        layout.addWidget(spinbox)
        return spinbox

    def add_int_param(self, layout, label, default_value, min_val, max_val):
        """Add an integer spinbox parameter control."""
        layout.addWidget(QLabel(label))
        spinbox = QSpinBox()
        spinbox.setRange(min_val, max_val)
        spinbox.setValue(default_value)
        layout.addWidget(spinbox)
        return spinbox

    def create_display_panel(self):
        """Create the right panel for image display."""
        panel = QWidget()
        layout = QVBoxLayout(panel)

        # Title
        title = QLabel("Generated Signature Variations")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 16px; font-weight: bold; padding: 10px;")
        layout.addWidget(title)

        # Scroll area for images
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self.image_container = QWidget()
        self.image_grid = QGridLayout(self.image_container)
        self.image_grid.setSpacing(10)
        scroll.setWidget(self.image_container)
        layout.addWidget(scroll)

        # Status label
        self.status_label = QLabel("Click 'Generate Signatures' to begin")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet("padding: 10px; color: #666;")
        layout.addWidget(self.status_label)

        return panel

    def get_current_params(self):
        """Get current parameter values from UI controls."""
        params = {
            'gaussian_blur_sigma': self.param_controls['gaussian_blur_sigma'].value(),
            'pressure_noise_strength': self.param_controls['pressure_noise_strength'].value(),
            'ink_alpha_factor': self.param_controls['ink_alpha_factor'].value(),
            'signature_brightness_factor': self.param_controls['signature_brightness_factor'].value(),
            'final_contrast_factor': self.param_controls['final_contrast_factor'].value(),
            'randomization': {
                'rotation_angle': self.param_controls['rotation_angle'].value(),
                'offset_x': self.param_controls['offset_x'].value(),
                'offset_y': self.param_controls['offset_y'].value(),
                'scale_min': self.param_controls['scale_min'].value(),
                'scale_max': self.param_controls['scale_max'].value(),
            },
            'mesh_warp': {
                'grid_size': 3,
                'jitter_amount': self.param_controls['mesh_warp_jitter'].value(),
            }
        }
        return params

    def generate_signatures(self):
        """Generate signature variations based on current parameters."""
        worker_name = self.worker_combo.currentText()
        num_variations = self.num_variations_spin.value()
        params = self.get_current_params()

        # Disable buttons during generation
        self.generate_btn.setEnabled(False)
        self.save_btn.setEnabled(False)
        self.save_all_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.status_label.setText(f"Generating {num_variations} variations...")

        # Create and start worker thread
        self.worker = GenerationWorker(self.generator, worker_name, num_variations, params)
        self.worker.progress.connect(self.update_progress)
        self.worker.finished.connect(self.on_generation_finished)
        self.worker.start()

    def update_progress(self, value):
        """Update progress bar."""
        self.progress_bar.setValue(value)

    def on_generation_finished(self, images):
        """Handle completion of signature generation."""
        self.current_images = images
        self.display_images(images)

        # Re-enable buttons
        self.generate_btn.setEnabled(True)
        self.save_all_btn.setEnabled(True)
        self.progress_bar.setVisible(False)
        self.status_label.setText(f"Generated {len(images)} variations. Click an image to select.")

    def display_images(self, images):
        """Display images in a grid layout."""
        # Clear existing images
        while self.image_grid.count():
            item = self.image_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Display new images
        cols = self.qa_config.grid_columns
        for i, pil_image in enumerate(images):
            row = i // cols
            col = i % cols

            # Convert PIL image to QPixmap
            pixmap = self.pil_to_qpixmap(pil_image)

            # Create clickable label
            label = QLabel()
            label.setPixmap(pixmap.scaled(400, 300, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            label.setFrameStyle(1)
            label.mousePressEvent = lambda event, idx=i: self.select_image(idx)
            label.setStyleSheet("border: 2px solid #ccc; padding: 5px;")

            self.image_grid.addWidget(label, row, col)

    def pil_to_qpixmap(self, pil_image):
        """Convert PIL Image to QPixmap."""
        # Convert PIL image to bytes
        buffer = io.BytesIO()
        pil_image.save(buffer, format='PNG')
        buffer.seek(0)

        # Create QPixmap from bytes
        qimage = QImage()
        qimage.loadFromData(buffer.read())
        return QPixmap.fromImage(qimage)

    def select_image(self, index):
        """Handle image selection."""
        self.selected_image_index = index
        self.save_btn.setEnabled(True)

        # Update visual feedback
        for i in range(self.image_grid.count()):
            item = self.image_grid.itemAt(i)
            if item and item.widget():
                label = item.widget()
                if i == index:
                    label.setStyleSheet("border: 3px solid #4CAF50; padding: 5px;")
                else:
                    label.setStyleSheet("border: 2px solid #ccc; padding: 5px;")

        self.status_label.setText(f"Selected image {index + 1}. Click 'Save Selected' to save.")

    def save_selected(self):
        """Save the selected image."""
        if self.selected_image_index is not None and self.selected_image_index < len(self.current_images):
            image = self.current_images[self.selected_image_index]
            worker_name = self.worker_combo.currentText()
            params_summary = f"v{self.selected_image_index + 1}"

            output_path = self.generator.save_composite(image, worker_name, params_summary)

            QMessageBox.information(self, "Success", f"Image saved to:\n{output_path}")
            self.status_label.setText("Image saved successfully!")

    def save_all(self):
        """Save all generated images."""
        if not self.current_images:
            return

        worker_name = self.worker_combo.currentText()
        saved_paths = []

        for i, image in enumerate(self.current_images):
            params_summary = f"v{i + 1}"
            output_path = self.generator.save_composite(image, worker_name, params_summary)
            saved_paths.append(output_path)

        QMessageBox.information(
            self,
            "Success",
            f"Saved {len(saved_paths)} images to:\n{self.qa_config.output_directory}"
        )
        self.status_label.setText(f"All {len(saved_paths)} images saved successfully!")

    def reset_parameters(self):
        """Reset all parameters to default values."""
        sig_config = self.qa_config.get_signature_config()

        self.param_controls['gaussian_blur_sigma'].setValue(sig_config.get('gaussian_blur_sigma', 0.7))
        self.param_controls['pressure_noise_strength'].setValue(sig_config.get('pressure_noise_strength', 0.0))
        self.param_controls['ink_alpha_factor'].setValue(sig_config.get('ink_alpha_factor', 1.5))
        self.param_controls['signature_brightness_factor'].setValue(sig_config.get('signature_brightness_factor', 1.25))
        self.param_controls['final_contrast_factor'].setValue(sig_config.get('final_contrast_factor', 1.4))

        rand_config = sig_config.get('randomization', {})
        self.param_controls['rotation_angle'].setValue(rand_config.get('rotation_angle', 8))
        self.param_controls['offset_x'].setValue(rand_config.get('offset_x', 1))
        self.param_controls['offset_y'].setValue(rand_config.get('offset_y', 2))
        self.param_controls['scale_min'].setValue(rand_config.get('scale_min', 0.95))
        self.param_controls['scale_max'].setValue(rand_config.get('scale_max', 0.98))

        mesh_config = sig_config.get('mesh_warp', {})
        self.param_controls['mesh_warp_jitter'].setValue(mesh_config.get('jitter_amount', 1))

        self.status_label.setText("Parameters reset to defaults")
