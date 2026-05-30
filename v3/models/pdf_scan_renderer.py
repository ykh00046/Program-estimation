"""Excel→PDF 변환 + 스캔 효과 렌더 책임 (PDCA #22).

Excel -> (win32com) Temp PDF -> (PyMuPDF) 이미지 -> (PIL/numpy) 스캔효과 -> 최종 PDF.
Excel 작성 로직과 분리되어 있다.
"""
import os
from typing import Dict, List, Optional

import win32com.client
import fitz  # PyMuPDF
from PIL import Image, ImageEnhance, ImageFilter
import numpy as np

from utils.logger import logger


class PdfScanRenderer:
    """스캔 효과가 적용된 PDF 생성 전담."""

    def __init__(self, pdf_folder: str, excel_folder: str) -> None:
        self.pdf_folder = pdf_folder
        self.excel_folder = excel_folder  # temp_ 중간 PDF 위치

    def export_to_pdf(self, excel_file: Optional[str], effects_params: Optional[Dict]) -> Optional[str]:
        """
        엑셀 파일을 스캔 효과가 적용된 PDF로 변환합니다.
        (Excel -> Temp PDF -> Image -> Effects -> Final PDF)
        """
        temp_pdf_path = None
        effects_params = effects_params or {}
        try:
            if not excel_file or not os.path.exists(excel_file):
                logger.error(f"PDF로 변환할 엑셀 파일이 없습니다: {excel_file}")
                return None

            pdf_file = excel_file.replace('.xlsx', '.pdf')
            final_pdf_path = os.path.join(self.pdf_folder, os.path.basename(pdf_file))
            temp_pdf_path = os.path.join(self.excel_folder, f"temp_{os.path.basename(pdf_file)}")

            # 1. 엑셀 -> 임시 고품질 PDF
            self._excel_to_temp_pdf(excel_file, temp_pdf_path)

            # 2. 임시 PDF -> 이미지 목록
            page_images = self._pdf_to_images(temp_pdf_path, effects_params)
            if not page_images:
                raise ValueError("PDF를 이미지로 변환하는 데 실패했습니다.")

            # 3. 각 이미지에 스캔 효과 적용
            processed_images = [self._apply_scan_effects(img, effects_params) for img in page_images]

            # 4. 효과 적용된 이미지 목록 -> 최종 PDF
            self._images_to_final_pdf(processed_images, final_pdf_path)

            logger.info(f"스캔 효과 적용 PDF 생성 완료: {final_pdf_path}")
            return final_pdf_path

        except Exception as e:
            logger.error(f"PDF 변환 전체 프로세스 오류: {e}", exc_info=True)
            return None
        finally:
            # 5. 임시 파일 정리
            self._cleanup([temp_pdf_path])

    def _excel_to_temp_pdf(self, excel_path: str, pdf_path: str) -> None:
        """엑셀 파일을 PDF로 변환 (win32com 사용)"""
        excel = None
        workbook = None
        try:
            excel = win32com.client.Dispatch("Excel.Application")
            excel.Visible = False
            excel.DisplayAlerts = False
            abs_excel_path = os.path.abspath(excel_path)
            abs_pdf_path = os.path.abspath(pdf_path)

            workbook = excel.Workbooks.Open(abs_excel_path)
            workbook.Worksheets(1).ExportAsFixedFormat(0, abs_pdf_path)
            logger.debug(f"임시 PDF 생성 완료: {pdf_path}")
        finally:
            try:
                if workbook:
                    workbook.Close(SaveChanges=False)
            except (OSError, IOError):
                logger.warning("Excel workbook 닫기 실패")
            try:
                if excel:
                    excel.Quit()
            except (OSError, IOError):
                logger.warning("Excel 프로세스 종료 실패")

    def _pdf_to_images(self, pdf_path: str, params: Dict) -> List["Image.Image"]:
        """PDF를 Pillow 이미지 목록으로 변환 (PyMuPDF 사용)"""
        images = []
        dpi = params.get("dpi", 250)
        with fitz.open(pdf_path) as doc:
            for page in doc:
                pix = page.get_pixmap(dpi=dpi)
                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                images.append(img)
        logger.debug(f"PDF를 이미지로 변환 완료: {len(images)} 페이지, DPI: {dpi}")
        return images

    def _apply_scan_effects(self, image: "Image.Image", params: Dict) -> "Image.Image":
        """이미지에 스캔 효과 적용"""
        blur = params.get("blur_radius", 0.3)
        noise = params.get("noise_range", 25)
        contrast = params.get("contrast_factor", 1.4)
        brightness = params.get("brightness_factor", 1.1)

        proc_img = image.filter(ImageFilter.GaussianBlur(radius=blur))

        img_array = np.array(proc_img)
        noise_array = np.random.randint(-noise, noise, img_array.shape, dtype='int16')
        img_array = np.clip(img_array + noise_array, 0, 255).astype('uint8')
        proc_img = Image.fromarray(img_array)

        enhancer = ImageEnhance.Contrast(proc_img)
        proc_img = enhancer.enhance(contrast)

        enhancer = ImageEnhance.Brightness(proc_img)
        proc_img = enhancer.enhance(brightness)

        return proc_img

    def _images_to_final_pdf(self, image_list: List["Image.Image"], output_path: str) -> None:
        """이미지 목록을 최종 PDF로 저장"""
        if not image_list:
            raise ValueError("PDF로 저장할 이미지가 없습니다.")

        image_list[0].save(
            output_path, "PDF", resolution=100.0, save_all=True, append_images=image_list[1:]
        )

    def _cleanup(self, files: List[Optional[str]]) -> None:
        """임시 파일 삭제"""
        for f in files:
            if f and os.path.exists(f):
                try:
                    os.remove(f)
                    logger.debug(f"임시 파일 삭제: {f}")
                except OSError as e:
                    logger.warning(f"임시 파일 삭제 실패: {f}, 오류: {e}")
