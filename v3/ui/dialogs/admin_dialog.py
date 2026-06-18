"""
관리자 다이얼로그 - 작업자 및 서명 관리
"""
import os
import shutil
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QWidget,
    QListWidget, QPushButton, QLineEdit,
    QLabel, QMessageBox, QFileDialog, QInputDialog,
    QDialogButtonBox, QGroupBox
)
from config.config_manager import config
from config.settings import BASE_PATH
from utils.logger import logger
from ui.panels.admin_signature_panel import SignatureSettingsPanel


class PasswordDialog(QDialog):
    """비밀번호 입력 다이얼로그"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("관리자 인증")
        self.setModal(True)
        self.setFixedSize(300, 220)
        
        layout = QVBoxLayout()
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)
        
        layout.addWidget(QLabel("관리자 비밀번호를 입력하세요:"))
        
        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.Password)
        self.password_edit.returnPressed.connect(self._verify)
        layout.addWidget(self.password_edit)
        
        layout.addStretch()
        
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self._verify)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)
        
        self.setLayout(layout)


    def _verify(self):
        if not config.is_admin_password_set():
            if self._prompt_set_password():
                self.accept()
            return

        if config.verify_admin_password(self.password_edit.text()):
            self.accept()
        else:
            QMessageBox.warning(self, "인증 실패", "비밀번호가 올바르지 않습니다.")
            self.password_edit.clear()
            self.password_edit.setFocus()

    def _prompt_set_password(self) -> bool:
        password, ok = QInputDialog.getText(self, "설정 필요", "관리자 비밀번호를 설정하세요:", QLineEdit.Password)
        if not ok:
            return False
        password = password.strip()
        if not password:
            QMessageBox.warning(self, "오류", "비밀번호를 비울 수 없습니다.")
            return False

        confirm, ok = QInputDialog.getText(self, "확인", "비밀번호를 다시 입력하세요:", QLineEdit.Password)
        if not ok:
            return False
        if password != confirm.strip():
            QMessageBox.warning(self, "오류", "비밀번호가 일치하지 않습니다.")
            return False

        if config.set_admin_password(password):
            QMessageBox.information(self, "완료", "관리자 비밀번호가 설정되었습니다.")
            return True

        QMessageBox.critical(self, "오류", "비밀번호 설정에서 오류가 발생했습니다.")
        return False


class AdminDialog(QDialog):
    """관리자 다이얼로그 - 작업자 및 서명 관리"""

    SIGNATURE_DIR = os.path.join(BASE_PATH, "resources", "signature")

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("관리자 모드 - 작업자/서명 관리")
        self.setMinimumSize(1100, 800)
        self.resize(1100, 800)
        
        self.workers = list(config.workers)  # 복사본 생성
        self._init_ui()
        self._load_data()

    def _init_ui(self):
        layout = QVBoxLayout()
        
        # 탭 위젯
        tabs = QTabWidget()
        tabs.addTab(self._create_workers_tab(), "작업자 관리")
        tabs.addTab(self._create_signatures_tab(), "서명 파일 관리")
        
        # 서명 설정 패널 (새로 추가됨)
        self.signature_settings_panel = SignatureSettingsPanel()
        tabs.addTab(self.signature_settings_panel, "서명 품질/위치 설정")
        
        layout.addWidget(tabs)
        
        # 하단 버튼
        btns = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        btns.accepted.connect(self._save_and_close)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)
        
        self.setLayout(layout)

    def _create_workers_tab(self) -> QWidget:
        """작업자 관리 탭"""
        tab = QWidget()
        layout = QVBoxLayout()
        
        # 작업자 목록
        self.worker_list = QListWidget()
        layout.addWidget(self.worker_list)
        
        # 버튼
        btn_layout = QHBoxLayout()
        
        add_btn = QPushButton("추가")
        add_btn.clicked.connect(self._add_worker)
        btn_layout.addWidget(add_btn)
        
        remove_btn = QPushButton("삭제")
        remove_btn.clicked.connect(self._remove_worker)
        btn_layout.addWidget(remove_btn)
        
        layout.addLayout(btn_layout)

        admin_box = QGroupBox("관리자")
        admin_layout = QHBoxLayout(admin_box)
        admin_layout.addWidget(QLabel("관리자 비밀번호"))
        change_pw_btn = QPushButton("비밀번호 변경")
        change_pw_btn.clicked.connect(self._change_admin_password)
        admin_layout.addWidget(change_pw_btn)
        admin_layout.addStretch()
        layout.addWidget(admin_box)

        tab.setLayout(layout)
        return tab

    def _create_signatures_tab(self) -> QWidget:
        """서명 관리 탭"""
        tab = QWidget()
        layout = QVBoxLayout()
        
        # 작업자 선택
        layout.addWidget(QLabel("작업자를 선택하고 서명을 관리하세요:"))
        
        self.sig_worker_list = QListWidget()
        self.sig_worker_list.currentItemChanged.connect(self._on_worker_selected)
        layout.addWidget(self.sig_worker_list)
        
        # 서명 파일 목록
        sig_group = QGroupBox("서명 파일")
        sig_layout = QVBoxLayout()
        
        self.sig_file_list = QListWidget()
        sig_layout.addWidget(self.sig_file_list)
        
        sig_btn_layout = QHBoxLayout()
        
        upload_btn = QPushButton("서명 추가")
        upload_btn.clicked.connect(self._upload_signature)
        sig_btn_layout.addWidget(upload_btn)
        
        delete_btn = QPushButton("서명 삭제")
        delete_btn.clicked.connect(self._delete_signature)
        sig_btn_layout.addWidget(delete_btn)
        
        sig_layout.addLayout(sig_btn_layout)
        sig_group.setLayout(sig_layout)
        layout.addWidget(sig_group)
        
        tab.setLayout(layout)
        return tab

    def _load_data(self):
        """데이터 로드"""
        self.worker_list.clear()
        self.sig_worker_list.clear()
        
        for worker in self.workers:
            self.worker_list.addItem(worker)
            self.sig_worker_list.addItem(worker)

    def _add_worker(self):
        """작업자 추가"""
        name, ok = QInputDialog.getText(self, "작업자 추가", "작업자 이름:")
        if ok and name.strip():
            name = name.strip()
            if name in self.workers:
                QMessageBox.warning(self, "오류", f"'{name}'은(는) 이미 존재합니다.")
                return
            self.workers.append(name)
            self._load_data()
            logger.info(f"작업자 추가: {name}")

    def _remove_worker(self):
        """작업자 삭제"""
        item = self.worker_list.currentItem()
        if not item:
            QMessageBox.warning(self, "선택 필요", "삭제할 작업자를 선택하세요.")
            return
        
        name = item.text()
        reply = QMessageBox.question(
            self, "확인", 
            f"'{name}' 작업자를 삭제하시겠습니까?\n(서명 파일은 유지됩니다)",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.workers.remove(name)
            self._load_data()
            logger.info(f"작업자 삭제: {name}")

    def _on_worker_selected(self, current, previous):
        """작업자 선택 시 서명 파일 목록 로드"""
        self.sig_file_list.clear()
        if not current:
            return
        
        worker_name = current.text()
        pattern = f"{worker_name}_charge_"
        
        if os.path.exists(self.SIGNATURE_DIR):
            for f in sorted(os.listdir(self.SIGNATURE_DIR)):
                if f.startswith(pattern) and f.endswith(".png"):
                    self.sig_file_list.addItem(f)

    def _upload_signature(self):
        """서명 파일 업로드"""
        worker_item = self.sig_worker_list.currentItem()
        if not worker_item:
            QMessageBox.warning(self, "선택 필요", "작업자를 먼저 선택하세요.")
            return
        
        worker_name = worker_item.text()
        
        files, _ = QFileDialog.getOpenFileNames(
            self, "서명 이미지 선택", "", "PNG 파일 (*.png)"
        )
        
        if not files:
            return
        
        os.makedirs(self.SIGNATURE_DIR, exist_ok=True)
        
        # 기존 파일 번호 확인
        existing_nums = []
        for f in os.listdir(self.SIGNATURE_DIR):
            if f.startswith(f"{worker_name}_charge_") and f.endswith(".png"):
                try:
                    num = int(f.replace(f"{worker_name}_charge_", "").replace(".png", ""))
                    existing_nums.append(num)
                except ValueError:
                    pass
        
        next_num = max(existing_nums, default=0) + 1
        
        for file_path in files:
            new_name = f"{worker_name}_charge_{next_num}.png"
            dest_path = os.path.join(self.SIGNATURE_DIR, new_name)
            shutil.copy2(file_path, dest_path)
            logger.info(f"서명 파일 추가: {new_name}")
            next_num += 1
        
        # 목록 새로고침
        self._on_worker_selected(worker_item, None)
        QMessageBox.information(self, "완료", f"{len(files)}개의 서명 파일이 추가되었습니다.")

    def _delete_signature(self):
        """서명 파일 삭제"""
        item = self.sig_file_list.currentItem()
        if not item:
            QMessageBox.warning(self, "선택 필요", "삭제할 서명 파일을 선택하세요.")
            return
        
        filename = item.text()
        reply = QMessageBox.question(
            self, "확인", f"'{filename}'을(를) 삭제하시겠습니까?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            file_path = os.path.join(self.SIGNATURE_DIR, filename)
            if os.path.exists(file_path):
                os.remove(file_path)
                logger.info(f"서명 파일 삭제: {filename}")
            
            # 목록 새로고침
            worker_item = self.sig_worker_list.currentItem()
            self._on_worker_selected(worker_item, None)

    def _change_admin_password(self):
        if config.is_admin_password_set():
            current, ok = QInputDialog.getText(self, "비밀번호 확인", "현재 비밀번호를 입력하세요:", QLineEdit.Password)
            if not ok:
                return
            if not config.verify_admin_password(current):
                QMessageBox.warning(self, "인증 실패", "현재 비밀번호가 올바르지 않습니다.")
                return

        new_pw, ok = QInputDialog.getText(self, "비밀번호 변경", "새 비밀번호를 입력하세요:", QLineEdit.Password)
        if not ok:
            return
        new_pw = new_pw.strip()
        if not new_pw:
            QMessageBox.warning(self, "오류", "비밀번호를 비울 수 없습니다.")
            return

        confirm, ok = QInputDialog.getText(self, "확인", "새 비밀번호를 다시 입력하세요:", QLineEdit.Password)
        if not ok:
            return
        if new_pw != confirm.strip():
            QMessageBox.warning(self, "오류", "비밀번호가 일치하지 않습니다.")
            return

        if config.set_admin_password(new_pw):
            QMessageBox.information(self, "완료", "비밀번호가 변경되었습니다.")
        else:
            QMessageBox.critical(self, "오류", "비밀번호 변경 중 오류가 발생했습니다.")

    def _save_and_close(self):
        """저장 후 닫기"""
        if config.save_workers(self.workers):
            logger.info(f"작업자 목록 저장 완료: {len(self.workers)}명")
            QMessageBox.information(self, "저장 완료", "변경사항이 저장되었습니다.")
            self.accept()
        else:
            QMessageBox.critical(self, "저장 실패", "작업자 목록 저장에 실패했습니다.")
