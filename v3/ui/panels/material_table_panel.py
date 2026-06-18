from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidgetItem, QHeaderView, QMessageBox
)
from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QColor
from datetime import datetime
from qfluentwidgets import SearchLineEdit
from utils.logger import logger
from ui.components import KeyHandlingTableWidget, StyledButton
from ui.styles import UIStyles, UITheme




class MaterialTablePanel(QWidget):
    """자재 LOT 입력 및 테이블 입력을 담당하는 패널"""
    
    # 시그널 정의
    validationStatusChanged = Signal(bool) # 유효성 상태 변경 (저장 버튼 활성화용)
    amountCheckFailed = Signal() # 배합량 미입력 시 포커스 요청
    tableEditFinished = Signal() # 테이블 입력 완료 (저장 버튼 등으로 이동)
    resetRequested = Signal() # 초기화 요청 (레시피 패널도 초기화)

    def __init__(self, data_manager, parent=None):
        super().__init__(parent)
        self.data_manager = data_manager
        self.current_amount = 0.0 # 현재 배합량 저장
        self._current_highlight_row = -1  # 현재 하이라이트된 LOT 행
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout()
        self.setLayout(layout)
        layout.setContentsMargins(10, 12, 10, 10)
        layout.setSpacing(8)
        
        # 상단 바 (검색 + 액션 버튼)
        top_bar = QHBoxLayout()
        top_bar.setSpacing(8)
        
        self.search_edit = SearchLineEdit(self)
        self.search_edit.setPlaceholderText("품목코드/품목명/LOT 검색...")
        self.search_edit.textChanged.connect(self._filter_table)
        self.search_edit.setFixedHeight(34)
        top_bar.addWidget(self.search_edit, 1)
        
        # 테이블 위젯
        self.table = KeyHandlingTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels([
            "품목코드", "품목명", "배합비율(%)", "이론계량(g)", "실제배합(g)", "자재LOT", "출고일자"
        ])
        
        # 싱글 클릭으로 편집 활성화
        from PySide6.QtWidgets import QAbstractItemView
        self.table.setEditTriggers(
            QAbstractItemView.CurrentChanged | 
            QAbstractItemView.SelectedClicked |
            QAbstractItemView.AnyKeyPressed
        )
        
        # 헤더 설정
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(1, QHeaderView.Stretch) # 품목명
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.Fixed)  # 자재LOT 고정 너비
        header.resizeSection(5, 180)  # LOT 컬럼 180px 고정
        header.setSectionResizeMode(6, QHeaderView.ResizeToContents)  # 출고일자
        
        # 스타일시트 - Global UIStyles 사용
        self.table.setStyleSheet(UIStyles.get_table_style())
        
        # 줄무늬(Zebra) 효과 활성화
        self.table.setAlternatingRowColors(True)
        
        # 행 높이 증가
        self.table.verticalHeader().setDefaultSectionSize(48)
        self.table.verticalHeader().setVisible(False)
        
        # 이벤트 연결
        self.table.cellChanged.connect(self._on_cell_changed)
        self.table.lastRowEnterPressed.connect(self.tableEditFinished)
        
        # 액션 버튼 (우측)
        self.btn_auto_assign = StyledButton("LOT 자동 배정", "secondary")
        self.btn_auto_assign.setMinimumHeight(34)
        
        self.btn_clear = StyledButton("초기화 (Ctrl+R)", "secondary")
        self.btn_clear.setMinimumHeight(34)
        self.btn_clear.clicked.connect(self.clear_table)
        
        top_bar.addWidget(self.btn_auto_assign)
        top_bar.addWidget(self.btn_clear)
        
        layout.addLayout(top_bar)
        layout.addWidget(self.table)

        # LOT 자동 배정 버튼에 대한 시그널은 외부에서 연결하거나
        # Panel이 날짜를 알아야 함. set_context(work_date) 등.
        # 일단 버튼을 멤버로 저장했으니 MainWindow에서 accessible 하게 하거나,
        # signal을 만든다.
        
    # Public Methods
    
    def set_auto_assign_callback(self, callback):
        """LOT 자동 배정 버튼 클릭 시 실행할 콜백 (MainWindow가 날짜를 넘겨줘야 함)"""
        self.btn_auto_assign.clicked.connect(callback)

    def load_items(self, items):
        """레시피 아이템 로드"""
        # items: list of dict
        items = sorted(items, key=lambda x: x.get("순서", 0))
        self.table.blockSignals(True)
        self.table.setRowCount(len(items))
        for r, m in enumerate(items):
            self._set_item(r, 0, m.get("품목코드", ""), editable=False)
            self._set_item(r, 1, m.get("품목명", ""), editable=False)
            self._set_item(r, 2, f"{float(m.get('배합비율', 0.0)):.2f}", editable=False)
            self._set_item(r, 3, "", editable=False) # 이론계량
            self._set_item(r, 4, "", editable=False) # 실제배합
            self._set_item(r, 5, "", editable=True)  # 자재LOT
            self._set_item(r, 6, "", editable=False) # 출고일자
        self.table.blockSignals(False)
        self._check_validation()

    def update_theory(self, amount: float):
        """이론 배합량 업데이트"""
        self.current_amount = amount
        rowCount = self.table.rowCount()
        if rowCount == 0:
            return

        self.table.blockSignals(True)
        for r in range(rowCount):
            item = self.table.item(r, 2) # 배합비율
            if item is None:
                continue
            try:
                ratio = float(item.text())
            except ValueError:
                ratio = 0.0
            
            theory = amount * (ratio / 100.0)
            self._set_item(r, 3, f"{theory:.3f}", editable=False)
            self._set_item(r, 4, f"{theory:.3f}", editable=False)
        self.table.blockSignals(False)
        self._check_validation()

    def auto_assign_lots(self, work_date: str):
        """자재별로 자동 LOT 배정 실행"""
        if not work_date:
            QMessageBox.warning(self, "입력 오류", "작업일자를 먼저 선택하세요.")
            return
        try:
            datetime.strptime(work_date, "%Y-%m-%d")
        except ValueError:
            QMessageBox.warning(self, "입력 오류", "작업일자가 올바르지 않습니다.")
            return

        logger.info(f"자동 LOT 배정 시작 (작업일자: {work_date})")

        assigned_count = 0
        rowCount = self.table.rowCount()

        self.table.blockSignals(True)
        for r in range(rowCount):
            item_code_widget = self.table.item(r, 0)
            if not item_code_widget:
                continue

            item_code = item_code_widget.text()
            lot_numbers = self.data_manager.find_material_lot(item_code, work_date)
            lot_number = lot_numbers[0] if lot_numbers else None

            if lot_number:
                self._set_item(r, 5, lot_number, editable=True)
                logger.debug(f"LOT 배정: {item_code} -> {lot_number}")
                assigned_count += 1
            else:
                current_lot = self.table.item(r, 5).text() if self.table.item(r, 5) else ""
                if not current_lot:
                    logger.warning(f"LOT 미배정: {item_code}")

        self.table.blockSignals(False)

        if assigned_count > 0:
            QMessageBox.information(self, "배정 완료", f"{assigned_count}개의 자재 LOT이 배정되었습니다.")
        else:
            QMessageBox.warning(self, "배정 실패", "해당 일자에 맞는 자재LOT 정보를 찾을 수 없습니다.")

        self._check_validation()

    def clear_table(self):
        """테이블 입력값(자재LOT) 초기화"""
        rowCount = self.table.rowCount()
        self.table.blockSignals(True)
        for r in range(rowCount):
            item = self.table.item(r, 5)
            if item:
                item.setText("")
        self.table.blockSignals(False)
        self._check_validation()
        # 레시피/배합량도 초기화하도록 시그널 발생
        self.resetRequested.emit()

    def clear_items(self):
        """테이블 행 전체 초기화"""
        self.table.setRowCount(0)
        self._check_validation()

    def get_data(self) -> dict:
        """자재 데이터 수집 (product_lot generation 제외)"""
        data = {}
        for r in range(self.table.rowCount()):
            item_code = self.table.item(r, 0).text()
            data[item_code] = {
                '품목코드': item_code,
                '품목명': self.table.item(r, 1).text(),
                '배합비율': self._to_float(self.table.item(r, 2).text()),
                '이론계량': self._to_float(self.table.item(r, 3).text()),
                '실제배합': self._to_float(self.table.item(r, 4).text()),
                'LOT': self.table.item(r, 5).text() if self.table.item(r, 5) else ''
            }
        return data

    def is_complete(self) -> bool:
        """모든 자재 LOT 입력 여부 확인"""
        for r in range(self.table.rowCount()):
            lot_item = self.table.item(r, 5)
            if not lot_item or not lot_item.text().strip():
                return False
        return True

    def focus_first_cell(self):
        """첫 번째 자재 LOT 셀로 포커스 이동"""
        if self.table.rowCount() > 0:
            index = self.table.model().index(0, 5) # 5=자재LOT
            self.table.setCurrentIndex(index)
            self.table.setFocus()
            self.table.edit(index)
            self.highlight_lot_cell(0)  # 첫 번째 LOT 셀 하이라이트

    def highlight_lot_cell(self, row: int):
        """특정 행의 LOT 셀에 빨간 테두리 하이라이트"""
        # 이전 하이라이트 제거
        if self._current_highlight_row >= 0 and self._current_highlight_row < self.table.rowCount():
            old_item = self.table.item(self._current_highlight_row, 5)
            if old_item:
                old_item.setBackground(QColor(UITheme.ACCENT_HIGHLIGHT_BG))  # 원래 배경색
        
        # 새 하이라이트 적용
        if 0 <= row < self.table.rowCount():
            item = self.table.item(row, 5)
            if item:
                item.setBackground(QColor(UITheme.ERROR_HIGHLIGHT_BG))  # 빨간색 하이라이트
            self._current_highlight_row = row
        else:
            self._current_highlight_row = -1

    def clear_lot_highlight(self):
        """LOT 셀 하이라이트 모두 제거"""
        for r in range(self.table.rowCount()):
            item = self.table.item(r, 5)
            if item:
                item.setBackground(QColor(UITheme.ACCENT_HIGHLIGHT_BG))
        self._current_highlight_row = -1

    # Internal Methods

    def _set_item(self, row, col, text, editable=True):
        item = QTableWidgetItem(str(text))
        if not editable:
            item.setFlags(item.flags() & ~Qt.ItemIsEditable)
        
        # 5번 열(자재LOT) 배경색 강조
        if col == 5:
            item.setBackground(QColor(UITheme.ACCENT_HIGHLIGHT_BG)) 
            
        self.table.setItem(row, col, item)

    def _on_cell_changed(self, row, column):
        if column == 5:
            # 안전장치: 배합량이 0이거나 입력되지 않았으면 입력 차단
            if self.current_amount <= 0:
                item = self.table.item(row, column)
                if item and item.text().strip(): 
                    # 이미 입력된 경우 지우고 포커스 요청 시그널
                    self.table.blockSignals(True)
                    item.setText("")
                    self.table.blockSignals(False)
                    
                    QMessageBox.warning(self, "입력 순서", "배합량을 먼저 설정해주세요!")
                    self.amountCheckFailed.emit()
                    return

            # LOT 입력 시 다음 행으로 하이라이트 이동
            self._update_lot_highlight(row)
            self._check_validation()

    def _update_lot_highlight(self, completed_row: int):
        """LOT 입력 완료 시 다음 빈 LOT 셀로 하이라이트 이동"""
        for r in range(completed_row + 1, self.table.rowCount()):
            item = self.table.item(r, 5)
            if item and not item.text().strip():
                self.highlight_lot_cell(r)
                return
        # 모든 LOT 입력 완료 시 하이라이트 제거
        self.clear_lot_highlight()

    def _check_validation(self):
        """유효성 검사 및 시그널 발생"""
        self.validationStatusChanged.emit(self.is_complete())

    def _to_float(self, s: str):
        try:
            s_strip = str(s).strip()
            return float(s_strip) if s_strip else 0.0
        except (ValueError, TypeError):
            return 0.0

    def _filter_table(self, text: str):
        """검색어로 테이블 행 필터링"""
        search_text = text.lower().strip()
        
        for row in range(self.table.rowCount()):
            show_row = False
            if not search_text:
                show_row = True
            else:
                # 품목코드(0), 품목명(1), 자재LOT(5) 컬럼에서 검색
                for col in [0, 1, 5]:
                    item = self.table.item(row, col)
                    if item and search_text in item.text().lower():
                        show_row = True
                        break
            
            self.table.setRowHidden(row, not show_row)
