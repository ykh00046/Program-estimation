"""
DHR 레시피 관리 다이얼로그
레시피 CRUD 기능
"""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel,
    QLineEdit, QComboBox, QTableWidget, QTableWidgetItem,
    QPushButton, QMessageBox, QAbstractItemView, QHeaderView, QSplitter,
    QWidget, QInputDialog
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor

from models.dhr_database import DhrDatabaseManager
from utils.logger import logger
from ui.styles import UIStyles, UITheme
from ui.components import StyledButton, center_window


class DhrRecipeManagerDialog(QDialog):
    """DHR 레시피 관리 다이얼로그"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.db = DhrDatabaseManager()
        self.current_recipe_id = None
        self.setWindowTitle("DHR 레시피 관리")
        self.setGeometry(100, 100, 1200, 700)
        self._init_ui()
        self._load_categories()
        self._load_recipes()
    
    def _init_ui(self):
        self.setStyleSheet(UIStyles.get_dialog_style())

        main_layout = QVBoxLayout()
        self.setLayout(main_layout)

        content_layout = QHBoxLayout()
        content_layout.setContentsMargins(10, 10, 10, 10)
        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self._build_recipe_list_panel())

        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(5, 0, 0, 0)
        right_layout.addWidget(self._build_info_group())
        right_layout.addWidget(self._build_material_group())

        save_btn_layout = QHBoxLayout()
        save_btn_layout.addStretch()
        save_btn = StyledButton("저장", "success")
        save_btn.setMinimumWidth(120)
        save_btn.clicked.connect(self._save_recipe)
        save_btn_layout.addWidget(save_btn)
        right_layout.addLayout(save_btn_layout)
        splitter.addWidget(right_widget)

        splitter.setSizes([400, 800])
        splitter.setHandleWidth(2)
        splitter.setStyleSheet(f"QSplitter::handle {{ background-color: {UITheme.BORDER_COLOR}; }}")

        content_layout.addWidget(splitter)
        main_layout.addLayout(content_layout)
        main_layout.addLayout(self._build_bottom_bar())

        center_window(self)

    def _make_category_btn(self, text, callback) -> StyledButton:
        """분류 +/- 버튼 팩토리 (28x28 secondary)."""
        btn = StyledButton(text, "secondary")
        btn.setFixedSize(28, 28)
        btn.clicked.connect(callback)
        return btn

    def _build_recipe_list_panel(self) -> QWidget:
        """좌측 레시피 목록 패널 (테이블 + 새 레시피/삭제 버튼)."""
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 5, 0)

        title_lbl = QLabel("레시피 목록")
        title_lbl.setStyleSheet(f"color: {UITheme.TEXT_PRIMARY}; font-weight: bold; font-size: 14px;")
        left_layout.addWidget(title_lbl)

        self.recipe_table = QTableWidget()
        self.recipe_table.setColumnCount(6)
        self.recipe_table.setHorizontalHeaderLabels(["ID", "레시피명", "거래처", "제품종류", "약품", "착용기간"])
        self.recipe_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.recipe_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.recipe_table.clicked.connect(self._on_recipe_selected)
        self.recipe_table.setColumnHidden(0, True)
        self.recipe_table.setStyleSheet(UIStyles.get_table_style())
        self.recipe_table.setAlternatingRowColors(True)
        self.recipe_table.verticalHeader().setVisible(False)
        left_layout.addWidget(self.recipe_table)

        list_btn_layout = QHBoxLayout()
        new_btn = StyledButton("새 레시피", "primary")
        new_btn.clicked.connect(self._new_recipe)
        list_btn_layout.addWidget(new_btn)
        delete_btn = StyledButton("삭제", "danger")
        delete_btn.clicked.connect(self._delete_recipe)
        list_btn_layout.addWidget(delete_btn)
        list_btn_layout.addStretch()
        left_layout.addLayout(list_btn_layout)
        return left_widget

    def _build_info_group(self) -> QGroupBox:
        """레시피 기본 정보 그룹 (3개 입력 행 조립)."""
        info_group = QGroupBox("레시피 정보")
        info_layout = QVBoxLayout()
        info_layout.addLayout(self._build_name_row())
        info_layout.addLayout(self._build_company_type_row())
        info_layout.addLayout(self._build_drug_period_row())
        info_group.setLayout(info_layout)
        return info_group

    def _build_name_row(self) -> QHBoxLayout:
        """레시피명 입력 행."""
        row = QHBoxLayout()
        lbl = QLabel("레시피명:")
        lbl.setStyleSheet(f"color: {UITheme.TEXT_SECONDARY};")
        row.addWidget(lbl)
        self.name_edit = QLineEdit()
        self.name_edit.setStyleSheet(UIStyles.get_input_style())
        row.addWidget(self.name_edit)
        return row

    def _build_company_type_row(self) -> QHBoxLayout:
        """거래처 + 제품종류 입력 행 (콤보 + 추가/삭제 버튼)."""
        row = QHBoxLayout()
        lbl_company = QLabel("거래처:")
        lbl_company.setStyleSheet(f"color: {UITheme.TEXT_SECONDARY};")
        row.addWidget(lbl_company)
        self.company_combo = QComboBox()
        self.company_combo.setEditable(False)
        self.company_combo.setMinimumWidth(150)
        self.company_combo.setStyleSheet(UIStyles.get_input_style())
        row.addWidget(self.company_combo)
        row.addWidget(self._make_category_btn("+", lambda: self._add_category('company', self.company_combo)))
        row.addWidget(self._make_category_btn("-", lambda: self._delete_category('company', self.company_combo)))
        row.addSpacing(15)

        lbl_type = QLabel("제품종류:")
        lbl_type.setStyleSheet(f"color: {UITheme.TEXT_SECONDARY};")
        row.addWidget(lbl_type)
        self.product_type_combo = QComboBox()
        self.product_type_combo.setEditable(False)
        self.product_type_combo.setMinimumWidth(150)
        self.product_type_combo.setStyleSheet(UIStyles.get_input_style())
        row.addWidget(self.product_type_combo)
        row.addWidget(self._make_category_btn("+", lambda: self._add_category('product_type', self.product_type_combo)))
        row.addWidget(self._make_category_btn("-", lambda: self._delete_category('product_type', self.product_type_combo)))
        row.addStretch()
        return row

    def _build_drug_period_row(self) -> QHBoxLayout:
        """약품 + 착용기간 입력 행."""
        row = QHBoxLayout()
        lbl_drug = QLabel("약품:")
        lbl_drug.setStyleSheet(f"color: {UITheme.TEXT_SECONDARY};")
        row.addWidget(lbl_drug)
        self.drug_edit = QLineEdit()
        self.drug_edit.setMinimumWidth(150)
        self.drug_edit.setStyleSheet(UIStyles.get_input_style())
        row.addWidget(self.drug_edit)
        row.addSpacing(15)

        lbl_period = QLabel("착용기간:")
        lbl_period.setStyleSheet(f"color: {UITheme.TEXT_SECONDARY};")
        row.addWidget(lbl_period)
        self.wear_period_combo = QComboBox()
        self.wear_period_combo.setEditable(False)
        self.wear_period_combo.setMinimumWidth(150)
        self.wear_period_combo.setStyleSheet(UIStyles.get_input_style())
        row.addWidget(self.wear_period_combo)
        row.addWidget(self._make_category_btn("+", lambda: self._add_category('wear_period', self.wear_period_combo)))
        row.addWidget(self._make_category_btn("-", lambda: self._delete_category('wear_period', self.wear_period_combo)))
        row.addStretch()
        return row

    def _build_material_group(self) -> QGroupBox:
        """자재 목록 그룹 (테이블 + 행 추가/삭제 버튼)."""
        mat_group = QGroupBox("자재 목록")
        mat_layout = QVBoxLayout()

        self.mat_table = QTableWidget()
        self.mat_table.setColumnCount(3)
        self.mat_table.setHorizontalHeaderLabels(["품목코드", "품목명", "배합비율(%)"])
        header = self.mat_table.horizontalHeader()
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        self.mat_table.setStyleSheet(UIStyles.get_table_style())
        self.mat_table.setAlternatingRowColors(True)
        self.mat_table.verticalHeader().setVisible(False)
        mat_layout.addWidget(self.mat_table)

        mat_btn_layout = QHBoxLayout()
        add_row_btn = StyledButton("행 추가", "secondary")
        add_row_btn.clicked.connect(self._add_mat_row)
        mat_btn_layout.addWidget(add_row_btn)
        remove_row_btn = StyledButton("행 삭제", "secondary")
        remove_row_btn.clicked.connect(self._remove_mat_row)
        mat_btn_layout.addWidget(remove_row_btn)
        mat_btn_layout.addStretch()
        mat_layout.addLayout(mat_btn_layout)

        mat_group.setLayout(mat_layout)
        return mat_group

    def _build_bottom_bar(self) -> QHBoxLayout:
        """최하단 닫기 버튼."""
        bottom_layout = QHBoxLayout()
        bottom_layout.setContentsMargins(10, 0, 10, 10)
        bottom_layout.addStretch()
        close_btn = StyledButton("닫기", "secondary")
        close_btn.clicked.connect(self.close)
        bottom_layout.addWidget(close_btn)
        return bottom_layout

    def _load_categories(self):
        """분류 항목 콤보박스 로드"""
        # 거래처
        self.company_combo.clear()
        self.company_combo.addItem("", "")  # 빈 항목
        for v in self.db.get_categories('company'):
            self.company_combo.addItem(v, v)
        
        # 제품종류
        self.product_type_combo.clear()
        self.product_type_combo.addItem("", "")
        for v in self.db.get_categories('product_type'):
            self.product_type_combo.addItem(v, v)
        
        # 착용기간
        self.wear_period_combo.clear()
        self.wear_period_combo.addItem("", "")
        for v in self.db.get_categories('wear_period'):
            self.wear_period_combo.addItem(v, v)
    
    def _add_category(self, cat_type: str, combo: QComboBox):
        """분류 항목 추가"""
        type_names = {
            'company': '거래처',
            'product_type': '제품종류',
            'wear_period': '착용기간'
        }
        text, ok = QInputDialog.getText(
            self, f"{type_names[cat_type]} 추가", 
            f"새 {type_names[cat_type]}를 입력하세요:"
        )
        if ok and text.strip():
            self.db.add_category(cat_type, text.strip())
            self._load_categories()
            # 방금 추가한 항목 선택
            idx = combo.findText(text.strip())
            if idx >= 0:
                combo.setCurrentIndex(idx)
            logger.info(f"분류 추가: {cat_type} = {text.strip()}")
    
    def _delete_category(self, cat_type: str, combo: QComboBox):
        """분류 항목 삭제"""
        current = combo.currentText()
        if not current:
            QMessageBox.warning(self, "경고", "삭제할 항목을 선택하세요.")
            return
        
        type_names = {
            'company': '거래처',
            'product_type': '제품종류',
            'wear_period': '착용기간'
        }
        
        reply = QMessageBox.question(
            self, "삭제 확인",
            f"{type_names[cat_type]} '{current}'을(를) 삭제하시겠습니까?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            # DB에서 삭제
            with self.db.get_connection() as conn:
                conn.execute(
                    "DELETE FROM dhr_recipe_categories WHERE category_type = ? AND value = ?",
                    (cat_type, current)
                )
                conn.commit()
            self._load_categories()
            logger.info(f"분류 삭제: {cat_type} = {current}")
    
    def _load_recipes(self):
        """레시피 목록 로드"""
        recipes = self.db.get_recipes()
        self.recipe_table.setRowCount(len(recipes))
        for row, r in enumerate(recipes):
            self.recipe_table.setItem(row, 0, QTableWidgetItem(str(r['id'])))
            self.recipe_table.setItem(row, 1, QTableWidgetItem(str(r.get('recipe_name', ''))))
            self.recipe_table.setItem(row, 2, QTableWidgetItem(str(r.get('company', ''))))
            self.recipe_table.setItem(row, 3, QTableWidgetItem(str(r.get('product_type', ''))))
            self.recipe_table.setItem(row, 4, QTableWidgetItem(str(r.get('drug', ''))))
            self.recipe_table.setItem(row, 5, QTableWidgetItem(str(r.get('wear_period', ''))))
        self.recipe_table.resizeColumnsToContents()
    
    def _on_recipe_selected(self):
        """레시피 선택 시 편집 영역 채우기"""
        row = self.recipe_table.currentRow()
        if row < 0:
            return
        
        try:
            recipe_id = int(self.recipe_table.item(row, 0).text())
            self.current_recipe_id = recipe_id
            
            # 레시피 정보 채우기
            self.name_edit.setText(self.recipe_table.item(row, 1).text())
            
            # 콤보박스 선택
            company = self.recipe_table.item(row, 2).text()
            idx = self.company_combo.findText(company)
            self.company_combo.setCurrentIndex(idx if idx >= 0 else 0)
            
            product_type = self.recipe_table.item(row, 3).text()
            idx = self.product_type_combo.findText(product_type)
            self.product_type_combo.setCurrentIndex(idx if idx >= 0 else 0)
            
            self.drug_edit.setText(self.recipe_table.item(row, 4).text())
            
            wear_period = self.recipe_table.item(row, 5).text()
            idx = self.wear_period_combo.findText(wear_period)
            self.wear_period_combo.setCurrentIndex(idx if idx >= 0 else 0)
            
            # 자재 목록 로드
            materials = self.db.get_recipe_materials(recipe_id)
            self.mat_table.setRowCount(len(materials))
            for i, mat in enumerate(materials):
                self.mat_table.setItem(i, 0, QTableWidgetItem(str(mat.get('material_code', ''))))
                self.mat_table.setItem(i, 1, QTableWidgetItem(str(mat.get('material_name', ''))))
                self.mat_table.setItem(i, 2, QTableWidgetItem(str(mat.get('ratio', ''))))
                    
        except Exception as e:
            logger.error(f"레시피 로드 오류: {e}")
    
    def _new_recipe(self):
        """새 레시피 초기화"""
        self.current_recipe_id = None
        self.name_edit.clear()
        self.company_combo.setCurrentIndex(0)
        self.product_type_combo.setCurrentIndex(0)
        self.drug_edit.clear()
        self.wear_period_combo.setCurrentIndex(0)
        self.mat_table.setRowCount(0)
        self._add_mat_row()  # 기본 1행 추가
    
    def _add_mat_row(self):
        """자재 행 추가"""
        row = self.mat_table.rowCount()
        self.mat_table.insertRow(row)
        for col in range(3):
            self.mat_table.setItem(row, col, QTableWidgetItem(""))
    
    def _remove_mat_row(self):
        """자재 행 삭제"""
        row = self.mat_table.currentRow()
        if row >= 0:
            self.mat_table.removeRow(row)
    
    def _save_recipe(self):
        """레시피 저장"""
        name = self.name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "입력 오류", "레시피명을 입력하세요.")
            return
        
        recipe_data = {
            'recipe_name': name,
            'company': self.company_combo.currentText(),
            'product_type': self.product_type_combo.currentText(),
            'drug': self.drug_edit.text().strip(),
            'wear_period': self.wear_period_combo.currentText(),
            'default_amount': 0  # 배합량은 불러오기 시 입력
        }
        
        materials = []
        for row in range(self.mat_table.rowCount()):
            code = self.mat_table.item(row, 0).text() if self.mat_table.item(row, 0) else ""
            mat_name = self.mat_table.item(row, 1).text() if self.mat_table.item(row, 1) else ""
            ratio_text = self.mat_table.item(row, 2).text() if self.mat_table.item(row, 2) else "0"
            
            if mat_name.strip():  # 품목명이 있는 행만 저장
                try:
                    ratio = float(ratio_text) if ratio_text.strip() else 0
                except ValueError:
                    ratio = 0
                
                materials.append({
                    'material_code': code,
                    'material_name': mat_name,
                    'ratio': ratio
                })
        
        try:
            if self.current_recipe_id:
                # 수정
                self.db.update_recipe(self.current_recipe_id, recipe_data, materials)
                QMessageBox.information(self, "저장 완료", f"레시피 '{name}'이(가) 수정되었습니다.")
            else:
                # 신규
                new_id = self.db.save_recipe(recipe_data, materials)
                self.current_recipe_id = new_id
                QMessageBox.information(self, "저장 완료", f"레시피 '{name}'이(가) 저장되었습니다.")
            
            self._load_recipes()
        except Exception as e:
            logger.error(f"레시피 저장 오류: {e}")
            QMessageBox.critical(self, "오류", f"저장 중 오류가 발생했습니다.\n{e}")
    
    def _delete_recipe(self):
        """레시피 삭제"""
        row = self.recipe_table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "경고", "삭제할 레시피를 선택하세요.")
            return
        
        name = self.recipe_table.item(row, 1).text()
        reply = QMessageBox.question(
            self, "삭제 확인", 
            f"레시피 '{name}'을(를) 정말 삭제하시겠습니까?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            try:
                recipe_id = int(self.recipe_table.item(row, 0).text())
                self.db.delete_recipe(recipe_id)
                QMessageBox.information(self, "삭제 완료", f"레시피 '{name}'이(가) 삭제되었습니다.")
                self._new_recipe()
                self._load_recipes()
            except Exception as e:
                logger.error(f"레시피 삭제 오류: {e}")
                QMessageBox.critical(self, "오류", f"삭제 중 오류가 발생했습니다.\n{e}")
