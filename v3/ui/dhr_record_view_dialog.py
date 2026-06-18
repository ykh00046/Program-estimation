"""
DHR 기록 조회 다이얼로그
"""
import os

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel,
    QPushButton, QDateEdit, QTableWidget, QTableWidgetItem,
    QMessageBox, QAbstractItemView
)
from PySide6.QtCore import Qt, QDate

from typing import Dict, Optional

from models.dhr_database import DhrDatabaseManager
from models.excel_exporter import ExcelExporter
from ui.workers import start_worker, wait_for_workers
from utils.logger import logger


def _run_dhr_export_job(job: Dict) -> Optional[str]:
    """DHR 실적서 출력 작업 (워커 스레드 실행 — 위젯 접근 금지, PDCA #33).

    서명 합성 → Excel 출력 → PDF 변환 → 임시 서명 파일 정리.
    성공 시 최종 PDF 경로, 실패 시 None 반환.
    """
    from models.image_processor import ImageProcessor

    img_processor = ImageProcessor(
        resources_path=job['resources_path'], config=job['signature_cfg'])
    success, msg = img_processor.create_signed_image(
        job['base_image_path'], job['signed_image_path'], job['worker'],
        debug_path=job['debug_path'],
    )
    image_to_embed = job['signed_image_path'] if success else job['base_image_path']
    if not success:
        logger.warning(f"서명 이미지 생성 실패: {msg}. 기본 이미지로 대체합니다.")

    exporter = ExcelExporter()
    excel_file = exporter.export_to_excel(
        job['export_data'],
        include_image=True,
        image_path=image_to_embed,
        include_work_time=True,
    )

    if success and os.path.exists(job['signed_image_path']):
        try:
            os.remove(job['signed_image_path'])
        except (OSError, IOError):
            pass

    if not excel_file:
        return None
    return exporter.export_to_pdf(excel_file, job['effects_params'])


class DhrRecordDetailDialog(QDialog):
    """DHR 기록 상세 조회 다이얼로그"""

    def __init__(self, record_data, details_data, effects_params, parent=None):
        super().__init__(parent)
        self.record_data = record_data
        self.details_data = details_data
        self.effects_params = effects_params
        self.setWindowTitle(f"DHR 상세 조회 - {record_data['product_lot']}")
        self.setGeometry(300, 300, 900, 600)
        self.init_ui()

    def init_ui(self):
        """UI 초기화"""
        layout = QVBoxLayout()

        # 기본 정보 표시
        info_group = QGroupBox("기본 정보")
        info_layout = QHBoxLayout()
        
        info_layout.addWidget(QLabel(f"제품 LOT: {self.record_data['product_lot']}"))
        info_layout.addWidget(QLabel(f"제품명: {self.record_data.get('product_name', '')}"))
        info_layout.addWidget(QLabel(f"작업자: {self.record_data['worker']}"))
        info_layout.addWidget(QLabel(f"배합량: {self.record_data['total_amount']}g"))
        info_layout.addWidget(QLabel(f"작업일: {self.record_data['work_date']}"))
        
        info_group.setLayout(info_layout)
        layout.addWidget(info_group)

        # 상세 테이블
        detail_group = QGroupBox("배합 상세")
        detail_layout = QVBoxLayout()

        self.table = QTableWidget()
        headers = ["품목코드", "품목명", "자재LOT", "배합비율(%)", "이론계량(g)", "실제배합(g)"]
        self.table.setColumnCount(len(headers))
        self.table.setHorizontalHeaderLabels(headers)
        self.table.setRowCount(len(self.details_data))

        for row_idx, detail in enumerate(self.details_data):
            self.table.setItem(row_idx, 0, QTableWidgetItem(str(detail.get('material_code', ''))))
            self.table.setItem(row_idx, 1, QTableWidgetItem(str(detail.get('material_name', ''))))
            self.table.setItem(row_idx, 2, QTableWidgetItem(str(detail.get('material_lot', ''))))
            self.table.setItem(row_idx, 3, QTableWidgetItem(str(detail.get('ratio', ''))))
            self.table.setItem(row_idx, 4, QTableWidgetItem(str(detail.get('theory_amount', ''))))
            self.table.setItem(row_idx, 5, QTableWidgetItem(str(detail.get('actual_amount', ''))))

        self.table.resizeColumnsToContents()
        detail_layout.addWidget(self.table)

        detail_group.setLayout(detail_layout)
        layout.addWidget(detail_group)

        # 버튼
        button_layout = QHBoxLayout()
        self.export_btn = QPushButton("엑셀/PDF 출력")
        self.export_btn.clicked.connect(self.export_report)
        button_layout.addWidget(self.export_btn)
        close_btn = QPushButton("닫기")
        close_btn.clicked.connect(self.close)
        button_layout.addWidget(close_btn)
        layout.addLayout(button_layout)
        self.setLayout(layout)

    def _collect_export_job(self) -> Dict:
        """워커에 넘길 출력 작업 페이로드 (UI 스레드에서 위젯/설정 스냅샷)."""
        from config.config_manager import config

        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        resources_path = os.path.join(base_dir, 'resources', 'signature')
        return {
            'resources_path': resources_path,
            'base_image_path': os.path.join(resources_path, 'image.jpeg'),
            'signed_image_path': os.path.join(
                base_dir, 'resources', f"temp_signed_{self.record_data['worker']}.png"),
            'debug_path': os.path.join(base_dir, '실적서', 'debug_images'),
            'signature_cfg': config.get('signature', {}),
            'worker': self.record_data['worker'],
            'effects_params': self.effects_params,
            'export_data': {
                'product_lot': self.record_data['product_lot'],
                'worker': self.record_data['worker'],
                'total_amount': self.record_data['total_amount'],
                'work_date': self.record_data['work_date'],
                'work_time': self.record_data.get('work_time', ''),
                'scale': self.record_data.get('scale', ''),
                'materials': [dict(d) for d in self.details_data]
            },
        }

    def export_report(self):
        """엑셀/PDF 출력 (백그라운드 워커, PDCA #33)"""
        job = self._collect_export_job()
        start_worker(
            self, _run_dhr_export_job, args=(job,),
            use_com=True,
            busy_widgets=(self.export_btn,),
            on_result=self._on_export_done,
            on_failed=self._on_export_failed,
        )

    def _on_export_done(self, pdf_file: Optional[str]) -> None:
        if pdf_file:
            QMessageBox.information(
                self, "출력 완료",
                f"엑셀/PDF 파일이 생성되었습니다.\n\nLOT: {self.record_data['product_lot']}")
            logger.info(f"DHR 실적서 출력 완료: {pdf_file}")
        else:
            QMessageBox.warning(self, "출력 실패", "엑셀/PDF 파일 생성에 실패했습니다.")

    def _on_export_failed(self, message: str) -> None:
        logger.error(f"DHR 실적서 출력 오류: {message}")
        QMessageBox.critical(self, "오류", f"실적서 출력 중 오류가 발생했습니다.\n{message}")

    def closeEvent(self, event):
        """닫기 시 잔여 출력 워커 대기 — COM 워커 조기 파괴 방지 (PDCA #33)."""
        wait_for_workers(self)
        super().closeEvent(event)


class DhrRecordViewDialog(QDialog):
    """DHR 기록 조회 다이얼로그"""

    def __init__(self, effects_params, parent=None):
        super().__init__(parent)
        self.db_manager = DhrDatabaseManager()
        self.effects_params = effects_params
        self.setWindowTitle("DHR 기록 조회")
        self.setGeometry(200, 200, 1000, 600)
        self.init_ui()
        self.load_records()

    def init_ui(self):
        """UI 초기화"""
        layout = QVBoxLayout()

        # 검색 필터
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
        layout.addWidget(filter_group)

        # 기록 테이블
        self.table = QTableWidget()
        headers = ["선택", "제품LOT", "제품명", "작업자", "배합량", "작업일"]
        self.table.setColumnCount(len(headers))
        self.table.setHorizontalHeaderLabels(headers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.table.doubleClicked.connect(self.show_detail)
        layout.addWidget(self.table)

        # 버튼
        button_layout = QHBoxLayout()
        select_all_btn = QPushButton("전체 선택")
        select_all_btn.clicked.connect(self.select_all)
        button_layout.addWidget(select_all_btn)
        deselect_all_btn = QPushButton("전체 해제")
        deselect_all_btn.clicked.connect(self.deselect_all)
        button_layout.addWidget(deselect_all_btn)
        button_layout.addSpacing(20)
        detail_btn = QPushButton("상세 조회")
        detail_btn.clicked.connect(self.show_detail)
        button_layout.addWidget(detail_btn)
        export_btn = QPushButton("엑셀/PDF 출력")
        export_btn.clicked.connect(self.export_selected)
        button_layout.addWidget(export_btn)
        delete_btn = QPushButton("삭제")
        delete_btn.clicked.connect(self.delete_selected)
        button_layout.addWidget(delete_btn)
        button_layout.addStretch()
        close_btn = QPushButton("닫기")
        close_btn.clicked.connect(self.close)
        button_layout.addWidget(close_btn)
        layout.addLayout(button_layout)
        self.setLayout(layout)

    def load_records(self):
        """기록 로드"""
        try:
            start = self.start_date.date().toString("yyyy-MM-dd")
            end = self.end_date.date().toString("yyyy-MM-dd")
            records = self.db_manager.get_dhr_records(start_date=start, end_date=end)
            self.table.setRowCount(len(records))
            for row, record in enumerate(records):
                chk_box_item = QTableWidgetItem()
                chk_box_item.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
                chk_box_item.setCheckState(Qt.Unchecked)
                self.table.setItem(row, 0, chk_box_item)
                self.table.setItem(row, 1, QTableWidgetItem(str(record.get('product_lot', ''))))
                self.table.setItem(row, 2, QTableWidgetItem(str(record.get('product_name', ''))))
                self.table.setItem(row, 3, QTableWidgetItem(str(record.get('worker', ''))))
                self.table.setItem(row, 4, QTableWidgetItem(str(record.get('total_amount', ''))))
                self.table.setItem(row, 5, QTableWidgetItem(str(record.get('work_date', ''))))
            self.table.resizeColumnsToContents()
            self.table.setColumnWidth(0, 50)
            logger.info(f"DHR 기록 로드 완료: {len(records)}건")
        except Exception as e:
            logger.error(f"DHR 기록 로드 오류: {e}")
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
            record = self.db_manager.get_dhr_record_by_lot(product_lot)
            if record:
                details = self.db_manager.get_dhr_details(record['id'])
                dialog = DhrRecordDetailDialog(record, details, self.effects_params, self)
                dialog.exec()
            else:
                QMessageBox.warning(self, "오류", f"LOT '{product_lot}'에 대한 데이터를 찾을 수 없습니다.")
        except Exception as e:
            logger.error(f"DHR 상세 조회 오류: {e}")
            QMessageBox.critical(self, "오류", f"상세 정보를 표시하는 중 오류가 발생했습니다.\n{e}")

    def export_selected(self):
        """선택된 기록 출력"""
        checked_lots = [self.table.item(i, 1).text() for i in range(self.table.rowCount()) 
                        if self.table.item(i, 0).checkState() == Qt.Checked]
        if not checked_lots:
            QMessageBox.warning(self, "경고", "출력할 기록을 선택하세요.")
            return
        
        success_count = 0
        for lot in checked_lots:
            record = self.db_manager.get_dhr_record_by_lot(lot)
            if record:
                details = self.db_manager.get_dhr_details(record['id'])
                try:
                    dialog = DhrRecordDetailDialog(record, details, self.effects_params, self)
                    dialog.export_report()
                    success_count += 1
                except Exception as e:
                    logger.error(f"DHR 출력 오류: LOT {lot}, {e}")
        
        QMessageBox.information(self, "출력 완료", f"{success_count}건 출력 완료")

    def delete_selected(self):
        """선택된 기록 삭제"""
        checked_items = [(i, self.table.item(i, 1).text()) for i in range(self.table.rowCount()) 
                         if self.table.item(i, 0).checkState() == Qt.Checked]
        if not checked_items:
            QMessageBox.warning(self, "경고", "삭제할 기록을 선택하세요.")
            return

        reply = QMessageBox.question(self, "삭제 확인", 
                                     f"총 {len(checked_items)}개의 기록을 정말 삭제하시겠습니까?\n\n이 작업은 되돌릴 수 없습니다.", 
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.No:
            return

        success_count = 0
        for _, lot in checked_items:
            record = self.db_manager.get_dhr_record_by_lot(lot)
            if record and self.db_manager.delete_dhr_record(record['id']):
                success_count += 1

        QMessageBox.information(self, "삭제 완료", f"{success_count}건 삭제 완료")
        self.load_records()
