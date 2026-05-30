"""엑셀 및 PDF 출력 facade (PDCA #22).

공개 진입점 `ExcelExporter`는 책임을 두 협력자에 위임한다:
- Excel 작성/서식 → `models.excel_writer.ExcelWriter`
- Excel→PDF 변환 + 스캔효과 → `models.pdf_scan_renderer.PdfScanRenderer`

기존 공개 API(위치/생성자/메서드 시그니처)는 보존되어 호출자·모킹에 영향이 없다.
"""
import os
from typing import Dict, Optional

from config.config_manager import config
from utils.logger import logger
from models.excel_writer import ExcelWriter
from models.pdf_scan_renderer import PdfScanRenderer


class ExcelExporter:
    """엑셀/PDF 출력 facade — ExcelWriter/PdfScanRenderer에 위임."""

    def __init__(self) -> None:
        """초기화"""
        base_path = config.get("paths.output", "실적서")
        self.excel_folder = os.path.join(base_path, "excel")
        self.pdf_folder = os.path.join(base_path, "pdf")

        for folder in [self.excel_folder, self.pdf_folder]:
            os.makedirs(folder, exist_ok=True)

        self.cell_mapping = config.get("excel.cell_mapping", {})
        self.template_file = os.path.join("resources", "template.xlsx")

        self._writer = ExcelWriter(self.excel_folder, self.template_file, self.cell_mapping)
        self._pdf = PdfScanRenderer(self.pdf_folder, self.excel_folder)
        logger.debug(f"ExcelExporter 초기화: excel={self.excel_folder}, pdf={self.pdf_folder}")

    def export_to_excel(self, data: Dict, include_image: bool = False,
                        image_path: Optional[str] = None,
                        include_work_time: bool = True) -> Optional[str]:
        """배합 기록을 엑셀 파일로 출력 (ExcelWriter에 위임)."""
        # 공개 속성(excel_folder/template_file/cell_mapping)의 사후 변경을 존중.
        self._writer.excel_folder = self.excel_folder
        self._writer.template_file = self.template_file
        self._writer.cell_mapping = self.cell_mapping
        return self._writer.export_to_excel(data, include_image, image_path, include_work_time)

    def export_to_pdf(self, excel_file: Optional[str], effects_params: Optional[Dict]) -> Optional[str]:
        """엑셀 파일을 스캔 효과 적용 PDF로 변환 (PdfScanRenderer에 위임)."""
        self._pdf.pdf_folder = self.pdf_folder
        self._pdf.excel_folder = self.excel_folder
        return self._pdf.export_to_pdf(excel_file, effects_params)
