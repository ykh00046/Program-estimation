from dataclasses import dataclass
from typing import Tuple

from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QFrame, QLabel, QSizePolicy
from PySide6.QtCore import Qt
from qfluentwidgets import (
    CardWidget,
    CaptionLabel,
    CheckBox,
    LargeTitleLabel,
)

from qfluentwidgets import FluentIcon as FIF

from config.config_manager import config
from ui.components import StatusBar, StyledButton
from ui.controllers import StatusController
from ui.styles import UITheme


@dataclass
class MixingPageRefs:
    save_btn: StyledButton
    status_bar: StatusBar


@dataclass
class SidebarRefs:
    """register_sidebar_interfaces가 생성해 main_window가 소유할 참조 묶음.

    status_bar는 단일 소스인 `mixing_page_refs.status_bar`에서 파생하므로
    별도 필드로 중복 보유하지 않는다.
    """
    mixing_page_refs: object
    manual_interface: object
    bulk_interface: object
    recipe_interface: object


@dataclass
class StatusbarRefs:
    """setup_statusbar가 생성해 main_window가 소유할 참조 묶음."""
    google_sheets_status_label: object
    status_controller: object


def build_action_page(title: str, description: str, button_text: str, on_click, object_name: str) -> QWidget:
    page = QWidget()
    page.setObjectName(object_name)
    root = QVBoxLayout(page)
    root.setContentsMargins(36, 32, 36, 32)
    root.setSpacing(16)

    card = CardWidget()
    layout = QVBoxLayout(card)
    layout.setContentsMargins(32, 26, 32, 26)
    layout.setSpacing(14)

    title_label = LargeTitleLabel(title)
    title_label.setStyleSheet(f"color: {UITheme.TEXT_PRIMARY};")
    desc_label = CaptionLabel(description)
    desc_label.setStyleSheet(f"color: {UITheme.TEXT_SECONDARY}; font-size: 13px;")

    action_btn = StyledButton(button_text, "primary")
    action_btn.setMinimumHeight(44)
    action_btn.setMaximumWidth(420)
    action_btn.clicked.connect(on_click)

    layout.addWidget(title_label)
    layout.addWidget(desc_label)
    layout.addSpacing(12)
    layout.addWidget(action_btn, 0, Qt.AlignLeft)

    card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
    root.addWidget(card)
    root.addStretch(1)
    return page


def build_mixing_page(window) -> Tuple[QWidget, MixingPageRefs]:
    """배합 페이지 - 세로 레이아웃으로 작업자 워크플로우 최적화"""
    page = QWidget()
    page.setObjectName("MixingPage")
    root = QVBoxLayout(page)
    root.setContentsMargins(28, 22, 28, 22)
    root.setSpacing(16)

    # 상단: Recipe & Work Info (컴팩트)
    top_card = CardWidget()
    top_layout = QHBoxLayout(top_card)
    top_layout.setContentsMargins(14, 10, 14, 10)
    top_layout.setSpacing(16)

    # 레시피 패널
    top_layout.addWidget(window.recipe_panel, 2)
    # 작업 정보 패널
    top_layout.addWidget(window.work_info_panel, 3)

    # 저장 버튼 (상단 우측)
    save_btn = StyledButton("저장", "primary")
    save_btn.setEnabled(False)
    save_btn.clicked.connect(window._save_record)
    save_btn.setMinimumHeight(40)
    top_layout.addWidget(save_btn, 0, Qt.AlignRight | Qt.AlignVCenter)

    root.addWidget(top_card)

    # 하단: Materials List (전체 너비, 확장)
    materials_card = CardWidget()
    materials_layout = QVBoxLayout(materials_card)
    materials_layout.setContentsMargins(14, 10, 14, 10)

    materials_title = CaptionLabel("자재 목록")
    materials_title.setStyleSheet(
        f"color: {UITheme.MINT_ACCENT}; font-weight: bold; font-size: 14px;"
    )
    materials_layout.addWidget(materials_title)
    materials_layout.addSpacing(6)
    materials_layout.addWidget(window.material_panel)

    root.addWidget(materials_card, 1)  # stretch factor로 확장

    # 상태바
    status_bar = StatusBar()
    root.addWidget(status_bar)

    return page, MixingPageRefs(save_btn=save_btn, status_bar=status_bar)


def build_settings_page(window) -> QWidget:
    """설정 페이지 - PDF/서명 옵션"""
    page = QWidget()
    page.setObjectName("SettingsPage")
    root = QVBoxLayout(page)
    root.setContentsMargins(36, 32, 36, 32)
    root.setSpacing(22)

    # 타이틀 영역
    title = LargeTitleLabel("설정")
    title.setStyleSheet(f"color: {UITheme.TEXT_PRIMARY};")
    subtitle = CaptionLabel("PDF 스캔 효과 및 서명 옵션을 관리합니다.")
    subtitle.setStyleSheet(f"color: {UITheme.TEXT_SECONDARY}; font-size: 13px;")
    root.addWidget(title)
    root.addWidget(subtitle)
    root.addSpacing(10)

    # UI behavior options
    ui_option_card = CardWidget()
    ui_option_layout = QHBoxLayout(ui_option_card)
    ui_option_layout.setContentsMargins(16, 12, 16, 12)
    ui_option_layout.setSpacing(12)

    ui_option_label = CaptionLabel("사이드바 옵션")
    hover_expand_chk = CheckBox("마우스를 올리면 사이드바 자동 펼침")
    hover_expand_chk.setToolTip("사이드바가 접힌 상태에서 마우스를 올리면 펼쳐지고, 벗어나면 잠시 후 다시 접힙니다.")
    if hasattr(window, "is_sidebar_hover_expand_enabled"):
        hover_expand_chk.setChecked(bool(window.is_sidebar_hover_expand_enabled()))
    if hasattr(window, "_set_sidebar_hover_expand_enabled"):
        hover_expand_chk.toggled.connect(window._set_sidebar_hover_expand_enabled)

    ui_option_layout.addWidget(ui_option_label)
    ui_option_layout.addStretch(1)
    ui_option_layout.addWidget(hover_expand_chk)
    root.addWidget(ui_option_card)

    # 설정 카드들 (가로 배치)
    settings_row = QHBoxLayout()
    settings_row.setSpacing(20)

    # PDF 스캔 효과 카드
    pdf_card = create_panel_card("PDF 스캔 효과", window.scan_effects_panel)
    settings_row.addWidget(pdf_card)

    # 서명 옵션 카드
    sig_card = create_panel_card("서명 옵션", window.signature_panel)
    settings_row.addWidget(sig_card)

    settings_row.addStretch(1)
    root.addLayout(settings_row)
    root.addStretch(1)

    return page


def create_panel_card(title: str, widget: QWidget) -> QFrame:
    card = CardWidget()
    layout = QVBoxLayout(card)
    layout.setContentsMargins(16, 12, 16, 12)
    layout.setSpacing(10)

    title_label = CaptionLabel(title)
    layout.addWidget(title_label)
    layout.addWidget(widget)
    return card


# setup_bottom_buttons 제거: 저장 버튼은 상단 카드 우측에 배치


def register_sidebar_interfaces(window) -> SidebarRefs:
    """MainWindow의 사이드바 서브 인터페이스 8종을 등록하고 참조 묶음을 반환합니다.

    호출 전 `window._create_panels()`가 완료되어 있어야 한다.
    반환된 `SidebarRefs`를 호출부(main_window)가 자기 속성에 할당하며,
    DHR 3-way sync 초기화는 호출부 책임이다(이 함수는 수행하지 않음).
    """
    from ui.panels.manual_input_interface import ManualInputInterface
    from ui.panels.recipe_management_interface import RecipeManagementInterface
    from ui.panels.bulk_creation_interface import BulkCreationInterface

    # 1. 배합 페이지 (메인 작업 화면)
    mixing, mixing_page_refs = build_mixing_page(window)
    window.addSubInterface(mixing, FIF.MIX_VOLUMES, "배합")

    # 2. 수기 입력
    manual_interface = ManualInputInterface(
        window,
        dhr_db=window.services.dhr_db,
        lot_manager=window.services.lot_manager,
    )
    window.addSubInterface(manual_interface, FIF.EDIT, "수기 입력")

    # 3. 일괄 생성
    bulk_interface = BulkCreationInterface(
        window,
        dhr_db=window.services.dhr_db,
        lot_manager=window.services.lot_manager,
    )
    window.addSubInterface(bulk_interface, FIF.PASTE, "일괄 생성")

    # 4. DHR 관리
    recipe_interface = RecipeManagementInterface(
        window,
        dhr_db=window.services.dhr_db,
    )
    window.addSubInterface(recipe_interface, FIF.LIBRARY, "DHR 관리")

    # 4-2. 대시보드 (PDCA #17)
    window.addSubInterface(window.dashboard_panel, FIF.PIE_SINGLE, "대시보드")

    # 5. 기록 조회
    records_page = build_action_page(
        "기록 조회",
        "저장된 배합 기록을 검색하고 출력합니다.",
        "기록 조회 열기",
        window._open_records,
        "RecordsPage",
    )
    window.addSubInterface(records_page, FIF.HISTORY, "기록 조회")

    # 6. 설정 페이지
    window.addSubInterface(build_settings_page(window), FIF.SETTING, "설정")

    # 7. 작업자 변경
    worker_page = build_action_page(
        "작업자 변경",
        "현재 작업자를 변경합니다.",
        "작업자 변경",
        window._request_worker_and_refresh,
        "WorkerPage",
    )
    window.addSubInterface(worker_page, FIF.PEOPLE, "작업자 변경")

    return SidebarRefs(
        mixing_page_refs=mixing_page_refs,
        manual_interface=manual_interface,
        bulk_interface=bulk_interface,
        recipe_interface=recipe_interface,
    )


def setup_statusbar(window) -> StatusbarRefs:
    """상태바 + Google Sheets 백업 라벨 + StatusController를 초기화하고 참조를 반환합니다.

    `window.mixing_status_bar`(register_sidebar_interfaces 반환분을 main_window가 할당)와
    `window.data_manager`에 의존하므로, 호출 전 그 두 속성이 설정되어 있어야 한다.
    """
    tol = config.tolerance
    scale = config.default_scale
    window._set_status_message(f"기본 스케일: {scale} | 허용오차: ±{tol}")

    google_sheets_status_label = QLabel("")
    window.mixing_status_bar.addPermanentWidget(google_sheets_status_label)
    google_sheets_status_label.setStyleSheet("padding: 0 5px;")
    status_controller = StatusController(
        status_bar=window.mixing_status_bar,
        google_sheets_label=google_sheets_status_label,
        google_sheets_config=window.data_manager.google_sheets_config,
    )
    return StatusbarRefs(
        google_sheets_status_label=google_sheets_status_label,
        status_controller=status_controller,
    )
