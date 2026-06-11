from dataclasses import dataclass, field
from typing import Callable, List, Optional, Tuple

from utils.logger import logger


@dataclass
class DhrUiSettingsState:
    scan_effects: dict = field(default_factory=dict)
    signature: dict = field(default_factory=dict)


class DhrSettingsSyncController:
    """Mixing/Manual/Bulk 3개 탭의 DHR 설정 패널을 실시간 동기화."""

    def __init__(self, pairs: List[Tuple[object, object]]) -> None:
        self._pairs = pairs
        self._syncing = False
        first_scan, first_sig = pairs[0]
        self.state = DhrUiSettingsState(
            scan_effects=dict(first_scan.get_data()),
            signature=dict(first_sig.get_data()),
        )

    def setup(self) -> None:
        for scan_panel, signature_panel in self._pairs:
            self._bind_pair(scan_panel, signature_panel)
        self._apply_to_all()

    def _bind_pair(self, scan_panel, signature_panel) -> None:
        scan_signals = (
            scan_panel.dpi_spin.valueChanged,
            scan_panel.noise_spin.valueChanged,
            scan_panel.blur_spin.valueChanged,
            scan_panel.contrast_spin.valueChanged,
            scan_panel.brightness_spin.valueChanged,
        )
        for signal in scan_signals:
            signal.connect(lambda *_args, p=scan_panel: self._on_scan_changed(p))

        signature_signals = (
            signature_panel.chk_charge.toggled,
            signature_panel.chk_review.toggled,
            signature_panel.chk_approve.toggled,
        )
        for signal in signature_signals:
            signal.connect(lambda *_args, p=signature_panel: self._on_sig_changed(p))

    def _apply_to_all(self) -> None:
        if self._syncing:
            return
        self._syncing = True
        try:
            for scan_panel, signature_panel in self._pairs:
                scan_panel.set_data(self.state.scan_effects)
                signature_panel.set_data(self.state.signature)
        finally:
            self._syncing = False

    def _on_scan_changed(self, source_panel) -> None:
        if self._syncing:
            return
        self.state.scan_effects = dict(source_panel.get_data())
        self._apply_to_all()

    def _on_sig_changed(self, source_panel) -> None:
        if self._syncing:
            return
        self.state.signature = dict(source_panel.get_data())
        self._apply_to_all()


class RecipeController:
    def __init__(
        self,
        data_manager,
        recipe_panel,
        material_panel,
        on_recipe_loaded: Callable[[int], None],
        on_recipe_cleared: Callable[[], None],
        on_after_load: Callable[[], None],
        on_error: Callable[[str], None],
    ):
        self.data_manager = data_manager
        self.recipe_panel = recipe_panel
        self.material_panel = material_panel
        self.on_recipe_loaded = on_recipe_loaded
        self.on_recipe_cleared = on_recipe_cleared
        self.on_after_load = on_after_load
        self.on_error = on_error

    def load_recipes(self) -> None:
        """Load recipe names into the recipe panel."""
        try:
            self.data_manager.load_recipes()
            names = self.data_manager.get_recipe_names()
            self.recipe_panel.set_recipes(names)
            logger.info(f"레시피 로드: {len(names)}종")
            self.on_recipe_loaded(len(names))
        except Exception as e:
            logger.error(f"레시피 로드 오류: {e}")
            self.on_error("데이터베이스에서 레시피를 불러오는데 실패했습니다.")

    def on_recipe_changed(self, recipe_name: str) -> None:
        if not recipe_name:
            self.material_panel.clear_items()
            self.on_recipe_cleared()
            return

        items = self.data_manager.get_recipe_items(recipe_name)
        self.material_panel.load_items(items)
        self.on_after_load()


class PanelSignalBinder:
    def __init__(self, recipe_panel, work_info_panel, material_panel):
        self.recipe_panel = recipe_panel
        self.work_info_panel = work_info_panel
        self.material_panel = material_panel

    def bind(self, callbacks) -> None:
        required_keys = {
            "on_recipe_changed",
            "on_amount_changed",
            "on_amount_confirmed",
            "on_amount_check_failed",
            "on_validation_changed",
            "on_table_edit_finished",
            "on_reset_requested",
        }
        missing = required_keys - set(callbacks.keys())
        if missing:
            raise KeyError(f"Missing callbacks for PanelSignalBinder: {sorted(missing)}")

        self.recipe_panel.recipeChanged.connect(callbacks["on_recipe_changed"])
        self.recipe_panel.amountChanged.connect(callbacks["on_amount_changed"])
        self.recipe_panel.amountConfirmed.connect(callbacks["on_amount_confirmed"])

        self.material_panel.amountCheckFailed.connect(callbacks["on_amount_check_failed"])
        self.material_panel.validationStatusChanged.connect(callbacks["on_validation_changed"])
        self.material_panel.tableEditFinished.connect(callbacks["on_table_edit_finished"])
        self.material_panel.resetRequested.connect(callbacks["on_reset_requested"])


class StatusController:
    def __init__(self, status_bar, google_sheets_label, google_sheets_config):
        self.status_bar = status_bar
        self.google_sheets_label = google_sheets_label
        self.google_sheets_config = google_sheets_config

    def set_message(self, message: str) -> None:
        # 커스텀 StatusBar(main_label "준비됨" 보유)에는 show_message로 라벨을 직접
        # 갱신한다 — QStatusBar.showMessage의 임시 메시지는 위젯 위에 겹쳐 그려져
        # "준비됨"과 텍스트가 포개지는 원인이었음 (PDCA #38 겹침 수정).
        show = getattr(self.status_bar, "show_message", None)
        if callable(show):
            show(message, timeout=0)
        else:
            self.status_bar.showMessage(message)

    def update_backup_status(self) -> None:
        status_text = self.google_sheets_config.get_backup_status_text()
        self.google_sheets_label.setText(f"☁️ {status_text}")
        logger.debug(f"Google Sheets 백업 상태 업데이트: {status_text}")


class SaveController:
    def __init__(
        self,
        data_manager,
        recipe_panel,
        work_info_panel,
        material_panel,
        signature_panel,
        scan_effects_panel,
        validate_inputs,
        on_validation_error,
        on_success,
        backup_runner: Optional[Callable[[str], None]] = None,
    ):
        self.data_manager = data_manager
        self.recipe_panel = recipe_panel
        self.work_info_panel = work_info_panel
        self.material_panel = material_panel
        self.signature_panel = signature_panel
        self.scan_effects_panel = scan_effects_panel
        self.validate_inputs = validate_inputs
        self.on_validation_error = on_validation_error
        self.on_success = on_success
        # PDCA #33: 주입 시 동기 백업 대신 호출자가 비동기 백업을 수행
        self.backup_runner = backup_runner

    def _collect_payload(self) -> dict:
        work_data = self.work_info_panel.get_data()
        materials_data = self.material_panel.get_data()
        return {
            "worker_name": work_data.get("worker_name"),
            "recipe_name": self.recipe_panel.get_recipe_name(),
            "mixing_amount": self.recipe_panel.get_amount(),
            "materials_data": materials_data,
            "work_date": work_data.get("work_date"),
            "work_time": work_data.get("work_time"),
            "signature_options": self.signature_panel.get_data(),
            "effects_params": self.scan_effects_panel.get_data(),
            "include_work_time": work_data.get("include_time"),
        }

    def save_record(self) -> None:
        valid, error_msg = self.validate_inputs()
        if not valid:
            self.on_validation_error(error_msg)
            return

        payload = self._collect_payload()
        lot = self.data_manager.save_record(
            **payload, auto_backup=self.backup_runner is None)
        self.on_success(lot)
        if self.backup_runner is not None:
            self.backup_runner(lot)
