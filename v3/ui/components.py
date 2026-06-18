"""
재사용 가능한 UI 컴포넌트들
공통으로 사용되는 UI 요소들을 모듈화합니다.
"""
from PySide6.QtWidgets import (
    QApplication, QDialog, QGraphicsDropShadowEffect,
    QGroupBox, QHBoxLayout, QLabel, QLineEdit, QProgressBar, QStatusBar, QStyledItemDelegate, QTableWidget, QVBoxLayout, QWidget,
)
from PySide6.QtCore import QEvent, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QValidator
from qfluentwidgets import PushButton, CardWidget, CaptionLabel, SubtitleLabel, ProgressBar
from ui.styles import UIStyles, UITheme  # 테마/스타일 임포트



def center_window(widget: QWidget):
    """위젯을 화면 중앙으로 이동시킵니다. (다중 모니터 및 프레임 고려)"""
    screen_geo = QApplication.primaryScreen().availableGeometry()
    widget_geo = widget.frameGeometry()
    center_point = screen_geo.center()
    widget_geo.moveCenter(center_point)
    widget.move(widget_geo.topLeft())

def create_group_box(title: str, widget: QWidget) -> QGroupBox:

    """QGroupBox를 생성하고 위젯을 배치합니다. (DRY 헬퍼)
    
    Args:
        title: 그룹 박스 제목
        widget: 그룹 박스 내부에 배치할 위젯
    
    Returns:
        설정된 QGroupBox
    """
    group = QGroupBox(title)
    layout = QVBoxLayout()
    layout.addWidget(widget)
    group.setLayout(layout)
    return group


def StyledButton(text: str, button_type: str = "primary", parent=None) -> PushButton:
    """Fluent-style button factory with Premium Theme."""
    btn = PushButton(text, parent)
    
    if button_type in ["primary", "success"]:
        btn.setStyleSheet(UIStyles.get_primary_button_style())
        # 특정 버튼 텍스트 색상 보정
        current_style = btn.styleSheet()
        btn.setStyleSheet(current_style + f"QPushButton {{ color: {UITheme.TEXT_ON_ACCENT}; }}")
        
    elif button_type == "danger":
        btn.setStyleSheet(UIStyles.get_danger_button_style())
        
    else:
        # Default/Secondary/Info
        btn.setStyleSheet(UIStyles.get_secondary_button_style())
        
    return btn


class LabeledField(QWidget):
    """Label + input field wrapper."""

    def __init__(self, label: str, widget: QWidget, required: bool = False, parent=None):
        super().__init__(parent)
        self.label_text = label
        self.widget = widget
        self.required = required
        self.setup_ui()
    
    def setup_ui(self):
        """UI 설정"""
        layout = QVBoxLayout()
        layout.setSpacing(6)
        
        # 라벨 설정
        label = QLabel(self.label_text.upper())
        if self.required:
            label.setText(f"{self.label_text.upper()} <span style='color: {UITheme.MINT_ACCENT};'>*</span>")
        
        label.setStyleSheet(f"color: {UITheme.TEXT_SECONDARY}; font-size: 11px; font-weight: 700; letter-spacing: 0.3px;")
        
        # 입력 위젯 스타일 적용 (Global 스타일 사용)
        # 이미 styles.py에서 전역적으로 적용되지만, 개별 위젯에 강제 적용이 필요한 경우
        # self.widget.setStyleSheet(UIStyles.get_input_style())
        
        layout.addWidget(label)
        layout.addWidget(self.widget)
        self.setLayout(layout)
    
    def get_value(self):
        """위젯 값 반환"""
        if hasattr(self.widget, 'text'):
            return self.widget.text()
        elif hasattr(self.widget, 'value'):
            return self.widget.value()
        elif hasattr(self.widget, 'currentText'):
            return self.widget.currentText()
        return None
    
    def set_value(self, value):
        """위젯 값 설정"""
        if hasattr(self.widget, 'setText'):
            self.widget.setText(str(value))
        elif hasattr(self.widget, 'setValue'):
            self.widget.setValue(value)
        elif hasattr(self.widget, 'setCurrentText'):
            self.widget.setCurrentText(str(value))
    
    def validate(self) -> bool:
        """필수 필드 검증"""
        if self.required:
            val = self.get_value()
            if val is None or (isinstance(val, str) and not val.strip()):
                self.highlight_error(True)
                return False
        self.highlight_error(False)
        return True
    
    def highlight_error(self, error: bool = True):
        """오류 하이라이트"""
        if error:
            self.widget.setStyleSheet(f"""
                QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {{
                    background-color: {UITheme.ERROR_BG};
                    border: 1px solid {UITheme.ERROR_COLOR};
                    border-radius: 6px;
                    padding: 8px 12px;
                    color: {UITheme.TEXT_PRIMARY};
                }}
            """)
        else:
            self.widget.setStyleSheet(f"""
                QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {{
                    background-color: {UITheme.FIELD_BG};
                    border: 1px solid {UITheme.BORDER_COLOR};
                    border-radius: 6px;
                    padding: 8px 12px;
                    color: {UITheme.TEXT_PRIMARY};
                }}
            """)


class InfoCard(CardWidget):
    """Info display card."""
    def __init__(self, title: str, value: str = "0", parent=None):
        super().__init__(parent)
        self.setFixedSize(280, 140)
        self.setStyleSheet(UIStyles.get_card_style())

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 15, 20, 15)
        layout.setSpacing(6)

        self.title_lbl = CaptionLabel(title)
        self.title_lbl.setStyleSheet(
            f"color: {UITheme.TEXT_SECONDARY}; font-size: 11px; font-weight: 500; letter-spacing: 0.6px;"
        )

        self.value_lbl = SubtitleLabel(value)
        self.value_lbl.setStyleSheet(
            f"color: {UITheme.TEXT_PRIMARY}; font-size: 32px; font-weight: 800;"
        )

        layout.addWidget(self.title_lbl)
        layout.addWidget(self.value_lbl)
        layout.addStretch()


class MintInfoCard(CardWidget):
    """Mint-accent KPI card."""
    def __init__(self, title: str, value: str = "0", parent=None):
        super().__init__(parent)
        self.setFixedSize(280, 140)
        self.setStyleSheet(UIStyles.get_card_style())

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 15, 20, 15)
        layout.setSpacing(6)

        self.title_lbl = CaptionLabel(title)
        self.title_lbl.setStyleSheet(
            f"color: {UITheme.TEXT_SECONDARY}; font-size: 11px; font-weight: 500; letter-spacing: 0.5px;"
        )

        self.value_lbl = SubtitleLabel(value)
        self.value_lbl.setStyleSheet(
            f"color: {UITheme.MINT_ACCENT}; font-size: 30px; font-weight: 800;"
        )

        self.p_bar = ProgressBar(self)
        self.p_bar.setFixedHeight(4)
        self.p_bar.setValue(0)

        layout.addWidget(self.title_lbl)
        layout.addWidget(self.value_lbl)
        layout.addStretch()
        layout.addWidget(self.p_bar)

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(28)
        shadow.setColor(QColor(227, 161, 47, 55))
        shadow.setOffset(0, 6)
        self.setGraphicsEffect(shadow)

    def update_value(self, val, progress=0):
        self.value_lbl.setText(str(val))
        self.p_bar.setValue(progress)


class StatusBar(QStatusBar):
    """향상된 상태바"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
    
    def setup_ui(self):
        """UI 설정"""
        # 메인 메시지 영역
        self.main_label = QLabel("준비됨")
        self.addWidget(self.main_label)
        
        # 진행 상태 표시
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setFixedWidth(200)
        self.addPermanentWidget(self.progress_bar)
        
        # 시간 표시
        self.time_label = QLabel()
        self.time_label.setStyleSheet(f"color: {UITheme.TEXT_PRIMARY};")
        self.addPermanentWidget(self.time_label)
        
        # 타이머 설정
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_time)
        self.timer.start(1000)
        
        self.update_time()
    
    def update_time(self):
        """시간 업데이트"""
        from datetime import datetime
        self.time_label.setText(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    
    def show_message(self, message: str, timeout: int = 5000):
        """상태 메시지 표시"""
        self.main_label.setText(message)
        if timeout > 0:
            QTimer.singleShot(timeout, lambda: self.main_label.setText("준비됨"))
    
    def show_progress(self, show: bool = True, value: int = 0):
        """진행 상태 표시"""
        self.progress_bar.setVisible(show)
        self.progress_bar.setValue(value)


class DataTableWidget(QTableWidget):
    """데이터 테이블 위젯"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_style()
    
    def setup_style(self):
        """스타일 설정"""
        self.setStyleSheet(UIStyles.get_table_style())
        self.setAlternatingRowColors(True)
        self.setSelectionBehavior(QTableWidget.SelectRows)
        self.setSelectionMode(QTableWidget.SingleSelection)
        self.horizontalHeader().setStretchLastSection(True)
        self.verticalHeader().setVisible(False)
        self.verticalHeader().setDefaultSectionSize(48)  # 행 높이 48px


class ToleranceValidator(QValidator):
    """허용 오차 검증기"""
    
    def __init__(self, min_val: float, max_val: float, tolerance: float = 0.01, parent=None):
        super().__init__(parent)
        self.min_val = min_val
        self.max_val = max_val
        self.tolerance = tolerance
    
    def validate(self, input_str: str, pos: int):
        """입력값 검증"""
        if not input_str:
            return QValidator.Intermediate, input_str, pos
        
        try:
            value = float(input_str)
            if self.min_val - self.tolerance <= value <= self.max_val + self.tolerance:
                return QValidator.Acceptable, input_str, pos
            else:
                return QValidator.Invalid, input_str, pos
        except ValueError:
            return QValidator.Invalid, input_str, pos


class ConfirmDialog(QDialog):
    """확인 다이얼로그"""
    
    def __init__(self, title: str, message: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(400)
        self.setup_ui(message)
    
    def setup_ui(self, message: str):
        """UI 설정"""
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        
        # 메시지
        msg_label = QLabel(message)
        msg_label.setWordWrap(True)
        layout.addWidget(msg_label)
        
        # 버튼
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        self.cancel_btn = StyledButton("취소", "secondary")
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.cancel_btn)
        
        self.confirm_btn = StyledButton("확인", "success")
        self.confirm_btn.clicked.connect(self.accept)
        btn_layout.addWidget(self.confirm_btn)
        
        layout.addLayout(btn_layout)


class LotCellDelegate(QStyledItemDelegate):
    """LOT 셀 편집 시 Enter 키로 다음 행 이동을 처리하는 Delegate"""
    
    enterPressed = Signal(int)  # 현재 행 번호 전달
    lastRowEnterPressed = Signal()  # 마지막 행에서 Enter
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._table = parent

    def createEditor(self, parent, option, index):
        editor = super().createEditor(parent, option, index)
        if isinstance(editor, QLineEdit):
            editor.installEventFilter(self)
            # 에디터 스타일 설정 (SSOT 적용)
            editor.setStyleSheet(UIStyles.get_input_style())
        return editor
    
    def updateEditorGeometry(self, editor, option, index):
        """에디터가 셀 영역 전체를 채우도록 설정"""
        editor.setGeometry(option.rect)

    def eventFilter(self, obj, event):
        if event.type() == QEvent.KeyPress:
            if event.key() in (Qt.Key_Return, Qt.Key_Enter):
                # 현재 인덱스 가져오기
                current_index = self._table.currentIndex()
                current_row = current_index.row()
                
                # 편집 완료
                self.commitData.emit(obj)
                self.closeEditor.emit(obj, QStyledItemDelegate.NoHint)
                
                # 다음 행으로 이동 또는 마지막 행 처리
                if current_row < self._table.rowCount() - 1:
                    self.enterPressed.emit(current_row)
                else:
                    self.lastRowEnterPressed.emit()
                
                return True
        return super().eventFilter(obj, event)


class KeyHandlingTableWidget(QTableWidget):
    """LOT 셀 Enter 키 네비게이션을 지원하는 테이블 위젯"""
    
    # 마지막 행 편집 완료 시그널
    lastRowEnterPressed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        
        # LOT 컬럼(5번)에 커스텀 delegate 설정 - MaterialTablePanel 전용 로직이 포함됨
        self.lot_delegate = LotCellDelegate(self)
        self.setItemDelegateForColumn(5, self.lot_delegate)
        
        # 시그널 연결
        self.lot_delegate.enterPressed.connect(self._move_to_next_row)
        self.lot_delegate.lastRowEnterPressed.connect(self.lastRowEnterPressed.emit)

    def _move_to_next_row(self, current_row):
        """다음 빈 LOT 셀로 이동 (스마트 포커스)"""
        start_row = current_row + 1
        rowCount = self.rowCount()
        
        # 다음 행부터 끝까지 빈 셀 검색
        for r in range(start_row, rowCount):
            item = self.item(r, 5) # 5=자재LOT
            # 값이 없거나 공백인 경우에만 이동
            if not item or not item.text().strip():
                next_index = self.model().index(r, 5)
                self.setCurrentIndex(next_index)
                self.edit(next_index)
                return

        # 빈 셀이 없으면 마지막 행 시그널 발생 (저장 버튼 포커스 등을 위해)
        self.lastRowEnterPressed.emit()
