# -*- coding: utf-8 -*-
"""
PDF 변환 로직 - test_pdf_quality.py의 클래스 기반 리팩토링 버전
"""
import os
import win32com.client
import fitz  # PyMuPDF
from PIL import Image, ImageEnhance, ImageFilter
import numpy as np
from PySide6.QtCore import QObject, Signal

from utils.logger import logger


class PdfConverter(QObject):
    """
    Excel 파일을 스캔 효과가 적용된 PDF로 변환하는 클래스
    """
    # 시그널 정의
    progress_updated = Signal(int, str)  # (진행률, 메시지)
    finished = Signal(bool, str)  # (성공 여부, 메시지)

    def __init__(self):
        super().__init__()
        self.temp_pdf_path = None

    def convert(self, input_excel_path, output_pdf_path, blur_radius=0.3, noise_range=25,
                contrast_factor=0.97, brightness_factor=1.05, dpi=300):
        """
        엑셀 파일을 스캔 효과가 적용된 PDF로 변환

        Args:
            input_excel_path: 입력 엑셀 파일 경로
            output_pdf_path: 출력 PDF 파일 경로
            blur_radius: 블러 효과 강도 (0.0-5.0)
            noise_range: 노이즈 효과 강도 (0-100)
            contrast_factor: 대비 조정 (0.5-1.5)
            brightness_factor: 밝기 조정 (0.5-1.5)
            dpi: 이미지 변환 해상도
        """
        try:
            # 입력 파일 확인
            if not os.path.exists(input_excel_path):
                self.finished.emit(False, f"입력 파일을 찾을 수 없습니다: {input_excel_path}")
                return

            # 임시 PDF 경로 설정
            base_dir = os.path.dirname(output_pdf_path)
            self.temp_pdf_path = os.path.join(base_dir, "temp_converter.pdf")

            # 1단계: Excel → 임시 PDF
            self.progress_updated.emit(10, "엑셀 파일을 PDF로 변환 중...")
            success, msg = self._excel_to_pdf(input_excel_path, self.temp_pdf_path)
            if not success:
                self.finished.emit(False, msg)
                return

            # 2단계: PDF → 이미지
            self.progress_updated.emit(30, "PDF를 이미지로 변환 중...")
            page_images = self._pdf_to_images(self.temp_pdf_path, dpi)
            if not page_images:
                self.finished.emit(False, "PDF를 이미지로 변환하는 데 실패했습니다.")
                return

            # 3단계: 스캔 효과 적용
            self.progress_updated.emit(50, f"스캔 효과 적용 중... (총 {len(page_images)}페이지)")
            processed_images = []
            for i, img in enumerate(page_images):
                processed_img = self._apply_scan_effects(
                    img, blur_radius, noise_range, contrast_factor, brightness_factor
                )
                processed_images.append(processed_img)
                progress = 50 + int((i + 1) / len(page_images) * 30)
                self.progress_updated.emit(progress, f"스캔 효과 적용 중... ({i+1}/{len(page_images)}페이지)")

            # 4단계: 이미지 → 최종 PDF
            self.progress_updated.emit(85, "최종 PDF 생성 중...")
            success, msg = self._images_to_pdf(processed_images, output_pdf_path)
            if not success:
                self.finished.emit(False, msg)
                return

            # 5단계: 임시 파일 정리
            self.progress_updated.emit(95, "임시 파일 정리 중...")
            self._cleanup()

            # 완료
            self.progress_updated.emit(100, "변환 완료!")
            self.finished.emit(True, f"PDF 변환이 완료되었습니다: {os.path.basename(output_pdf_path)}")

        except Exception as e:  # noqa: BLE001 — 워커 진입점: 변환 전체 실패를 UI에 전달
            logger.error(f"PDF 변환 중 오류 발생: {e}", exc_info=True)
            self.finished.emit(False, f"변환 중 오류 발생: {str(e)}")
            self._cleanup()

    def _excel_to_pdf(self, excel_path, pdf_path):
        """엑셀 파일을 PDF로 변환"""
        excel = None
        workbook = None
        try:
            excel = win32com.client.Dispatch("Excel.Application")
            excel.Visible = False
            excel.DisplayAlerts = False

            workbook = excel.Workbooks.Open(excel_path)
            workbook.Worksheets(1).ExportAsFixedFormat(0, pdf_path)

            return True, "엑셀 → PDF 변환 완료"

        except Exception as e:  # noqa: BLE001 — win32com COM 오류(com_error 등) 광역 흡수
            return False, f"엑셀 → PDF 변환 오류: {str(e)}"

        finally:
            if workbook:
                workbook.Close(SaveChanges=False)
            if excel:
                excel.Quit()

    def _pdf_to_images(self, pdf_path, dpi):
        """PDF를 이미지 목록으로 변환"""
        images = []
        try:
            doc = fitz.open(pdf_path)
            for page in doc:
                pix = page.get_pixmap(dpi=dpi)
                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                images.append(img)
            doc.close()
        except Exception as e:  # noqa: BLE001 — PyMuPDF(fitz) 렌더링 예외 광역 흡수
            logger.error(f"PDF → 이미지 변환 오류: {e}", exc_info=True)
        return images

    def _apply_scan_effects(self, image, blur_radius, noise_range, contrast_factor, brightness_factor):
        """스캔 효과 적용"""
        # 블러 효과
        processed_image = image.filter(ImageFilter.GaussianBlur(radius=blur_radius))

        # 노이즈 추가
        img_array = np.array(processed_image)
        noise = np.random.randint(-noise_range, noise_range, img_array.shape, dtype='int16')
        img_array = np.clip(img_array + noise, 0, 255).astype('uint8')
        processed_image = Image.fromarray(img_array)

        # 대비 조정
        enhancer = ImageEnhance.Contrast(processed_image)
        processed_image = enhancer.enhance(contrast_factor)

        # 밝기 조정
        enhancer = ImageEnhance.Brightness(processed_image)
        processed_image = enhancer.enhance(brightness_factor)

        return processed_image

    def _images_to_pdf(self, image_list, output_path):
        """이미지 목록을 PDF로 저장"""
        try:
            if not image_list:
                return False, "PDF로 변환할 이미지가 없습니다."

            first_image = image_list[0]
            other_images = image_list[1:]

            first_image.save(
                output_path,
                "PDF",
                resolution=100.0,
                save_all=True,
                append_images=other_images
            )

            return True, "이미지 → PDF 변환 완료"

        except (OSError, IOError) as e:
            return False, f"이미지 → PDF 변환 오류: {str(e)}"

    def _cleanup(self):
        """임시 파일 정리"""
        if self.temp_pdf_path and os.path.exists(self.temp_pdf_path):
            try:
                os.remove(self.temp_pdf_path)
            except (OSError, IOError) as e:
                logger.warning(f"임시 파일 삭제 오류: {e}")
