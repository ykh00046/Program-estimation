from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QLabel,
    QComboBox, QDoubleSpinBox, QPushButton
)
from PySide6.QtCore import Signal, Qt, QEvent
from ui.styles import UIStyles, UITheme

# 빨간 테두리 스타일
HIGHLIGHT_STYLE = f"border: 1px solid {UITheme.MINT_ACCENT}; border-radius: 6px;"
NORMAL_STYLE = ""

class RecipePanel(QWidget):
    """레시피 선택 및 배합량 입력을 담당하는 패널"""
    
    recipeChanged = Signal(str)
    amountChanged = Signal(float)
    amountConfirmed = Signal() # Enter 입력 시 방출

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()
        self._setup_workflow()

    def _init_ui(self):
        layout = QHBoxLayout()
        self.setLayout(layout)
        
        # 레시피 선택
        recipe_label = QLabel("레시피 선택")
        recipe_label.setStyleSheet(f"color: {UITheme.TEXT_PRIMARY}; font-weight: 600;")
        layout.addWidget(recipe_label)
        self.recipe_combo = QComboBox()
        self.recipe_combo.setMinimumWidth(200)
        self.recipe_combo.currentTextChanged.connect(self._on_recipe_changed)
        layout.addWidget(self.recipe_combo)

        # 배합 레시피 편집 진입점 (PDCA #37) — 클릭 처리는 MainWindow가 배선
        self.edit_recipes_btn = QPushButton("레시피 편집")
        self.edit_recipes_btn.setStyleSheet(UIStyles.get_secondary_button_style())
        layout.addWidget(self.edit_recipes_btn)

        layout.addSpacing(20)
        
        # 배합량 (화살표 버튼 제거)
        amount_label = QLabel("배합 중량 (g)")
        amount_label.setStyleSheet(f"color: {UITheme.TEXT_PRIMARY}; font-weight: 600;")
        layout.addWidget(amount_label)
        self.amount_spin = QDoubleSpinBox()
        self.amount_spin.setRange(0, 10000000)
        self.amount_spin.setDecimals(2)
        self.amount_spin.setSingleStep(100.0)
        self.amount_spin.setValue(0.0)
        
        # 화살표 버튼 숨기기
        self.amount_spin.setButtonSymbols(QDoubleSpinBox.NoButtons)
        
        # 0일 때 빈 칸으로 표시
        self.amount_spin.setSpecialValueText(" ")
        
        # 스타일 적용 (노란색 배경, 굵은 글씨)
        self.amount_spin.setStyleSheet(
            f"QDoubleSpinBox {{ background-color: {UITheme.SURFACE_ALT}; color: {UITheme.TEXT_PRIMARY}; "
            "font-weight: 600; font-size: 13pt; min-width: 120px; }"
        )
        
        self.amount_spin.valueChanged.connect(self._on_amount_changed)
        self.amount_spin.lineEdit().installEventFilter(self)
        
        layout.addWidget(self.amount_spin)
        layout.addStretch()

    def _setup_workflow(self):
        """워크플로우 초기화 - 첫 번째로 레시피 선택에 빨간 테두리"""
        self.highlight_recipe()

    def highlight_recipe(self):
        """레시피 콤보박스에 빨간 테두리"""
        self.recipe_combo.setStyleSheet(f"QComboBox {{ {HIGHLIGHT_STYLE} }}")
        self.amount_spin.setStyleSheet(
            f"QDoubleSpinBox {{ background-color: {UITheme.SURFACE_ALT}; color: {UITheme.TEXT_PRIMARY}; "
            "font-weight: 600; font-size: 13pt; min-width: 120px; }"
        )

    def highlight_amount(self):
        """배합량 입력칸에 빨간 테두리"""
        self.recipe_combo.setStyleSheet("")
        self.amount_spin.setStyleSheet(
            f"QDoubleSpinBox {{ background-color: {UITheme.SURFACE_ALT}; color: {UITheme.TEXT_PRIMARY}; "
            f"font-weight: 600; font-size: 13pt; min-width: 120px; {HIGHLIGHT_STYLE} }}"
        )

    def clear_highlights(self):
        """모든 하이라이트 제거"""
        self.recipe_combo.setStyleSheet("")
        self.amount_spin.setStyleSheet(
            f"QDoubleSpinBox {{ background-color: {UITheme.SURFACE_ALT}; color: {UITheme.TEXT_PRIMARY}; "
            "font-weight: 600; font-size: 13pt; min-width: 120px; }"
        )

    def set_recipes(self, recipes: list):
        """레시피 목록 설정"""
        self.recipe_combo.clear()
        self.recipe_combo.addItem("") # 빈 항목 추가
        self.recipe_combo.addItems(recipes)

    def get_recipe_name(self) -> str:
        return self.recipe_combo.currentText()

    def get_amount(self) -> float:
        return self.amount_spin.value()
    
    def reset(self):
        """레시피 선택과 배합량 초기화"""
        self.recipe_combo.setCurrentIndex(0)  # 빈 항목으로 설정
        self.amount_spin.setValue(0.0)
        self.highlight_recipe()  # 초기 하이라이트 상태로

    def _on_recipe_changed(self, text):
        self.recipeChanged.emit(text)
        if text:  # 레시피가 선택되면 다음으로 배합량에 하이라이트 + 포커스
            self.highlight_amount()
            self.focus_amount()  # 배합량 입력칸으로 커서 이동

    def _on_amount_changed(self, value):
        self.amountChanged.emit(value)
        if value > 0:  # 값이 입력되면 하이라이트 해제
            self.clear_highlights()

    def eventFilter(self, obj, event):
        """이벤트 필터: 배합량 SpinBox 포커스 및 Enter 키 처리"""
        if obj == self.amount_spin.lineEdit():
            if event.type() == QEvent.FocusIn:
                from PySide6.QtCore import QTimer
                if self.amount_spin.value() == 0:
                    QTimer.singleShot(0, lambda: self.amount_spin.lineEdit().clear())
                else:
                    QTimer.singleShot(0, self.amount_spin.selectAll)
            elif event.type() == QEvent.KeyPress:
                if event.key() in (Qt.Key_Return, Qt.Key_Enter):
                    self.amountConfirmed.emit()
                    return False 
        return super().eventFilter(obj, event)

    def focus_amount(self):
        """배합량 입력창으로 포커스 이동"""
        self.amount_spin.setFocus()
        self.amount_spin.selectAll()
