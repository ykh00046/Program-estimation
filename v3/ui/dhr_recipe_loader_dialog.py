"""
DHR 레시피 불러오기 다이얼로그
조건별 필터링으로 레시피 선택
"""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel,
    QComboBox, QTableWidget, QTableWidgetItem, QPushButton,
    QMessageBox, QAbstractItemView
)

from models.dhr_database import DhrDatabaseManager
from utils.logger import logger


class DhrRecipeLoaderDialog(QDialog):
    """조건별 필터링으로 레시피 선택 다이얼로그"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.db = DhrDatabaseManager()
        self.selected_recipe = None
        self.selected_materials = []
        self.setWindowTitle("레시피 불러오기")
        self.setGeometry(200, 200, 800, 500)
        self._init_ui()
        self._load_categories()
        self._load_recipes()
    
    def _init_ui(self):
        layout = QVBoxLayout()
        
        # 필터 그룹
        filter_group = QGroupBox("조건 선택")
        filter_layout = QHBoxLayout()
        
        # 거래처
        filter_layout.addWidget(QLabel("거래처:"))
        self.company_combo = QComboBox()
        self.company_combo.addItem("전체", "")
        self.company_combo.currentIndexChanged.connect(self._load_recipes)
        filter_layout.addWidget(self.company_combo)
        
        # 제품종류
        filter_layout.addWidget(QLabel("제품종류:"))
        self.product_type_combo = QComboBox()
        self.product_type_combo.addItem("전체", "")
        self.product_type_combo.currentIndexChanged.connect(self._load_recipes)
        filter_layout.addWidget(self.product_type_combo)
        
        # 약품
        filter_layout.addWidget(QLabel("약품:"))
        self.drug_combo = QComboBox()
        self.drug_combo.addItem("전체", "")
        self.drug_combo.currentIndexChanged.connect(self._load_recipes)
        filter_layout.addWidget(self.drug_combo)
        
        # 착용기간
        filter_layout.addWidget(QLabel("착용기간:"))
        self.wear_period_combo = QComboBox()
        self.wear_period_combo.addItem("전체", "")
        self.wear_period_combo.currentIndexChanged.connect(self._load_recipes)
        filter_layout.addWidget(self.wear_period_combo)
        
        filter_layout.addStretch()
        filter_group.setLayout(filter_layout)
        layout.addWidget(filter_group)
        
        # 레시피 목록 테이블
        self.table = QTableWidget()
        headers = ["ID", "레시피명", "거래처", "제품종류", "약품", "착용기간", "기본배합량"]
        self.table.setColumnCount(len(headers))
        self.table.setHorizontalHeaderLabels(headers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.doubleClicked.connect(self._on_select)
        self.table.setColumnHidden(0, True)  # ID 숨김
        layout.addWidget(self.table)
        
        # 버튼
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        select_btn = QPushButton("선택")
        select_btn.clicked.connect(self._on_select)
        btn_layout.addWidget(select_btn)
        
        cancel_btn = QPushButton("취소")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        
        layout.addLayout(btn_layout)
        self.setLayout(layout)
    
    def _load_categories(self):
        """분류 항목 로드"""
        for combo, cat_type in [
            (self.company_combo, 'company'),
            (self.product_type_combo, 'product_type'),
            (self.drug_combo, 'drug'),
            (self.wear_period_combo, 'wear_period')
        ]:
            values = self.db.get_categories(cat_type)
            for v in values:
                combo.addItem(v, v)
    
    def _load_recipes(self):
        """조건에 맞는 레시피 로드"""
        company = self.company_combo.currentData()
        product_type = self.product_type_combo.currentData()
        drug = self.drug_combo.currentData()
        wear_period = self.wear_period_combo.currentData()
        
        recipes = self.db.get_recipes(
            company=company if company else None,
            product_type=product_type if product_type else None,
            drug=drug if drug else None,
            wear_period=wear_period if wear_period else None
        )
        
        self.table.setRowCount(len(recipes))
        for row, recipe in enumerate(recipes):
            self.table.setItem(row, 0, QTableWidgetItem(str(recipe['id'])))
            self.table.setItem(row, 1, QTableWidgetItem(str(recipe.get('recipe_name', ''))))
            self.table.setItem(row, 2, QTableWidgetItem(str(recipe.get('company', ''))))
            self.table.setItem(row, 3, QTableWidgetItem(str(recipe.get('product_type', ''))))
            self.table.setItem(row, 4, QTableWidgetItem(str(recipe.get('drug', ''))))
            self.table.setItem(row, 5, QTableWidgetItem(str(recipe.get('wear_period', ''))))
            self.table.setItem(row, 6, QTableWidgetItem(str(recipe.get('default_amount', 0))))
        
        self.table.resizeColumnsToContents()
    
    def _on_select(self):
        """레시피 선택"""
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "경고", "레시피를 선택하세요.")
            return
        
        try:
            recipe_id = int(self.table.item(row, 0).text())
            recipes = self.db.get_recipes()
            
            # 선택한 레시피 찾기
            for r in recipes:
                if r['id'] == recipe_id:
                    self.selected_recipe = r
                    break
            
            if self.selected_recipe:
                self.selected_materials = self.db.get_recipe_materials(recipe_id)
                logger.info(f"레시피 선택: {self.selected_recipe['recipe_name']}")
                self.accept()
            else:
                QMessageBox.warning(self, "오류", "레시피를 찾을 수 없습니다.")
        except Exception as e:
            logger.error(f"레시피 선택 오류: {e}")
            QMessageBox.critical(self, "오류", f"레시피 선택 중 오류가 발생했습니다.\n{e}")
    
    def get_selected_data(self):
        """선택한 레시피와 자재 목록 반환"""
        return self.selected_recipe, self.selected_materials
