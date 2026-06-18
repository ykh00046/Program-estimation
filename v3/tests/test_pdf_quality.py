# -*- coding: utf-8 -*-
"""
PDF 변환 시 스캔 효과를 적용하여 사실감을 높이는 테스트 스크립트.
(엑셀 -> 임시 PDF -> 이미지 -> 효과 적용 -> 최종 PDF) 워크플로우 사용.
"""
import os
import win32com.client
import fitz  # PyMuPDF
from PIL import Image, ImageEnhance, ImageFilter
import numpy as np

# --- 설정 ---
# 테스트할 원본 엑셀 파일 경로
INPUT_EXCEL_PATH = os.path.abspath("실적서/excel/APB25111802.xlsx")
# 중간 과정에서 생성될 임시 PDF 파일 경로
TEMP_PDF_PATH = os.path.abspath("temp_high_quality.pdf")

def excel_to_pdf(excel_path: str, pdf_path: str):
    """
    엑셀 파일을 A4 인쇄 설정이 적용된 PDF로 변환합니다.
    """
    print(f"1. 엑셀 파일을 고품질 PDF로 변환 시작: '{os.path.basename(excel_path)}'")
    
    excel = None
    workbook = None
    try:
        excel = win32com.client.Dispatch("Excel.Application")
        excel.Visible = False
        excel.DisplayAlerts = False

        workbook = excel.Workbooks.Open(excel_path)
        
        # 첫 번째 시트를 PDF로 내보내기 (Type 0 = PDF)
        workbook.Worksheets(1).ExportAsFixedFormat(0, pdf_path)
        print(f"   - 임시 PDF 생성 완료: '{os.path.basename(pdf_path)}'")

    finally:
        if workbook:
            workbook.Close(SaveChanges=False)
        if excel:
            excel.Quit()
        print("   - 엑셀 프로세스 종료.")

def pdf_to_images(pdf_path: str, dpi: int = 300) -> list:
    """
    PDF 파일의 각 페이지를 Pillow 이미지 객체 목록으로 변환합니다.
    """
    print(f"2. 임시 PDF를 이미지로 변환 시작 (DPI: {dpi})...")
    images = []
    try:
        doc = fitz.open(pdf_path)
        for i, page in enumerate(doc):
            pix = page.get_pixmap(dpi=dpi)
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            images.append(img)
            print(f"   - {i+1}페이지 변환 완료.")
        doc.close()
    except Exception as e:
        print(f"   - PDF 이미지 변환 중 오류 발생: {e}")
    return images

def _apply_scan_effects_with_params(image: Image.Image, blur_radius: float, noise_range: int, contrast_factor: float, brightness_factor: float) -> Image.Image:
    """
    Pillow 이미지를 입력받아 스캔한 것처럼 보이게 하는 효과를 적용합니다. (파라미터 조절 가능)
    """
    processed_image = image.filter(ImageFilter.GaussianBlur(radius=blur_radius))
    img_array = np.array(processed_image)
    noise = np.random.randint(-noise_range, noise_range, img_array.shape, dtype='int16')
    img_array = np.clip(img_array + noise, 0, 255).astype('uint8')
    processed_image = Image.fromarray(img_array)
    enhancer = ImageEnhance.Contrast(processed_image)
    processed_image = enhancer.enhance(contrast_factor)
    enhancer = ImageEnhance.Brightness(processed_image)
    processed_image = enhancer.enhance(brightness_factor)
    return processed_image

def images_to_pdf(image_list: list, output_path: str):
    """
    Pillow 이미지 목록을 하나의 PDF 파일로 저장합니다.
    """
    if not image_list:
        print("   - PDF로 변환할 이미지가 없습니다.")
        return

    print(f"4. 효과 적용된 이미지를 최종 PDF로 저장 시작: '{os.path.basename(output_path)}'")
    
    first_image = image_list[0]
    other_images = image_list[1:]
    
    first_image.save(
        output_path, 
        "PDF", 
        resolution=100.0, 
        save_all=True, 
        append_images=other_images
    )
    print("   - 최종 PDF 저장 완료.")

def cleanup(files: list):
    """
    임시 파일들을 삭제합니다.
    """
    print("5. 임시 파일 정리 시작...")
    for f in files:
        if os.path.exists(f):
            os.remove(f)
            print(f"   - '{os.path.basename(f)}' 삭제 완료.")

def main():
    """
    메인 실행 함수
    """
    if not os.path.exists(INPUT_EXCEL_PATH):
        print(f"오류: 입력 엑셀 파일을 찾을 수 없습니다. '{INPUT_EXCEL_PATH}'")
        return

    # 1. 엑셀 -> 임시 PDF
    excel_to_pdf(INPUT_EXCEL_PATH, TEMP_PDF_PATH)

    if not os.path.exists(TEMP_PDF_PATH):
        print("오류: 엑셀을 PDF로 변환하는 데 실패했습니다.")
        return

    # 2. 임시 PDF -> 이미지 목록 (원본 이미지)
    page_images = pdf_to_images(TEMP_PDF_PATH)

    # --- 버전 1: 높은 노이즈 + 낮은 밝기 ---
    print("\n--- 버전 1: 높은 노이즈 + 낮은 밝기 ---")
    processed_images_v1 = [_apply_scan_effects_with_params(img, 0.3, 25, 0.97, 1.05) for img in page_images]
    images_to_pdf(processed_images_v1, os.path.abspath("test_scan_v1_high_noise_low_brightness.pdf"))

    # --- 버전 2: 높은 노이즈 + 중간 밝기 ---
    print("\n--- 버전 2: 높은 노이즈 + 중간 밝기 ---")
    processed_images_v2 = [_apply_scan_effects_with_params(img, 0.3, 25, 0.97, 1.10) for img in page_images]
    images_to_pdf(processed_images_v2, os.path.abspath("test_scan_v2_high_noise_medium_brightness.pdf"))

    # --- 버전 3: 높은 노이즈 + 높은 밝기 ---
    print("\n--- 버전 3: 높은 노이즈 + 높은 밝기 ---")
    processed_images_v3 = [_apply_scan_effects_with_params(img, 0.3, 25, 0.97, 1.15) for img in page_images]
    images_to_pdf(processed_images_v3, os.path.abspath("test_scan_v3_high_noise_high_brightness.pdf"))

    # 5. 임시 파일 정리
    cleanup([TEMP_PDF_PATH])

    print("\n모든 작업 완료! 결과물 PDF: 'test_scan_v1_high_noise_low_brightness.pdf', 'test_scan_v2_high_noise_medium_brightness.pdf', 'test_scan_v3_high_noise_high_brightness.pdf'")

if __name__ == "__main__":
    main()