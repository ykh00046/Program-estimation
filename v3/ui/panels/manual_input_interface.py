"""
DHR 관리 인터페이스 (사이드바 메뉴용)
기존 DHRManualWindow를 메인 윈도우 패널로 전환 및 기능 통합
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QTableWidgetItem, QHeaderView,
    QMessageBox, QTabWidget, QScrollArea, QDialog
)
from PySide6.QtCore import Qt, QDate, QTime
from PySide6.QtGui import QColor
from models.lot_manager import LotManager
from config.settings import LOT_FILE

from ui.components import StyledButton, create_group_box, center_window
from ui.styles import UIStyles, UITheme
from ui.panels.scan_effects_panel import ScanEffectsPanel
from ui.panels.signature_panel import SignaturePanel
from ui.widgets.pasteable_table import PasteableTableWidget
from config.config_manager import config
from utils.logger import logger
from models.dhr_database import DhrDatabaseManager
from typing import Optional
from qfluentwidgets import (
    CardWidget, LineEdit, DoubleSpinBox, DateEdit, TimeEdit, CheckBox
)


class ManualInputInterface(QScrollArea):
    """수기 배합일지 작성 패널"""

    def __init__(self, parent=None, dhr_db=None, lot_manager=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setObjectName("ManualInputInterface")
        self.setStyleSheet("QScrollArea { border: none; background-color: transparent; }")
        
        # 데이터 관리자
        self.dhr_db = dhr_db or DhrDatabaseManager()
        self.lot_manager = lot_manager or LotManager(LOT_FILE)
        
        self._init_ui()
        self._connect_signals()

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

        root.addLayout(self._build_toolbar())

        top_layout = QHBoxLayout()
        top_layout.setSpacing(20)
        top_layout.addWidget(self._build_work_group())
        top_layout.addWidget(self._build_product_group())
        root.addLayout(top_layout)

        root.addWidget(self._build_settings_tabs())
        root.addWidget(self._build_table_group())
        root.addLayout(self._build_bottom_bar())

    def _build_toolbar(self) -> QHBoxLayout:
        """상단 타이틀 + 레시피 불러오기 버튼."""
        toolbar_layout = QHBoxLayout()
        title_label = QLabel("수기 입력")
        title_label.setStyleSheet(f"font-size: 24px; font-weight: bold; color: {UITheme.TEXT_PRIMARY};")
        toolbar_layout.addWidget(title_label)
        toolbar_layout.addStretch()

        load_recipe_btn = StyledButton("레시피 불러오기", "primary")
        load_recipe_btn.clicked.connect(self._open_recipe_loader)
        toolbar_layout.addWidget(load_recipe_btn)
        return toolbar_layout

    def _build_work_group(self) -> CardWidget:
        """작업 정보 카드 (작업일자/시간/시간표시)."""
        work_group = CardWidget()
        work_container = QVBoxLayout(work_group)
        work_container.setContentsMargins(16, 12, 16, 12)
        work_container.setSpacing(8)
        work_container.addWidget(QLabel("작업 정보"))

        work_layout = QHBoxLayout()
        work_layout.addWidget(QLabel("작업일자:"))
        self.date_edit = DateEdit()
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDate(QDate.currentDate())
        work_layout.addWidget(self.date_edit)

        work_layout.addWidget(QLabel("작업시간:"))
        self.time_edit = TimeEdit()
        self.time_edit.setTime(QTime.currentTime())
        work_layout.addWidget(self.time_edit)

        self.chk_include_time = CheckBox("엑셀에 시간 표시")
        self.chk_include_time.setToolTip("일괄 생성 시 09시+랜덤 분부터 시작, 동일 날짜는 20~40분 가산")
        self.chk_include_time.setChecked(True)
        work_layout.addWidget(self.chk_include_time)

        work_container.addLayout(work_layout)
        return work_group

    def _build_product_group(self) -> CardWidget:
        """제품 정보 카드 (제품명/LOT/배합량)."""
        product_group = CardWidget()
        product_container = QVBoxLayout(product_group)
        product_container.setContentsMargins(16, 12, 16, 12)
        product_container.setSpacing(8)
        product_container.addWidget(QLabel("제품 정보"))

        product_layout = QHBoxLayout()
        product_layout.addWidget(QLabel("제품명:"))
        self.product_name_edit = LineEdit()
        self.product_name_edit.setPlaceholderText("제품명을 입력하세요")
        product_layout.addWidget(self.product_name_edit)

        product_layout.addWidget(QLabel("제품LOT:"))
        self.product_lot_edit = LineEdit()
        self.product_lot_edit.setReadOnly(True)
        product_layout.addWidget(self.product_lot_edit)

        product_layout.addWidget(QLabel("배합량(g):"))
        self.amount_spin = DoubleSpinBox()
        self.amount_spin.setRange(0, 9999999)
        self.amount_spin.setDecimals(2)
        self.amount_spin.setValue(0)
        product_layout.addWidget(self.amount_spin)

        product_container.addLayout(product_layout)
        return product_group

    def _build_settings_tabs(self) -> QTabWidget:
        """PDF 스캔 효과 + 서명 옵션 설정 탭."""
        tabs = QTabWidget()
        settings_tab = QWidget()
        settings_layout = QHBoxLayout()

        self.scan_effects_panel = ScanEffectsPanel()
        settings_layout.addWidget(create_group_box("PDF 스캔 효과", self.scan_effects_panel))

        self.signature_panel = SignaturePanel()
        settings_layout.addWidget(create_group_box("서명 옵션", self.signature_panel))

        settings_layout.addStretch()
        settings_tab.setLayout(settings_layout)
        tabs.addTab(settings_tab, "PDF/서명 설정")
        return tabs

    def _build_table_group(self) -> CardWidget:
        """자재 입력 테이블 카드 (붙여넣기 지원 + 행 버튼)."""
        table_group = CardWidget()
        table_container = QVBoxLayout(table_group)
        table_container.setContentsMargins(16, 12, 16, 12)
        table_layout = QVBoxLayout()

        self.table = PasteableTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels([
            "품목코드", "품목명", "배합비율(%)", "이론계량(g)", "실제배합(g)", "자재LOT"
        ])
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.setStyleSheet(UIStyles.get_table_style())
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)

        self._add_row()
        table_layout.addWidget(self.table)

        table_btn_layout = QHBoxLayout()
        add_row_btn = StyledButton("행 추가")
        add_row_btn.clicked.connect(self._add_row)
        table_btn_layout.addWidget(add_row_btn)
        remove_row_btn = StyledButton("행 삭제")
        remove_row_btn.clicked.connect(self._remove_row)
        table_btn_layout.addWidget(remove_row_btn)
        table_btn_layout.addStretch()
        table_layout.addLayout(table_btn_layout)

        table_container.addLayout(table_layout)
        return table_group

    def _build_bottom_bar(self) -> QHBoxLayout:
        """하단 기록 조회 / 저장 및 출력 버튼."""
        bottom = QHBoxLayout()
        record_view_btn = StyledButton("기록 조회", "secondary")
        record_view_btn.clicked.connect(self._open_record_view)
        bottom.addWidget(record_view_btn)
        bottom.addStretch()

        self.save_btn = StyledButton("저장 및 출력", "success")
        self.save_btn.clicked.connect(self._save_and_export)
        bottom.addWidget(self.save_btn)
        return bottom

    def _open_recipe_loader(self):
        """레시피 불러오기 다이얼로그"""
        from ui.dhr_recipe_loader_dialog import DhrRecipeLoaderDialog
        dlg = DhrRecipeLoaderDialog(self)
        center_window(dlg) # 중앙 정렬
        if dlg.exec() == QDialog.Accepted:
            if hasattr(dlg, 'selected_recipe') and dlg.selected_recipe:
                self.load_recipe(dlg.selected_recipe, dlg.selected_materials)

    def _connect_signals(self):
        """시그널 연결"""
        # 제품명 또는 날짜 변경 시 LOT 자동 생성
        self.product_name_edit.textChanged.connect(self._update_product_lot)
        self.date_edit.dateChanged.connect(self._update_product_lot)
        
        # 초기 LOT 생성
        self._update_product_lot()

    def _update_product_lot(self):
        """제품 LOT 자동 생성 (제품명 + YYMMDD)"""
        product_name = self.product_name_edit.text().strip()
        date = self.date_edit.date()
        if not product_name:
            self.product_lot_edit.clear()
            return

        work_date = date.toString("yyyy-MM-dd")
        try:
            lot = self.dhr_db.generate_product_lot(product_name, work_date)
        except Exception:
            date_str = date.toString("yyMMdd")
            lot = f"{product_name}{date_str}"
        self.product_lot_edit.setText(lot)

    def _add_row(self):
        """행 추가"""
        row = self.table.rowCount()
        self.table.insertRow(row)
        
        for col in range(6):
            item = QTableWidgetItem("")
            if col == 3:  # 이론계량 - 자동계산
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                item.setBackground(QColor(UITheme.READONLY_BG))
            self.table.setItem(row, col, item)

    def _remove_row(self):
        """현재 선택된 행 삭제"""
        row = self.table.currentRow()
        if row >= 0:
            self.table.removeRow(row)
        elif self.table.rowCount() > 0:
            self.table.removeRow(self.table.rowCount() - 1)

    def _table_text(self, row: int, col: int) -> str:
        item = self.table.item(row, col)
        return item.text().strip() if item else ""

    def _is_empty_material_row(self, row: int) -> bool:
        return all(not self._table_text(row, col) for col in range(6))

    def _get_effective_material_row_count(self) -> int:
        return sum(0 if self._is_empty_material_row(row) else 1 for row in range(self.table.rowCount()))

    def _recalc_theory(self):
        """이론계량 재계산"""
        amount = self.amount_spin.value()
        
        for row in range(self.table.rowCount()):
            ratio_item = self.table.item(row, 2)
            if ratio_item:
                try:
                    ratio = float(ratio_item.text()) if ratio_item.text() else 0
                    theory = amount * (ratio / 100.0)
                    self.table.item(row, 3).setText(f"{theory:.3f}")
                except ValueError:
                    pass

    def _validate(self) -> bool:
        """입력 검증"""
        if not self.product_name_edit.text().strip():
            QMessageBox.warning(self, "입력 오류", "제품명을 입력하세요.")
            self.product_name_edit.setFocus()
            return False
        
        if self.amount_spin.value() <= 0:
            QMessageBox.warning(self, "입력 오류", "배합량을 입력하세요.")
            self.amount_spin.setFocus()
            return False
        
        if self._get_effective_material_row_count() == 0:
            QMessageBox.warning(self, "입력 오류", "자재를 최소 1개 이상 입력하세요.")
            return False
        
        return True

    def _save_and_export(self):
        """Save DHR record and export Excel/PDF."""
        if not self._validate():
            return

        self._recalc_theory()
        data = self._collect_data()
        details_data = self._build_details_for_export(data)

        saved_lot = self._persist_dhr_record(data, details_data)
        if saved_lot is None:
            return
        data["product_lot"] = saved_lot

        try:
            excel_path, pdf_path = self._run_export_pipeline(data, details_data)
            self._notify_save_result(saved_lot, excel_path, pdf_path)
            logger.info(f"DHR export finished: {data['product_name']}")
        except Exception as e:
            logger.error(f"DHR export failed after DB save: {e}")
            QMessageBox.warning(
                self,
                "Partial Success",
                f"DB save succeeded but export failed.\n\nLOT: {saved_lot}\n{e}",
            )

    def _build_details_for_export(self, data: dict) -> list:
        """테이블의 자재 행을 export용 details_data로 변환."""
        details_data = []
        for row in range(self.table.rowCount()):
            if self._is_empty_material_row(row):
                continue
            material_code = self._table_text(row, 0) or f"ITEM_{row+1}"
            details_data.append({
                "material_code": material_code,
                "material_name": self._table_text(row, 1),
                "material_lot": self._table_text(row, 5),
                "ratio": self._to_float(self._table_text(row, 2)),
                "theory_amount": self._to_float(self._table_text(row, 3)),
                "actual_amount": self._to_float(self._table_text(row, 4)),
            })
        return details_data

    def _persist_dhr_record(self, data: dict, details_data: list) -> Optional[str]:
        """DHR DB 저장. 성공 시 LOT 반환, 실패 시 critical popup + None."""
        try:
            saved_lot = self.dhr_db.generate_product_lot(data["product_name"], data["work_date"])
            record_data = {
                "product_lot": saved_lot,
                "product_name": data["product_name"],
                "worker": self.worker_name,
                "work_date": data["work_date"],
                "work_time": data["work_time"] if data["include_time"] else "",
                "total_amount": data["amount"],
                "scale": config.default_scale,
            }
            self.dhr_db.save_dhr_record(record_data, details_data)
            self.product_lot_edit.setText(saved_lot)
            logger.info(f"DHR record saved: {saved_lot}")
            return saved_lot
        except Exception as e:
            logger.error(f"DHR DB save failed: {e}")
            QMessageBox.critical(self, "Error", f"DB save failed.\n{e}")
            return None

    def _run_export_pipeline(self, data: dict, details_data: list) -> tuple:
        """Excel + PDF 출력. Excel 실패 시 RuntimeError raise. PDF 실패 시 (excel, None)."""
        from models.excel_exporter import ExcelExporter
        exporter = ExcelExporter()
        export_data = {
            "product_lot": data["product_lot"],
            "recipe_name": data["product_name"],
            "work_date": data["work_date"],
            "work_time": data["work_time"] if data["include_time"] else "",
            "worker": self.worker_name,
            "total_amount": data["amount"],
            "materials": details_data,
            "scale": config.default_scale,
        }
        excel_path = exporter.export_to_excel(export_data, include_work_time=data["include_time"])
        if not excel_path:
            raise RuntimeError("Excel export failed")
        effects_params = self.scan_effects_panel.get_data()
        pdf_path = exporter.export_to_pdf(excel_path, effects_params)
        return excel_path, pdf_path

    def _notify_save_result(self, lot: str, excel_path: str, pdf_path) -> None:
        """저장 결과 메시지박스 (전체 성공 / PDF 실패 부분 성공)."""
        import os
        msg = f"Saved.\n\nLOT: {lot}\nExcel: {os.path.basename(excel_path)}"
        if pdf_path:
            msg += f"\nPDF: {os.path.basename(pdf_path)}"
            QMessageBox.information(self, "Done", msg)
        else:
            QMessageBox.warning(
                self,
                "Partial Success",
                f"DB save succeeded but PDF export failed.\n\nLOT: {lot}\nExcel: {os.path.basename(excel_path)}",
            )

    def _open_record_view(self):
        """DHR 기록 조회 다이얼로그 열기"""
        from ui.dhr_record_view_dialog import DhrRecordViewDialog
        effects_params = self.scan_effects_panel.get_data()
        dialog = DhrRecordViewDialog(effects_params, self)
        center_window(dialog)
        dialog.exec()

    def _collect_data(self) -> dict:
        """테이블 데이터 수집"""
        materials = {}
        
        for row in range(self.table.rowCount()):
            if self._is_empty_material_row(row):
                continue

            code = self.table.item(row, 0).text() if self.table.item(row, 0) else ""
            if not code.strip():
                code = f"ITEM_{row+1}"
            
            materials[code] = {
                '품목코드': code,
                '품목명': self.table.item(row, 1).text() if self.table.item(row, 1) else "",
                '배합비율': self._to_float(self.table.item(row, 2).text() if self.table.item(row, 2) else "0"),
                '이론계량': self._to_float(self.table.item(row, 3).text() if self.table.item(row, 3) else "0"),
                '실제배합': self._to_float(self.table.item(row, 4).text() if self.table.item(row, 4) else "0"),
                'LOT': self.table.item(row, 5).text() if self.table.item(row, 5) else ""
            }
        
        return {
            'product_name': self.product_name_edit.text().strip(),
            'product_lot': self.product_lot_edit.text().strip(),
            'amount': self.amount_spin.value(),
            'work_date': self.date_edit.date().toString("yyyy-MM-dd"),
            'work_time': self.time_edit.time().toString("HH:mm:ss"),
            'include_time': self.chk_include_time.isChecked(),
            'materials': materials
        }

    def _to_float(self, s: str) -> float:
        try:
            return float(s.strip()) if s.strip() else 0.0
        except ValueError:
            return 0.0

    def load_recipe(self, recipe_data: dict, materials: list):
        """레시피 데이터로 테이블 채우기"""
        # 제품명 설정
        if recipe_data.get('recipe_name'):
            self.product_name_edit.setText(recipe_data['recipe_name'])
        
        # 기본 배합량 설정
        if recipe_data.get('default_amount'):
            self.amount_spin.setValue(recipe_data['default_amount'])
        
        # 테이블 초기화 후 자재 추가
        self.table.setRowCount(0)
        
        for mat in materials:
            row = self.table.rowCount()
            self.table.insertRow(row)
            
            # 품목코드
            self.table.setItem(row, 0, QTableWidgetItem(str(mat.get('material_code', ''))))
            # 품목명
            self.table.setItem(row, 1, QTableWidgetItem(str(mat.get('material_name', ''))))
            # 배합비율
            self.table.setItem(row, 2, QTableWidgetItem(str(mat.get('ratio', ''))))
            # 이론계량 (자동계산)
            theory_item = QTableWidgetItem("")
            theory_item.setFlags(theory_item.flags() & ~Qt.ItemIsEditable)
            theory_item.setBackground(QColor(UITheme.READONLY_BG))
            self.table.setItem(row, 3, theory_item)
            # 실제배합
            self.table.setItem(row, 4, QTableWidgetItem(""))
            # 자재LOT
            self.table.setItem(row, 5, QTableWidgetItem(""))
        
        # 이론계량 재계산
        self._recalc_theory()
        
        logger.info(f"레시피 로드 완료: {recipe_data.get('recipe_name', 'Unknown')}, 자재 {len(materials)}건")
