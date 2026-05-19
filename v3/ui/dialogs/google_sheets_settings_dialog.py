"""
Google Sheets 백업 설정을 위한 다이얼로그
"""

import os
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QCheckBox, QDialogButtonBox, QFileDialog, QMessageBox
)
from PySide6.QtCore import Qt, Signal

from config.google_sheets_config import GoogleSheetsConfig
from ui.components import StyledButton
from utils.logger import logger


class GoogleSheetsSettingsDialog(QDialog):
    """Google Sheets 백업 설정을 관리하는 다이얼로그"""

    settings_updated = Signal() # 설정 변경 시 Main Window에 알리기 위한 시그널

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Google Sheets 백업 설정")
        self.setModal(True)
        self.setFixedSize(450, 250) # 다이얼로그 크기 고정

        self.config_manager = GoogleSheetsConfig()
        self._init_ui()
        self._load_settings()

    def _init_ui(self):
        main_layout = QVBoxLayout()
        
        # 1. 인증 파일 경로 설정
        creds_layout = QHBoxLayout()
        creds_layout.addWidget(QLabel("인증 파일 (JSON):"))
        self.creds_path_input = QLineEdit()
        self.creds_path_input.setPlaceholderText("서비스 계정 JSON 파일 경로")
        creds_layout.addWidget(self.creds_path_input)
        self.creds_browse_btn = StyledButton("찾아보기", "info")
        self.creds_browse_btn.clicked.connect(self._browse_credentials_file)
        creds_layout.addWidget(self.creds_browse_btn)
        main_layout.addLayout(creds_layout)

        # 2. 스프레드시트 URL 설정
        url_layout = QHBoxLayout()
        url_layout.addWidget(QLabel("스프레드시트 URL:"))
        self.spreadsheet_url_input = QLineEdit()
        self.spreadsheet_url_input.setPlaceholderText("백업할 스프레드시트의 URL")
        url_layout.addWidget(self.spreadsheet_url_input)
        main_layout.addLayout(url_layout)

        # 3. 백업 활성화 여부
        self.backup_enabled_chk = QCheckBox("Google Sheets 백업 활성화")
        main_layout.addWidget(self.backup_enabled_chk)

        # 4. 저장 시 자동 백업 여부
        self.auto_backup_on_save_chk = QCheckBox("기록 저장 시 자동 백업")
        self.auto_backup_on_save_chk.setToolTip("새로운 배합 기록 저장 시 Google Sheets에 자동으로 백업합니다.")
        main_layout.addWidget(self.auto_backup_on_save_chk)

        # 5. 버튼 (저장, 취소)
        button_box = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self._save_settings)
        button_box.rejected.connect(self.reject)
        main_layout.addWidget(button_box)

        self.setLayout(main_layout)

    def _load_settings(self):
        """현재 설정을 UI에 로드합니다."""
        self.creds_path_input.setText(self.config_manager.get_credentials_file())
        self.spreadsheet_url_input.setText(self.config_manager.get_spreadsheet_url())
        self.backup_enabled_chk.setChecked(self.config_manager.is_backup_enabled())
        self.auto_backup_on_save_chk.setChecked(self.config_manager.is_auto_backup_on_save())
        logger.info("Google Sheets 설정 다이얼로그에 기존 설정 로드 완료.")

    def _browse_credentials_file(self):
        """인증 파일(JSON)을 선택하는 파일 다이얼로그를 엽니다."""
        initial_path = self.creds_path_input.text()
        if not initial_path or not os.path.exists(initial_path):
            initial_path = os.path.expanduser("~") # 사용자 홈 디렉토리에서 시작

        file_path, _ = QFileDialog.getOpenFileName(
            self, "Google 서비스 계정 JSON 파일 선택", initial_path, "JSON Files (*.json)"
        )
        if file_path:
            self.creds_path_input.setText(file_path)
            logger.info(f"인증 파일 선택: {file_path}")

    def _save_settings(self):
        """UI에 입력된 설정을 저장하고 다이얼로그를 닫습니다."""
        creds_file = self.creds_path_input.text().strip()
        spreadsheet_url = self.spreadsheet_url_input.text().strip()
        backup_enabled = self.backup_enabled_chk.isChecked()
        auto_backup_on_save = self.auto_backup_on_save_chk.isChecked()

        # 유효성 검사
        if backup_enabled:
            if not creds_file:
                QMessageBox.warning(self, "설정 오류", "백업 활성화 시 인증 파일 경로를 입력해야 합니다.")
                return
            if not os.path.exists(creds_file):
                QMessageBox.warning(self, "설정 오류", f"인증 파일 '{creds_file}'을 찾을 수 없습니다. 올바른 경로를 지정해주세요.")
                return
            if not spreadsheet_url:
                QMessageBox.warning(self, "설정 오류", "백업 활성화 시 스프레드시트 URL을 입력해야 합니다.")
                return
            if not (spreadsheet_url.startswith("http://") or spreadsheet_url.startswith("https://")):
                 QMessageBox.warning(self, "설정 오류", "유효한 스프레드시트 URL 형식이 아닙니다.")
                 return

        self.config_manager.set_credentials_file(creds_file)
        self.config_manager.set_spreadsheet_url(spreadsheet_url)
        self.config_manager.set_backup_enabled(backup_enabled)
        self.config_manager.set_auto_backup_on_save(auto_backup_on_save)
        
        self.config_manager.save_config() # 최종적으로 config_manager를 통해 저장
        self.settings_updated.emit() # 설정이 업데이트되었음을 알림
        logger.info("Google Sheets 설정 저장 완료.")
        self.accept()

if __name__ == '__main__':
    from PySide6.QtWidgets import QApplication
    import sys
    
    app = QApplication(sys.argv)
    # logger 초기화 (테스트를 위해)
    # from utils.logger import setup_logging
    # setup_logging() 
    
    dialog = GoogleSheetsSettingsDialog()
    if dialog.exec():
        logger.info("설정 저장됨")
    else:
        logger.info("설정 취소됨")
    sys.exit(app.exec())
