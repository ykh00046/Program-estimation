"""
DHR 일괄 생성 인터페이스 (사이드바 메뉴용)
엑셀 붙여넣기를 통한 대량 DHR 생성 전용
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QTableWidgetItem, QHeaderView, QMessageBox, QTabWidget, QScrollArea, QDialog
)

from models.lot_manager import LotManager
from config.settings import LOT_FILE
from ui.components import StyledButton, create_group_box, center_window
from ui.styles import UIStyles, UITheme
from ui.panels.scan_effects_panel import ScanEffectsPanel
from ui.panels.signature_panel import SignaturePanel
from ui.widgets.pasteable_table import PasteableTableWidget, PasteableSimpleTableWidget
from config.config_manager import config
from utils.logger import logger
from utils.bulk_helpers import parse_date_cell, parse_bulk_entries, get_materials_from_table
from models.dhr_database import DhrDatabaseManager
from models.dhr_bulk_generator import DhrBulkGenerator
from qfluentwidgets import CardWidget, LineEdit, CheckBox


class BulkCreationInterface(QScrollArea):
    """DHR 일괄 생성 패널"""

    def __init__(self, parent=None, dhr_db=None, lot_manager=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setObjectName("BulkCreationInterface")
        self.setStyleSheet("QScrollArea { border: none; background-color: transparent; }")
        
        self.dhr_db = dhr_db or DhrDatabaseManager()
        self.lot_manager = lot_manager or LotManager(LOT_FILE)
        
        self._init_ui()

    @property
    def worker_name(self):
        return config.last_worker or "Unknown"

    def _init_ui(self):
        self.content_widget = QWidget()
        self.content_widget.setObjectName("DHRContent")
        self.setWidget(self.content_widget)

        root = QVBoxLayout(self.content_widget)
        root.setContentsMargins(24, 20, 24, 40)
        root.setSpacing(20)

        title_label = QLabel("일괄 생성")
        title_label.setStyleSheet(f"font-size: 24px; font-weight: bold; color: {UITheme.TEXT_PRIMARY};")
        root.addWidget(title_label)

        root.addWidget(self._build_common_info_group())
        root.addWidget(self._build_bulk_data_group())
        root.addWidget(self._build_material_group())
        root.addWidget(self._build_settings_tabs())
        root.addLayout(self._build_action_bar())

    def _build_common_info_group(self) -> CardWidget:
        """공통 정보 카드 (제품명 + 시간 옵션)."""
        info_group = CardWidget()
        info_layout = QVBoxLayout(info_group)
        info_layout.setContentsMargins(16, 12, 16, 12)

        common_layout = QHBoxLayout()
        common_layout.addWidget(QLabel("제품명:"))
        self.product_name_edit = LineEdit()
        self.product_name_edit.setPlaceholderText("일괄 생성할 제품명")
        common_layout.addWidget(self.product_name_edit)

        common_layout.addWidget(QLabel("시간 설정:"))
        self.chk_include_time = CheckBox("엑셀에 시간 표시")
        self.chk_include_time.setChecked(True)
        common_layout.addWidget(self.chk_include_time)

        info_layout.addLayout(common_layout)
        return info_group

    def _build_bulk_data_group(self) -> CardWidget:
        """생성 데이터 입력 카드 (날짜/배합량 테이블 + 행 버튼)."""
        bulk_group = CardWidget()
        bulk_layout = QVBoxLayout(bulk_group)
        bulk_layout.setContentsMargins(16, 12, 16, 12)

        bulk_label = QLabel("1. 생성할 데이터 입력 (날짜 / 배합량)")
        bulk_label.setStyleSheet(f"color: {UITheme.TEXT_PRIMARY}; font-weight: bold;")
        bulk_layout.addWidget(bulk_label)

        guide_label = QLabel("입력 형식: 작업일자(YYYY-MM-DD) / 배합량(g) - 엑셀에서 복사하여 붙여넣기(Ctrl+V) 가능")
        guide_label.setStyleSheet(f"color: {UITheme.TEXT_SECONDARY}; font-size: 12px;")
        bulk_layout.addWidget(guide_label)

        self.bulk_table = PasteableSimpleTableWidget()
        self.bulk_table.setColumnCount(2)
        self.bulk_table.setHorizontalHeaderLabels(["작업일자", "배합량(g)"])
        self.bulk_table.setRowCount(5)
        self.bulk_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.bulk_table.setStyleSheet(UIStyles.get_table_style())
        self.bulk_table.setAlternatingRowColors(True)
        self.bulk_table.verticalHeader().setVisible(False)
        bulk_layout.addWidget(self.bulk_table)

        bulk_btn_box = QHBoxLayout()
        add_btn = StyledButton("행 추가")
        add_btn.clicked.connect(self._add_bulk_row)
        bulk_btn_box.addWidget(add_btn)
        remove_btn = StyledButton("행 삭제")
        remove_btn.clicked.connect(self._remove_bulk_row)
        bulk_btn_box.addWidget(remove_btn)
        bulk_btn_box.addStretch()
        bulk_layout.addLayout(bulk_btn_box)
        return bulk_group

    def _build_material_group(self) -> CardWidget:
        """자재 정보 카드 (공통 적용 테이블 + 행/레시피 버튼)."""
        mat_group = CardWidget()
        mat_layout = QVBoxLayout(mat_group)
        mat_layout.setContentsMargins(16, 12, 16, 12)

        mat_label = QLabel("2. 자재 정보 (모든 건에 공통 적용)")
        mat_label.setStyleSheet(f"color: {UITheme.TEXT_PRIMARY}; font-weight: bold;")
        mat_layout.addWidget(mat_label)

        self.mat_table = PasteableTableWidget()
        self.mat_table.setColumnCount(3)
        self.mat_table.setHorizontalHeaderLabels(["품목코드", "품목명", "배합비율(%)"])
        self.mat_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.mat_table.setStyleSheet(UIStyles.get_table_style())
        self.mat_table.setAlternatingRowColors(True)
        self.mat_table.verticalHeader().setVisible(False)
        self.mat_table.setRowCount(3)
        self._add_mat_row(0)
        mat_layout.addWidget(self.mat_table)

        mat_btn_box = QHBoxLayout()
        mat_add_btn = StyledButton("행 추가")
        mat_add_btn.clicked.connect(self._add_mat_row)
        mat_btn_box.addWidget(mat_add_btn)
        mat_remove_btn = StyledButton("행 삭제")
        mat_remove_btn.clicked.connect(self._remove_mat_row)
        mat_btn_box.addWidget(mat_remove_btn)
        mat_btn_box.addStretch()

        load_recipe_btn = StyledButton("레시피 불러오기", "primary")
        load_recipe_btn.clicked.connect(self._open_recipe_loader)
        mat_btn_box.addWidget(load_recipe_btn)

        mat_layout.addLayout(mat_btn_box)
        return mat_group

    def _build_settings_tabs(self) -> QTabWidget:
        """PDF 스캔 효과 + 서명 옵션 설정 탭."""
        tabs = QTabWidget()
        settings_tab = QWidget()
        settings_layout = QHBoxLayout(settings_tab)

        self.scan_effects_panel = ScanEffectsPanel()
        settings_layout.addWidget(create_group_box("PDF 스캔 효과", self.scan_effects_panel))

        self.signature_panel = SignaturePanel()
        settings_layout.addWidget(create_group_box("서명 옵션", self.signature_panel))

        settings_layout.addStretch()
        tabs.addTab(settings_tab, "PDF/서명 설정")
        return tabs

    def _build_action_bar(self) -> QHBoxLayout:
        """하단 기록 조회 / 일괄 생성 버튼."""
        action_layout = QHBoxLayout()
        record_view_btn = StyledButton("기록 조회", "secondary")
        record_view_btn.clicked.connect(self._open_record_view)
        action_layout.addWidget(record_view_btn)
        action_layout.addStretch()

        generate_btn = StyledButton("일괄 생성 및 출력", "success")
        generate_btn.clicked.connect(self._bulk_create)
        generate_btn.setMinimumHeight(45)
        generate_btn.setMinimumWidth(200)
        generate_btn.setStyleSheet("font-size: 16px; font-weight: bold;")
        action_layout.addWidget(generate_btn)
        return action_layout

    def _add_bulk_row(self):
        row = self.bulk_table.rowCount()
        self.bulk_table.insertRow(row)

    def _remove_bulk_row(self):
        row = self.bulk_table.currentRow()
        if row >= 0: self.bulk_table.removeRow(row)

    def _add_mat_row(self, row=None):
        if row is None: row = self.mat_table.rowCount()
        self.mat_table.insertRow(row)
        # 3열(이론계량)은 없지만 Base 클래스 호환을 위해
        for c in range(3):
            self.mat_table.setItem(row, c, QTableWidgetItem(""))

    def _remove_mat_row(self):
        row = self.mat_table.currentRow()
        if row >= 0: self.mat_table.removeRow(row)

    def _open_record_view(self):
        """DHR 기록 조회 다이얼로그 열기"""
        from ui.dhr_record_view_dialog import DhrRecordViewDialog
        effects_params = self.scan_effects_panel.get_data()
        dialog = DhrRecordViewDialog(effects_params, self)
        center_window(dialog)
        dialog.exec()

    def _open_recipe_loader(self):
        from ui.dhr_recipe_loader_dialog import DhrRecipeLoaderDialog
        dlg = DhrRecipeLoaderDialog(self)
        center_window(dlg)
        if dlg.exec() == QDialog.Accepted:
            if hasattr(dlg, 'selected_recipe') and dlg.selected_recipe:
                self.load_recipe(dlg.selected_recipe, dlg.selected_materials)

    def load_recipe(self, recipe_data: dict, materials: list):
        if recipe_data.get('recipe_name'):
            self.product_name_edit.setText(recipe_data['recipe_name'])
        
        self.mat_table.setRowCount(0)
        for mat in materials:
            row = self.mat_table.rowCount()
            self.mat_table.insertRow(row)
            self.mat_table.setItem(row, 0, QTableWidgetItem(str(mat.get('material_code', ''))))
            self.mat_table.setItem(row, 1, QTableWidgetItem(str(mat.get('material_name', ''))))
            self.mat_table.setItem(row, 2, QTableWidgetItem(str(mat.get('ratio', ''))))

    def _parse_date_cell(self, value: str) -> str:
        return parse_date_cell(value)

    def _parse_bulk_entries(self):
        return parse_bulk_entries(self.bulk_table)

    def _get_materials_for_bulk(self):
        return get_materials_from_table(self.mat_table)

    def _bulk_create(self):
        product_name = self.product_name_edit.text().strip()
        if not product_name:
            QMessageBox.warning(self, "입력 오류", "제품명을 입력하세요.")
            return

        try:
            entries = self._parse_bulk_entries()
            materials = self._get_materials_for_bulk()
        except ValueError as e:
            QMessageBox.warning(self, "입력 오류", str(e))
            return

        if not entries:
            QMessageBox.warning(self, "입력 오류", "생성할 데이터가 없습니다.")
            return

        include_time = self.chk_include_time.isChecked()
        generator = DhrBulkGenerator(self.dhr_db, self.lot_manager)

        try:
            count = generator.generate(
                entries=entries,
                product_name=product_name,
                materials=materials,
                worker=self.worker_name,
                include_time=include_time,
                scan_effects=self.scan_effects_panel.get_data(),
                signature_options=self.signature_panel.get_data(),
                export=True
            )
            export_failures = getattr(generator, "last_export_failures", [])
            if export_failures:
                preview = "\n".join(export_failures[:3])
                more = ""
                if len(export_failures) > 3:
                    more = f"\n... (+{len(export_failures) - 3} more)"
                QMessageBox.warning(
                    self,
                    "Partial Success",
                    f"DB records saved: {count}\nExport failures: {len(export_failures)}\n\n{preview}{more}",
                )
            else:
                QMessageBox.information(self, "Done", f"Bulk creation completed. (Total {count})")
        except Exception as e:
            logger.error(f"DHR 일괄 생성 실패: {e}")
            QMessageBox.critical(self, "오류", f"일괄 생성 중 오류가 발생했습니다.\n{e}")
