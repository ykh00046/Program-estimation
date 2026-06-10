"""메인 윈도우 — 패널/컨트롤러 조정자."""

from dataclasses import dataclass

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QKeySequence, QShortcut
from qfluentwidgets import (
    FluentWindow,
    setTheme, Theme  # 테마 설정 추가
)
from ui.styles import UIStyles  # 프리미엄 스타일 임포트
from ui.components import center_window
from ui.builders import register_sidebar_interfaces, setup_statusbar
from ui import notifications
from ui.controllers import (
    RecipeController,
    PanelSignalBinder,
    SaveController,
    DhrSettingsSyncController,
)
from ui.sidebar_hover_controller import SidebarHoverController
from ui.workers import start_worker, wait_for_workers
from typing import Tuple

from models.data_manager import DataManager
from models.dhr_database import DhrDatabaseManager
from models.lot_manager import LotManager
from config.settings import LOT_FILE
from ui.record_view_dialog import RecordViewDialog
from utils.logger import logger
from config.config_manager import config
from ui.panels.scan_effects_panel import ScanEffectsPanel
from ui.panels.signature_panel import SignaturePanel
from ui.panels.work_info_panel import WorkInfoPanel
from ui.panels.recipe_panel import RecipePanel
from ui.panels.material_table_panel import MaterialTablePanel
from ui.panels.dashboard_panel import DashboardPanel


@dataclass
class AppServices:
    data_manager: DataManager
    dhr_db: DhrDatabaseManager
    lot_manager: LotManager


class MainWindow(FluentWindow):
    """애플리케이션 메인 윈도우(복구 버전)"""

    def __init__(self):
        super().__init__()
        # eventFilter가 super().__init__() 이후 Qt 내부 이벤트(setWindowFlags 등)에서
        # 선(先) 호출될 수 있어, 속성 미존재 AttributeError를 막기 위해 최우선 할당.
        self.sidebar_hover_controller = SidebarHoverController(self)

        # 테마 설정 (UI 생성 전)
        setTheme(Theme.DARK)

        self.setWindowTitle("DHR 배합 프로그램")
        self.resize(1200, 800) # Window size increased
        # 창 항상 맨 위 설정
        if config.get("ui.window_stays_on_top", True):
            self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)

        self.services = self._create_services()
        self.data_manager = self.services.data_manager
        # self.worker_name = None # WorkInfoPanel에서 관리됨

        self._init_ui()
        self._setup_shortcuts()
        self.recipe_controller.load_recipes()
        
        # 작업자 선택 - 취소 시 앱 종료
        worker = self.work_info_panel.request_worker_input(initial=True)
        if not worker:
            self.hide()
            QTimer.singleShot(0, self._exit_app)
            return

        self._update_backup_status()

    def _create_services(self) -> AppServices:
        """앱에서 공유하는 서비스/매니저를 한 곳에서 생성합니다."""
        return AppServices(
            data_manager=DataManager(),
            dhr_db=DhrDatabaseManager(),
            lot_manager=LotManager(LOT_FILE),
        )

    def _exit_app(self):
        """앱 종료"""
        from PySide6.QtWidgets import QApplication
        QApplication.quit()

    def is_sidebar_hover_expand_enabled(self) -> bool:
        return self.sidebar_hover_controller.is_enabled()

    def _set_sidebar_hover_expand_enabled(self, enabled: bool, persist: bool = True) -> None:
        self.sidebar_hover_controller.set_enabled(enabled, persist=persist)

    def _init_sidebar_hover_behavior(self) -> None:
        self.sidebar_hover_controller.init_behavior()

    def eventFilter(self, obj, e):
        controller = getattr(self, "sidebar_hover_controller", None)
        if controller is not None:
            controller.handle_filter_event(obj, e)
        return super().eventFilter(obj, e)

    def _init_ui(self):
        """UI 초기화 - 리팩토링된 구조"""
        # Mica 효과 비활성화 (순수 배경색 사용을 위해)
        self.setMicaEffectEnabled(False)
        
        # 글로벌 스타일 적용 (SSOT)
        self.setStyleSheet(UIStyles.get_main_style())
        
        self._create_central_widget()
        self._init_sidebar_hover_behavior()
        sb = setup_statusbar(self)
        self.google_sheets_status_label = sb.google_sheets_status_label
        self.status_controller = sb.status_controller

    def showEvent(self, event):
        super().showEvent(event)
        if not getattr(self, "_has_centered", False):
            center_window(self)
            self._has_centered = True

    def _setup_shortcuts(self):
        """단축키 설정"""
        QShortcut(QKeySequence("Ctrl+S"), self).activated.connect(self._save_record)
        QShortcut(QKeySequence("Ctrl+R"), self).activated.connect(self._clear_table)
        QShortcut(QKeySequence("Ctrl+W"), self).activated.connect(
            self._request_worker_and_refresh
        )

    def _create_central_widget(self):
        """중앙 위젯 생성"""
        self._create_panels()
        refs = register_sidebar_interfaces(self)
        self.mixing_page_refs = refs.mixing_page_refs
        self.mixing_status_bar = refs.mixing_page_refs.status_bar
        self.manual_interface = refs.manual_interface
        self.bulk_interface = refs.bulk_interface
        self.recipe_interface = refs.recipe_interface
        self._setup_dhr_settings_sync()
        self._connect_panel_signals()

    def _create_panels(self):
        """모든 패널 객체 생성"""
        # 레시피 패널
        self.recipe_panel = RecipePanel()
        
        # 작업 정보 패널
        self.work_info_panel = WorkInfoPanel()
        
        # 자재 테이블 패널
        self.material_panel = MaterialTablePanel(self.data_manager)
        self.material_panel.set_auto_assign_callback(self.auto_assign_lots)
        
        # PDF/서명 패널 (다이얼로그에서 사용)
        self.scan_effects_panel = ScanEffectsPanel()
        self.signature_panel = SignaturePanel()

        # 대시보드 패널 (PDCA #17)
        self.dashboard_panel = DashboardPanel(self.data_manager)

        self.recipe_controller = RecipeController(
            data_manager=self.data_manager,
            recipe_panel=self.recipe_panel,
            material_panel=self.material_panel,
            on_recipe_loaded=lambda _n: None,
            on_recipe_cleared=self._handle_recipe_cleared,
            on_after_load=self._after_recipe_loaded,
            on_error=self._set_status_message,
        )

        self.save_controller = SaveController(
            data_manager=self.data_manager,
            recipe_panel=self.recipe_panel,
            work_info_panel=self.work_info_panel,
            material_panel=self.material_panel,
            signature_panel=self.signature_panel,
            scan_effects_panel=self.scan_effects_panel,
            validate_inputs=self._validate_inputs,
            on_validation_error=self._handle_save_validation_error,
            on_success=self._handle_save_success,
            backup_runner=self._start_backup_worker,
        )

    def _setup_dhr_settings_sync(self) -> None:
        """메인/수기/일괄 DHR 설정 패널의 값을 동기화합니다."""
        pairs = [
            (self.scan_effects_panel, self.signature_panel),
            (self.manual_interface.scan_effects_panel, self.manual_interface.signature_panel),
            (self.bulk_interface.scan_effects_panel, self.bulk_interface.signature_panel),
        ]
        self.dhr_settings_sync_controller = DhrSettingsSyncController(pairs)
        self.dhr_settings_sync_controller.setup()

    def _connect_panel_signals(self):
        """패널 간 시그널 연결"""
        binder = PanelSignalBinder(self.recipe_panel, self.work_info_panel, self.material_panel)
        binder.bind({
            "on_recipe_changed": self.recipe_controller.on_recipe_changed,
            "on_amount_changed": self._recalc_theory,
            "on_amount_confirmed": lambda: self.material_panel.focus_first_cell(),
            "on_amount_check_failed": self.recipe_panel.focus_amount,
            "on_validation_changed": self._update_actions_enabled,
            "on_table_edit_finished": self._handle_table_edit_finished,
            "on_reset_requested": self.recipe_panel.reset,
        })

    def _handle_table_edit_finished(self) -> None:
        """테이블 편집 완료 시 저장 요청(버튼 클릭 우회 금지)."""
        if not self.mixing_page_refs.save_btn.isEnabled():
            return
        self._save_record()
    
    def _update_backup_status(self):
        """Google Sheets 백업 상태를 업데이트합니다."""
        self.status_controller.update_backup_status()

    # ------------------------------------------------------------------
    # Google Sheets 백업 워커 (PDCA #33)
    # ------------------------------------------------------------------

    def _start_backup_worker(self, product_lot: str) -> None:
        """저장 직후 Sheets 백업을 백그라운드로 실행합니다 (UI 비차단)."""
        cfg = self.data_manager.google_sheets_config
        if not (cfg.is_backup_enabled() and cfg.is_auto_backup_on_save()):
            return
        start_worker(
            self, self.data_manager.backup_lot_to_sheets,
            args=(product_lot,),
            on_result=self._on_backup_done,
            on_failed=self._on_backup_failed,
        )

    def _on_backup_done(self, result: Tuple) -> None:
        success, msg = result
        self._update_backup_status()
        if success:
            self._set_status_message("Google Sheets 백업 완료")
        else:
            self._set_status_message(f"Google Sheets 백업 실패: {msg}")

    def _on_backup_failed(self, message: str) -> None:
        self._update_backup_status()
        self._set_status_message(f"Google Sheets 백업 실패: {message}")

    def closeEvent(self, event):
        """종료 시 잔여 백그라운드 워커를 대기합니다 (PDCA #33/#36).

        수기 입력/일괄 생성 인터페이스도 워커 owner이므로 함께 대기한다.
        (작업자 미선택 조기 종료 시 인터페이스 미생성 가능 — getattr 가드)
        """
        owners = (self,
                  getattr(self, "manual_interface", None),
                  getattr(self, "bulk_interface", None))
        for owner in owners:
            if owner is not None:
                wait_for_workers(owner)
        super().closeEvent(event)

    def _set_status_message(self, message: str) -> None:
        if hasattr(self, "status_controller"):
            self.status_controller.set_message(message)
        elif hasattr(self, "mixing_status_bar"):
            self.mixing_status_bar.showMessage(message)

    def _request_worker_and_refresh(self):
        self.work_info_panel.request_worker_input(initial=False)

    def _clear_table(self):
        """테이블 자재LOT 및 실제배합 입력값 초기화"""
        logger.info("테이블 입력 초기화 시작.")
        self.material_panel.clear_table()
        self._update_actions_enabled(False)
        self._set_status_message("테이블이 초기화되었습니다.")
        logger.info("테이블 초기화 완료.")

    def auto_assign_lots(self):
        """자재별로 작업일자 기준 적합한 자재LOT을 자동배정합니다."""
        work_date = self.work_info_panel.get_data().get("work_date")
        logger.info(f"자동 LOT 배정 시작 (작업일자: {work_date})")
        self.material_panel.auto_assign_lots(work_date)
        self._set_status_message("자동 LOT 배정 완료")

    def _open_records(self):
        try:
            effects_params = self.scan_effects_panel.get_data()
            dlg = RecordViewDialog(self.data_manager, effects_params, self)
            dlg.exec()
        except Exception as e:
            logger.log_error_with_context(e, {"context": "open_records"})

    def _after_recipe_loaded(self) -> None:
        self._recalc_theory()
        self._update_actions_enabled(False)

    def _recalc_theory(self):
        amount = self.recipe_panel.get_amount()
        self.material_panel.update_theory(amount)

    def _update_actions_enabled(self, valid: bool):
        save_btn = self.mixing_page_refs.save_btn
        save_btn.setEnabled(bool(valid))
        save_btn.setText("배합 저장")
        save_btn.setStyleSheet(UIStyles.get_primary_button_style())

    def _handle_recipe_cleared(self) -> None:
        self.material_panel.clear_items()
        self._update_actions_enabled(False)

    def _validate_inputs(self) -> Tuple[bool, str]:
        materials_data = self.material_panel.get_data()
        return self.data_manager.validate_record_inputs(
            worker_name=self.work_info_panel.get_worker_name(),
            recipe_name=self.recipe_panel.get_recipe_name(),
            mixing_amount=self.recipe_panel.get_amount(),
            materials_data=materials_data,
        )

    def _save_record(self):
        try:
            self.save_controller.save_record()
        except Exception as e:
            self._handle_save_error(e)

    def _handle_save_validation_error(self, error_msg: str) -> None:
        self._set_status_message(error_msg)
        notifications.show_warning(self,"입력 오류", error_msg)

    def _handle_save_success(self, lot: str) -> None:
        self._set_status_message(
            f"배합 저장 (DB/백업): LOT {lot} | 엑셀/PDF 출력은 '기록 조회' 화면을 이용하세요."
        )
        logger.info(f"배합 완료: LOT {lot}")
        notifications.show_success(self,"저장 완료", f"LOT: {lot} 저장이 완료되었습니다.")
        self.material_panel.clear_table()
        reset_mode = config.get("ui.save_reset_mode", "safe")
        if reset_mode == "safe":
            self.recipe_panel.reset()
        self._update_actions_enabled(False)

    def _handle_save_error(self, error: Exception) -> None:
        logger.log_error_with_context(error, {"context": "save_record"})
        self._set_status_message("저장 중 오류가 발생했습니다.")
        notifications.show_error(self,"저장 실패", f"저장 중 오류가 발생했습니다: {error}")
