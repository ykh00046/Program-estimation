from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QDateEdit,
    QTimeEdit,
    QCheckBox,
    QDialog,
    QComboBox,
    QMessageBox,
    QPushButton,
)
from PySide6.QtCore import Qt, QDate, QTime
from config.config_manager import config
from utils.logger import logger
from ui.styles import UITheme, UIStyles
from ui.dialogs.admin_dialog import PasswordDialog, AdminDialog


class WorkerInputDialog(QDialog):
    """작업자 선택 다이얼로그 (프레임리스 카드 스타일)."""

    def __init__(self, parent=None, current_worker=None):
        super().__init__(parent)
        self.setWindowTitle("작업자 선택")
        self.setModal(True)
        self.setFixedSize(520, 360)
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setStyleSheet(
            UIStyles.get_dialog_style()
            + f"""
            QLabel {{ color: {UITheme.TEXT_PRIMARY}; font-family: 'Segoe UI', sans-serif; }}
            """
        )

        self._init_ui(current_worker)

    def _init_ui(self, current_worker=None) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(68, 52, 68, 48)
        main_layout.setSpacing(0)
        main_layout.addStretch(1)

        card_layout = QVBoxLayout()
        card_layout.setSpacing(24)
        card_layout.setAlignment(Qt.AlignCenter)

        title = QLabel("Welcome Back!")
        title.setStyleSheet("font-size: 30px; font-weight: 700; letter-spacing: -0.5px;")
        title.setAlignment(Qt.AlignCenter)
        card_layout.addWidget(title)

        subtitle = QLabel("작업을 시작하려면 작업자를 선택하세요")
        subtitle.setStyleSheet(f"color: {UITheme.TEXT_SECONDARY}; font-size: 14px;")
        subtitle.setAlignment(Qt.AlignCenter)
        card_layout.addWidget(subtitle)

        self.worker_combo = QComboBox()
        self.worker_combo.addItems(list(config.workers))
        self.worker_combo.setStyleSheet(UIStyles.get_input_style())
        self.worker_combo.setFixedHeight(38)
        card_layout.addWidget(self.worker_combo)

        if current_worker and current_worker in config.workers:
            self.worker_combo.setCurrentText(current_worker)
        elif config.last_worker and config.last_worker in config.workers:
            self.worker_combo.setCurrentText(config.last_worker)

        admin_btn = QPushButton("관리자 모드")
        admin_btn.setCursor(Qt.PointingHandCursor)
        admin_btn.setStyleSheet(
            f"""
            QPushButton {{
                background: transparent;
                border: none;
                color: {UITheme.TEXT_SECONDARY};
                font-size: 12px;
                padding: 2px 6px;
            }}
            QPushButton:hover {{
                color: {UITheme.TEXT_PRIMARY};
                text-decoration: underline;
            }}
            """
        )
        admin_btn.clicked.connect(self._open_admin_dialog)
        admin_row = QHBoxLayout()
        admin_row.addStretch(1)
        admin_row.addWidget(admin_btn)
        admin_row.addStretch(1)
        card_layout.addLayout(admin_row)

        button_row = QHBoxLayout()
        button_row.setSpacing(14)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setStyleSheet(UIStyles.get_secondary_button_style())
        cancel_btn.clicked.connect(self.reject)

        ok_btn = QPushButton("OK")
        ok_btn.setStyleSheet(UIStyles.get_primary_button_style())
        ok_btn.clicked.connect(self._on_accept)

        button_row.addStretch(1)
        button_row.addWidget(cancel_btn)
        button_row.addWidget(ok_btn)

        card_layout.addLayout(button_row)

        main_layout.addLayout(card_layout)
        main_layout.addStretch(1)

    def _on_accept(self) -> None:
        name = self.get_worker_name()
        if not name:
            QMessageBox.warning(self, "작업자 선택", "작업자를 선택하세요.")
            return
        self.accept()

    def _open_admin_dialog(self) -> None:
        password = PasswordDialog(self)
        if password.exec() == QDialog.Accepted:
            admin = AdminDialog(self)
            admin.exec()

    def get_worker_name(self) -> str:
        return self.worker_combo.currentText().strip()


class WorkInfoPanel(QWidget):
    """작업 정보(일자/시간/작업자) 패널."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.worker_name = config.last_worker or None
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        self.setLayout(layout)

        date_label = QLabel("작업일자")
        date_label.setStyleSheet(f"color: {UITheme.TEXT_PRIMARY}; font-weight: 600;")
        layout.addWidget(date_label)

        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDate(QDate.currentDate())
        layout.addWidget(self.date_edit)

        layout.addSpacing(8)

        self.time_container = QWidget()
        time_layout = QHBoxLayout(self.time_container)
        time_layout.setContentsMargins(0, 0, 0, 0)
        time_layout.setSpacing(8)

        time_label = QLabel("작업시간")
        time_label.setStyleSheet(f"color: {UITheme.TEXT_PRIMARY}; font-weight: 600;")
        time_layout.addWidget(time_label)

        self.time_edit = QTimeEdit()
        self.time_edit.setTime(QTime.currentTime())
        self.time_edit.setEnabled(False)
        time_layout.addWidget(self.time_edit)

        self.chk_include_time = QCheckBox("작업시간 포함")
        self.chk_include_time.setChecked(False)
        self.chk_include_time.setEnabled(True)
        time_layout.addWidget(self.chk_include_time)

        self.time_container.setVisible(False)
        layout.addWidget(self.time_container)

        self.chk_manual_time = QCheckBox("작업시간 수동으로 입력")
        self.chk_manual_time.setChecked(False)
        self.chk_manual_time.toggled.connect(self._toggle_manual_time)
        layout.addWidget(self.chk_manual_time)

        layout.addStretch(1)

    def request_worker_input(self, initial=False):
        """작업자 입력 다이얼로그 표시."""
        dlg = WorkerInputDialog(self, self.worker_name)
        if dlg.exec() == QDialog.Accepted:
            self.worker_name = dlg.get_worker_name()
            config.save_last_worker(self.worker_name)
            logger.info(f"작업자 설정: {self.worker_name}")
            return self.worker_name
        if initial:
            logger.warning("초기 작업자 설정이 취소되었습니다.")
        return None

    def get_worker_name(self):
        return self.worker_name

    def get_data(self) -> dict:
        """작업 정보 데이터 반환."""
        if self.chk_manual_time.isChecked():
            include_time = self.chk_include_time.isChecked()
            work_time = self.time_edit.time().toString("HH:mm:ss") if include_time else ""
        else:
            include_time = True
            work_time = QTime.currentTime().toString("HH:mm:ss")
        return {
            "work_date": self.date_edit.date().toString("yyyy-MM-dd"),
            "work_time": work_time,
            "include_time": include_time,
            "worker_name": self.worker_name,
        }

    def _toggle_manual_time(self, enabled: bool) -> None:
        self.time_container.setVisible(enabled)
        self.time_edit.setEnabled(enabled)
        if enabled:
            self.chk_include_time.setChecked(True)
