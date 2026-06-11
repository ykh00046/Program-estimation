"""

배합 기록 조회 다이얼로그

실적서 출력 기능을 포함하여 있습니다.

"""

import os

import pandas as pd
from typing import List

from PySide6.QtWidgets import (
    QAbstractItemView, QCheckBox, QComboBox, QCompleter, QDateEdit, QDialog,
    QGridLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit, QMessageBox,
    QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout,
)
from PySide6.QtCore import QDate, Qt

from models.excel_exporter import ExcelExporter

from utils.logger import logger
from ui.styles import UIStyles, UITheme
from ui.components import StyledButton
from ui.record_ops_controller import RecordOpsController
from ui.workers import start_worker, wait_for_workers





class RecordDetailDialog(QDialog):
    """배합 기록 상세 조회 다이얼로그"""

    def __init__(self, lot_data, data_manager, effects_params, parent=None):
        super().__init__(parent)
        self.lot_data = lot_data.copy()
        self.data_manager = data_manager
        self.effects_params = effects_params
        self.parent_dialog = parent
        self.edit_mode = False
        self.setWindowTitle(f"상세 조회 - {lot_data.iloc[0]['product_lot']}")
        self.setGeometry(300, 300, 900, 600)
        self.init_ui()

    def init_ui(self):
        """UI 초기화 (기본정보 + 자재상세 + 수정/저장 바)."""
        layout = QVBoxLayout()
        layout.addWidget(self._build_info_group())
        layout.addWidget(self._build_detail_group())
        layout.addLayout(self._build_button_bar())
        self.setLayout(layout)

    def _build_info_group(self):
        """기본 정보 그리드 (제품 LOT/작업자/레시피/배합량/작업일시)."""
        info_group = QGroupBox("기본 정보")
        info_layout = QGridLayout()
        first_record = self.lot_data.iloc[0]

        info_layout.addWidget(QLabel("제품 LOT:"), 0, 0)
        info_layout.addWidget(QLabel(str(first_record['product_lot'])), 0, 1)
        info_layout.addWidget(QLabel("작업자:"), 0, 2)
        self.worker_edit = QLineEdit(str(first_record['worker']))
        self.worker_edit.setReadOnly(True)
        self.worker_edit.setStyleSheet(UIStyles.get_input_style())
        info_layout.addWidget(self.worker_edit, 0, 3)

        info_layout.addWidget(QLabel("레시피:"), 1, 0)
        info_layout.addWidget(QLabel(str(first_record['recipe_name'])), 1, 1)
        info_layout.addWidget(QLabel("배합량(g):"), 1, 2)
        self.amount_edit = QLineEdit(str(first_record['total_amount']))
        self.amount_edit.setReadOnly(True)
        self.amount_edit.setStyleSheet(UIStyles.get_input_style())
        info_layout.addWidget(self.amount_edit, 1, 3)

        info_layout.addWidget(QLabel("작업일시:"), 2, 0)
        info_layout.addWidget(QLabel(f"{first_record['work_date']} {first_record['work_time']}"), 2, 1, 1, 3)

        info_group.setLayout(info_layout)
        return info_group

    def _build_detail_group(self):
        """배합 상세 테이블 그룹."""
        detail_group = QGroupBox("배합 상세")
        detail_layout = QVBoxLayout()

        self.table = QTableWidget()
        headers = ["품목코드", "품목명", "자재LOT", "배합비율(%)", "이론계량(g)", "실제배합(g)"]
        self.table.setColumnCount(len(headers))
        self.table.setHorizontalHeaderLabels(headers)
        self.table.setRowCount(len(self.lot_data))
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)

        for row_idx, record_tuple in enumerate(self.lot_data.itertuples()):
            self.table.setItem(row_idx, 0, QTableWidgetItem(str(getattr(record_tuple, 'material_code', ''))))
            self.table.setItem(row_idx, 1, QTableWidgetItem(str(getattr(record_tuple, 'material_name', ''))))
            self.table.setItem(row_idx, 2, QTableWidgetItem(str(getattr(record_tuple, 'material_lot', ''))))
            self.table.setItem(row_idx, 3, QTableWidgetItem(str(getattr(record_tuple, 'ratio', ''))))
            self.table.setItem(row_idx, 4, QTableWidgetItem(str(getattr(record_tuple, 'theory_amount', ''))))
            self.table.setItem(row_idx, 5, QTableWidgetItem(str(getattr(record_tuple, 'actual_amount', ''))))

        self.table.resizeColumnsToContents()
        detail_layout.addWidget(self.table)
        detail_group.setLayout(detail_layout)
        return detail_group

    def _build_button_bar(self):
        """수정/저장/실적서/닫기 버튼 바."""
        button_layout = QHBoxLayout()

        self.edit_btn = StyledButton("수정 모드", "secondary")
        self.edit_btn.clicked.connect(self.toggle_edit_mode)
        button_layout.addWidget(self.edit_btn)

        self.save_btn = StyledButton("저장", "success")
        self.save_btn.clicked.connect(self.save_changes)
        self.save_btn.setEnabled(False)
        button_layout.addWidget(self.save_btn)

        button_layout.addSpacing(20)

        self.export_btn = StyledButton("실적서 출력", "secondary")
        self.export_btn.clicked.connect(self.export_report)
        button_layout.addWidget(self.export_btn)

        close_btn = StyledButton("닫기", "secondary")
        close_btn.clicked.connect(self.close)
        button_layout.addWidget(close_btn)
        return button_layout

    def toggle_edit_mode(self):
        """수정 모드 전환"""
        self.edit_mode = not self.edit_mode
        
        if self.edit_mode:
            # 수정 모드 활성화
            self.worker_edit.setReadOnly(False)
            self.amount_edit.setReadOnly(False)
            self.table.setEditTriggers(QAbstractItemView.AllEditTriggers)
            self.edit_btn.setText("수정 취소")
            self.save_btn.setEnabled(True)
            
            # 편집 가능 필드 스타일 변경 (Premium Mint)
            edit_style = f"background-color: {UITheme.ACCENT_RGBA_18}; border: 1px solid {UITheme.MINT_ACCENT}; color: {UITheme.TEXT_PRIMARY};"
            self.worker_edit.setStyleSheet(edit_style)
            self.amount_edit.setStyleSheet(edit_style)
            
            QMessageBox.information(self, "수정 모드", 
                "수정 모드가 활성화되었습니다.\n\n"
                "편집 가능한 항목:\n"
                "- 작업자\n"
                "- 배합량\n"
                "- 배합 상세 테이블 (자재LOT, 배합비율, 이론/실제 배합량)\n\n"
                "수정 후 '저장' 버튼을 클릭하세요.")
        else:
            # 수정 모드 비활성화 (원래 값으로 복원)
            first_record = self.lot_data.iloc[0]
            self.worker_edit.setText(str(first_record['worker']))
            self.amount_edit.setText(str(first_record['total_amount']))
            self.worker_edit.setReadOnly(True)
            self.amount_edit.setReadOnly(True)
            self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
            self.edit_btn.setText("수정 모드")
            self.save_btn.setEnabled(False)
            
            # 스타일 초기화
            # 스타일 초기화
            self.worker_edit.setStyleSheet(UIStyles.get_input_style())
            self.amount_edit.setStyleSheet(UIStyles.get_input_style())
            
            # 테이블 데이터 복원
            for row_idx, record_tuple in enumerate(self.lot_data.itertuples()):
                self.table.setItem(row_idx, 2, QTableWidgetItem(str(getattr(record_tuple, 'material_lot', ''))))
                self.table.setItem(row_idx, 3, QTableWidgetItem(str(getattr(record_tuple, 'ratio', ''))))
                self.table.setItem(row_idx, 4, QTableWidgetItem(str(getattr(record_tuple, 'theory_amount', ''))))
                self.table.setItem(row_idx, 5, QTableWidgetItem(str(getattr(record_tuple, 'actual_amount', ''))))
    
    def save_changes(self):
        """변경 사항 저장"""
        if not self._confirm_save_changes():
            return
        try:
            form = self._collect_edit_form()
            success = self.data_manager.update_record(
                product_lot=form['product_lot'],
                worker=form['worker'],
                total_amount=form['amount'],
                materials=form['materials'],
            )
            self._handle_update_result(success, form['product_lot'])
        except ValueError as e:
            QMessageBox.warning(self, "입력 오류", f"숫자 형식이 올바르지 않습니다.\n{e}")
        except Exception as e:
            logger.error(f"기록 수정 오류: {e}")
            QMessageBox.critical(self, "오류", f"기록 수정 중 오류가 발생했습니다.\n{e}")

    def _confirm_save_changes(self) -> bool:
        """수정 확인 다이얼로그. Yes만 True."""
        reply = QMessageBox.question(
            self, "수정 확인",
            "정말 기록을 수정하시겠습니까?\n\n이 작업은 되돌릴 수 없습니다.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        return reply == QMessageBox.Yes

    def _collect_edit_form(self) -> dict:
        """편집 폼의 값과 테이블 데이터를 수집해 dict로 반환."""
        rows = [
            [
                self.table.item(r, c).text() if self.table.item(r, c) else ""
                for c in range(self.table.columnCount())
            ]
            for r in range(self.table.rowCount())
        ]
        return {
            'product_lot': self.lot_data.iloc[0]['product_lot'],
            'worker': self.worker_edit.text().strip(),
            'amount': float(self.amount_edit.text().strip()),
            'materials': self._collect_material_updates_from_rows(rows),
        }

    @staticmethod
    def _collect_material_updates_from_rows(rows: List[List[str]]) -> List[dict]:
        """테이블 행(문자열 리스트)에서 자재 업데이트 dict 리스트를 만든다."""
        return [
            {
                'material_code': r[0],
                'material_lot': r[2],
                'ratio': float(r[3] or 0),
                'theory_amount': float(r[4] or 0),
                'actual_amount': float(r[5] or 0),
            }
            for r in rows
        ]

    def _handle_update_result(self, success: bool, product_lot: str) -> None:
        """업데이트 결과에 따라 사용자 알림 및 UI 상태를 갱신."""
        if success:
            QMessageBox.information(self, "수정 완료", "기록이 성공적으로 수정되었습니다.")
            logger.info(f"기록 수정 완료: LOT {product_lot}")
            self._exit_edit_mode()
            self._refresh_lot_data(product_lot)
        else:
            QMessageBox.warning(self, "수정 실패", "기록 수정에 실패했습니다.")

    def _exit_edit_mode(self) -> None:
        """편집 모드 종료: 위젯 ReadOnly·스타일·버튼 상태 복원."""
        self.edit_mode = False
        self.edit_btn.setText("수정 모드")
        self.save_btn.setEnabled(False)
        self.worker_edit.setReadOnly(True)
        self.amount_edit.setReadOnly(True)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.worker_edit.setStyleSheet(UIStyles.get_input_style())
        self.amount_edit.setStyleSheet(UIStyles.get_input_style())

    def _refresh_lot_data(self, product_lot: str) -> None:
        """저장 후 해당 product_lot의 lot_data 재조회."""
        self.lot_data = self.data_manager.get_all_records_df()
        self.lot_data = self.lot_data[self.lot_data['product_lot'] == product_lot]

    def export_report(self):
        """실적서 출력 (백그라운드 워커, PDCA #33)"""
        product_lot = self.lot_data.iloc[0]['product_lot']
        logger.info(f"실적서 출력 기능 실행: LOT {product_lot}")
        self._exporting_lot = product_lot
        start_worker(
            self, self.data_manager.export_existing_record,
            args=(product_lot, self.effects_params),
            use_com=True,
            busy_widgets=(self.export_btn,),
            on_result=self._on_export_done,
            on_failed=self._on_export_failed,
        )

    def _on_export_done(self, pdf_file) -> None:
        if pdf_file:
            logger.info(f"실적서 출력 완료: {pdf_file}")
            reply = QMessageBox.question(
                self, "출력 완료",
                f"엑셀/PDF 파일이 생성되었습니다.\n\nLOT: {self._exporting_lot}\n\n결과 폴더를 확인하시겠습니까?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes
            )
            if reply == QMessageBox.Yes:
                if hasattr(self.parent_dialog, '_open_output_folder'):
                    self.parent_dialog._open_output_folder()
        else:
            QMessageBox.warning(self, "출력 실패", "엑셀/PDF 파일 생성에 실패했습니다.")

    def _on_export_failed(self, message: str) -> None:
        logger.error(f"실적서 출력 오류: {message}")
        QMessageBox.critical(self, "오류", f"실적서 출력 중 오류가 발생했습니다.\n{message}")

    def closeEvent(self, event):
        """닫기 시 잔여 출력 워커 대기 — COM 워커 조기 파괴 방지 (PDCA #33)."""
        wait_for_workers(self)
        super().closeEvent(event)


class RecordViewDialog(QDialog):
    """배합 기록 조회 다이얼로그"""

    def __init__(self, data_manager, effects_params, parent=None, embedded=False):
        super().__init__(parent)
        self.data_manager = data_manager
        self.effects_params = effects_params  # 스캔 효과 파라미터 저장
        # 사이드바 페이지 임베드 모드 (PDCA #38) — 닫기 버튼 숨김 + ESC 무시
        self._embedded = bool(embedded)
        self._ops = RecordOpsController(data_manager)
        self.setWindowTitle("배합 기록 조회")
        if not self._embedded:
            self.setGeometry(200, 200, 1200, 800)
        self.init_ui()
        self.load_records()
        self._populate_items_combo()

    def reject(self):
        """임베드 모드에선 ESC가 페이지를 숨기지 않도록 무시한다 (PDCA #38)."""
        if self._embedded:
            return
        super().reject()

    def init_ui(self):
        """UI 초기화."""
        layout = QVBoxLayout()
        layout.addWidget(self._build_filter_group())
        layout.addWidget(self._build_records_table())
        layout.addWidget(self._build_aggregation_group())
        layout.addLayout(self._build_button_bar())
        self.setLayout(layout)

    def _build_filter_group(self):
        """검색 필터 (시작일/종료일/조회 버튼)."""
        filter_group = QGroupBox("검색 필터")
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("시작일:"))
        self.start_date = QDateEdit(calendarPopup=True, date=QDate.currentDate().addMonths(-1))
        filter_layout.addWidget(self.start_date)
        filter_layout.addWidget(QLabel("종료일:"))
        self.end_date = QDateEdit(calendarPopup=True, date=QDate.currentDate())
        filter_layout.addWidget(self.end_date)
        search_btn = QPushButton("조회")
        search_btn.clicked.connect(self.load_records)
        filter_layout.addWidget(search_btn)
        filter_layout.addStretch()
        filter_group.setLayout(filter_layout)
        return filter_group

    def _build_records_table(self):
        """기록 6컬럼 테이블 (선택/LOT/작업자/레시피/배합량/일시)."""
        self.table = QTableWidget()
        headers = ["선택", "제품LOT", "작업자", "레시피", "배합량", "작업일시"]
        self.table.setColumnCount(len(headers))
        self.table.setHorizontalHeaderLabels(headers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.table.doubleClicked.connect(self.show_detail)
        return self.table

    def _build_aggregation_group(self):
        """품목별 배합량 집계 그룹 (콤보 + 집계 버튼 + 결과 레이블)."""
        agg_group = QGroupBox("품목별 배합량 집계")
        agg_layout = QHBoxLayout()
        agg_layout.addWidget(QLabel("품목 선택:"))
        self.item_combo = QComboBox()
        self.item_combo.setMinimumWidth(250)
        self.item_combo.setEditable(True)
        self.item_combo.setInsertPolicy(QComboBox.NoInsert)
        self.item_combo.lineEdit().setPlaceholderText("품목명 검색...")
        agg_layout.addWidget(self.item_combo)
        agg_btn = QPushButton("집계 실행")
        agg_btn.clicked.connect(self.aggregate_by_item)
        agg_layout.addWidget(agg_btn)
        self.agg_result_label = QLabel("총 배합량: -")
        self.agg_result_label.setStyleSheet("font-weight: bold;")
        agg_layout.addWidget(self.agg_result_label)
        agg_layout.addStretch()
        agg_group.setLayout(agg_layout)
        return agg_group

    def _build_button_bar(self):
        """전체선택/해제/상세/시간체크/출력/폴더/삭제/닫기 버튼 바."""
        button_layout = QHBoxLayout()
        select_all_btn = StyledButton("전체 선택", "secondary")
        select_all_btn.clicked.connect(self.select_all)
        button_layout.addWidget(select_all_btn)

        deselect_all_btn = StyledButton("전체 해제", "secondary")
        deselect_all_btn.clicked.connect(self.deselect_all)
        button_layout.addWidget(deselect_all_btn)

        button_layout.addSpacing(20)

        detail_btn = StyledButton("상세 조회", "primary")
        detail_btn.clicked.connect(self.show_detail)
        button_layout.addWidget(detail_btn)

        self.chk_include_time_export = QCheckBox("작업시간 표시")
        self.chk_include_time_export.setChecked(True)
        button_layout.addWidget(self.chk_include_time_export)

        self.export_btn = StyledButton("엑셀/PDF 출력", "success")
        self.export_btn.clicked.connect(self.export_selected_record)
        button_layout.addWidget(self.export_btn)

        open_folder_btn = StyledButton("폴더 열기", "secondary")
        open_folder_btn.clicked.connect(self._open_output_folder)
        button_layout.addWidget(open_folder_btn)

        self.delete_btn = StyledButton("삭제", "danger")
        self.delete_btn.clicked.connect(self.delete_selected_record)
        button_layout.addWidget(self.delete_btn)

        button_layout.addStretch()

        if not self._embedded:
            close_btn = StyledButton("닫기", "secondary")
            close_btn.clicked.connect(self.close)
            button_layout.addWidget(close_btn)
        return button_layout

    def _open_output_folder(self):
        """출력물 폴더 열기"""
        try:
            # v3/실적서 폴더 경로
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            output_dir = os.path.join(base_dir, '실적서')
            
            if not os.path.exists(output_dir):
                os.makedirs(output_dir, exist_ok=True)
            
            os.startfile(output_dir)
            logger.info(f"출력 폴더 열기: {output_dir}")
        except (OSError, IOError) as e:
            logger.error(f"폴더 열기 오류: {e}")
            QMessageBox.critical(self, "오류", f"폴더를 열 수 없습니다.\n{e}")

    def _populate_items_combo(self):
        """데이터베이스에서 품목 목록을 가져와 콤보박스를 채웁니다."""
        try:
            material_names = self.data_manager.get_all_material_names()
            self.item_combo.clear()
            items = ["- 전체 품목 -"] + material_names
            self.item_combo.addItems(items)
            
            # Completer 설정 - 부분 검색 지원
            completer = self.item_combo.completer()
            completer.setFilterMode(Qt.MatchContains)  # 포함된 텍스트로 검색
            completer.setCompletionMode(QCompleter.PopupCompletion)
        except Exception as e:
            logger.error(f"품목 목록 로드 실패: {e}")
            QMessageBox.critical(self, "오류", "품목 목록을 불러오는 데 실패했습니다.")

    def aggregate_by_item(self):
        """선택된 품목의 총 배합량을 계산하고 표시합니다."""
        selected_item = self.item_combo.currentText()
        if not selected_item or selected_item == "- 전체 품목 -":
            QMessageBox.warning(self, "경고", "집계할 품목을 선택하세요.")
            return
        try:
            start_date = self.start_date.date().toString("yyyy-MM-dd")
            end_date = self.end_date.date().toString("yyyy-MM-dd")
            total_amount = self.data_manager.get_total_amount_for_item(start_date, end_date, selected_item)
            self.agg_result_label.setText(f"총 배합량: {total_amount:,.2f} g")
            logger.info(f"'{selected_item}' 집계 완료: {total_amount} g ({start_date}~{end_date})")
        except Exception as e:
            logger.error(f"품목별 집계 오류: {e}")
            QMessageBox.critical(self, "오류", "배합량을 집계하는 중 오류가 발생했습니다.")

    def load_records(self):
        """기록 로드"""
        try:
            start = self.start_date.date().toString("yyyy-MM-dd")
            end = self.end_date.date().toString("yyyy-MM-dd")
            records = self.data_manager.get_mixing_records(start_date=start, end_date=end)
            self.table.setRowCount(len(records))
            for row, record in enumerate(records):
                chk_box_item = QTableWidgetItem()
                chk_box_item.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
                chk_box_item.setCheckState(Qt.Unchecked)
                self.table.setItem(row, 0, chk_box_item)
                self.table.setItem(row, 1, QTableWidgetItem(str(record.get('product_lot', ''))))
                self.table.setItem(row, 2, QTableWidgetItem(str(record.get('worker', ''))))
                self.table.setItem(row, 3, QTableWidgetItem(str(record.get('recipe_name', ''))))
                self.table.setItem(row, 4, QTableWidgetItem(str(record.get('total_amount', ''))))
                self.table.setItem(row, 5, QTableWidgetItem(f"{record.get('work_date', '')} {record.get('work_time', '')}"))
            self.table.resizeColumnsToContents()
            self.table.setColumnWidth(0, 50)
            logger.info(f"기록 로드 완료: {len(records)}건")
        except Exception as e:
            logger.error(f"기록 로드 오류: {e}")
            QMessageBox.critical(self, "오류", "기록 로드 중 오류가 발생했습니다.")

    def select_all(self):
        """모든 기록 선택"""
        for i in range(self.table.rowCount()):
            self.table.item(i, 0).setCheckState(Qt.Checked)

    def deselect_all(self):
        """모든 기록 선택 해제"""
        for i in range(self.table.rowCount()):
            self.table.item(i, 0).setCheckState(Qt.Unchecked)

    def show_detail(self):
        """상세 조회"""
        current_row = self.table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "경고", "조회할 기록을 선택하세요.")
            return
        try:
            product_lot = self.table.item(current_row, 1).text()
            all_records_df = self.data_manager.get_all_records_df()
            lot_data = all_records_df[all_records_df['product_lot'] == product_lot]
            if not lot_data.empty:
                # 상세 다이얼로그에 효과 파라미터 전달
                detail_dialog = RecordDetailDialog(lot_data, self.data_manager, self.effects_params, self)
                detail_dialog.exec()
            else:
                QMessageBox.warning(self, "오류", f"LOT 번호 '{product_lot}'에 대한 상세 데이터를 찾을 수 없습니다.")
        except Exception as e:
            logger.error(f"상세 조회 오류: {e}")
            QMessageBox.critical(self, "오류", f"상세 정보를 표시하는 중 오류가 발생했습니다.\n{e}")

    def _get_checked_lots(self) -> List[str]:
        """체크된 행의 제품 LOT 번호 목록을 반환합니다."""
        return [
            self.table.item(i, 1).text()
            for i in range(self.table.rowCount())
            if self.table.item(i, 0).checkState() == Qt.Checked
        ]

    def export_selected_record(self):
        """선택된 기록의 엑셀/PDF 재출력 (백그라운드 워커, PDCA #33)"""
        checked_items = self._get_checked_lots()
        if not checked_items:
            QMessageBox.warning(self, "경고", "출력할 기록을 선택하세요.")
            return

        include_time = self.chk_include_time_export.isChecked()
        start_worker(
            self, self._ops.export_records,
            args=(checked_items, self.effects_params),
            kwargs={"include_work_time": include_time},
            use_com=True,
            busy_widgets=(self.export_btn, self.delete_btn),
            on_result=self._show_export_result,
            on_failed=self._show_export_error,
        )

    def _show_export_result(self, result) -> None:
        """일괄 출력 집계 결과 알림 (워커 완료 슬롯)."""
        summary_message = f"총 {result.total}건 중 {result.success_count}건 성공, {result.fail_count}건 실패."
        if result.failed_lots:
            summary_message += f"\n실패 LOT: {', '.join(result.failed_lots)}"

        if result.success_count > 0:
            reply = QMessageBox.question(
                self, "출력 완료" if result.fail_count == 0 else "부분 출력 완료",
                f"{summary_message}\n\n결과 폴더를 확인하시겠습니까?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes
            )
            if reply == QMessageBox.Yes:
                self._open_output_folder()
        else:
            QMessageBox.warning(self, "출력 실패", summary_message)

    def _show_export_error(self, message: str) -> None:
        logger.error(f"일괄 출력 오류: {message}")
        QMessageBox.critical(self, "오류", f"출력 중 오류가 발생했습니다.\n{message}")

    def delete_selected_record(self):
        """선택된 기록 삭제"""
        checked_items = self._get_checked_lots()
        if not checked_items:
            QMessageBox.warning(self, "경고", "삭제할 기록을 선택하세요.")
            return

        reply = QMessageBox.question(self, "삭제 확인", f"총 {len(checked_items)}개의 기록을 정말 삭제하시겠습니까?\n\n이 작업은 되돌릴 수 없습니다.", QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.No:
            return

        result = self._ops.delete_records(checked_items)

        summary_message = f"총 {result.total}건 중 {result.success_count}건 삭제 성공, {result.fail_count}건 실패."
        if result.failed_lots:
            summary_message += f"\n실패 LOT: {', '.join(result.failed_lots)}"

        QMessageBox.information(self, "삭제 완료", summary_message)
        self.load_records()

    def closeEvent(self, event):
        """닫기 시 잔여 출력 워커 대기 — COM 워커 조기 파괴 방지 (PDCA #33)."""
        wait_for_workers(self)
        super().closeEvent(event)

