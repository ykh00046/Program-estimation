"""
Google Sheets 백업 설정을 위한 다이얼로그
"""

import os
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QCheckBox, QDialogButtonBox, QFileDialog, QMessageBox
)
from PySide6.QtCore import Signal

from config.google_sheets_config import GoogleSheetsConfig
from models.backup.google_sheets_backup import GoogleSheetsBackup
from ui.components import StyledButton
from ui.workers import start_worker
from utils.logger import logger


class GoogleSheetsSettingsDialog(QDialog):
    """Google Sheets 백업 설정을 관리하는 다이얼로그"""

    settings_updated = Signal() # 설정 변경 시 Main Window에 알리기 위한 시그널

    def __init__(self, parent=None, backup=None):
        super().__init__(parent)
        self.setWindowTitle("Google Sheets 백업 설정")
        self.setModal(True)
        self.setFixedSize(520, 340) # 대기 큐 상태/제어 영역 포함

        self.config_manager = GoogleSheetsConfig()
        # Design Ref: §2 — #35의 검증된 큐/백업 계약을 UI에서 조합한다.
        self.backup = backup or GoogleSheetsBackup(self.config_manager)
        self._active_workers = set()
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

        # 5. 실패 백업 대기 큐 상태/수동 복구 (PDCA #41)
        retry_layout = QHBoxLayout()
        self.pending_label = QLabel()
        retry_layout.addWidget(self.pending_label)
        retry_layout.addStretch()
        self.retry_btn = StyledButton("지금 재시도", "info")
        self.retry_btn.setToolTip("저장된 설정으로 대기 중인 백업을 즉시 다시 전송합니다.")
        self.retry_btn.clicked.connect(self._retry_pending)
        retry_layout.addWidget(self.retry_btn)
        main_layout.addLayout(retry_layout)

        # 6. 버튼 (저장, 취소)
        self.button_box = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        self.button_box.accepted.connect(self._save_settings)
        self.button_box.rejected.connect(self.reject)
        main_layout.addWidget(self.button_box)

        self.setLayout(main_layout)

    def _load_settings(self):
        """현재 설정을 UI에 로드합니다."""
        self.creds_path_input.setText(self.config_manager.get_credentials_file())
        self.spreadsheet_url_input.setText(self.config_manager.get_spreadsheet_url())
        self.backup_enabled_chk.setChecked(self.config_manager.is_backup_enabled())
        self.auto_backup_on_save_chk.setChecked(self.config_manager.is_auto_backup_on_save())
        self._refresh_queue_status()
        logger.info("Google Sheets 설정 다이얼로그에 기존 설정 로드 완료.")

    def _refresh_queue_status(self):
        """대기 큐 행 수와 재시도 가능 상태를 동기화한다."""
        pending = self.backup.queue.count()
        self.pending_label.setText(f"전송 대기: {pending}건")
        running = any(worker.isRunning() for worker in self._active_workers)
        self.retry_btn.setEnabled(pending > 0 and not running)
        return pending

    def _retry_pending(self):
        """저장된 설정으로 대기 큐를 UI 비차단 재전송한다."""
        if self.backup.queue.count() <= 0:
            self._refresh_queue_status()
            return
        # Plan SC-3: 네트워크 전송은 기존 FunctionWorker 경로에서만 실행한다.
        self.retry_btn.setEnabled(False)
        worker = start_worker(
            self,
            self.backup.backup_records,
            args=([],),
            on_result=self._on_retry_result,
            on_failed=self._on_retry_failed,
            busy_widgets=(self.button_box,),
        )
        # result_ready 시점에는 QThread가 아직 running일 수 있으므로 finished 후 최종 상태를 맞춘다.
        worker.finished.connect(self._refresh_queue_status)

    def _on_retry_result(self, result):
        ok, message = result
        pending = self._refresh_queue_status()
        if ok:
            QMessageBox.information(self, "백업 재시도 완료", message)
        else:
            QMessageBox.warning(
                self, "백업 재시도 실패", f"{message}\n\n전송 대기: {pending}건")

    def _on_retry_failed(self, message):
        pending = self._refresh_queue_status()
        QMessageBox.warning(
            self, "백업 재시도 실패", f"{message}\n\n전송 대기: {pending}건")

    def _retry_is_running(self):
        return any(worker.isRunning() for worker in self._active_workers)

    def reject(self):
        if self._retry_is_running():
            QMessageBox.information(self, "백업 진행 중", "백업 재시도가 끝난 뒤 창을 닫아주세요.")
            return
        super().reject()

    def closeEvent(self, event):
        if self._retry_is_running():
            event.ignore()
            QMessageBox.information(self, "백업 진행 중", "백업 재시도가 끝난 뒤 창을 닫아주세요.")
            return
        super().closeEvent(event)

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
