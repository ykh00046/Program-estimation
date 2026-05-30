# ExcelExporter 책임 분해 (PDCA #22)

> **Feature**: excel_exporter_decomposition
> **Author**: AI Assistant
> **Created**: 2026-05-31
> **Status**: ✅ Plan
> **PDCA Cycle**: #22 (코드 검토 SRP 후보 — excel_exporter)

---

## 1. 배경

2026-05-29 코드 검토에서 `models/excel_exporter.py`(271 LOC, `ExcelExporter` 단일 클래스)가 **4개 책임**을 한 클래스에 담고 있음이 지적됨:

1. Excel 템플릿 채우기/서식 (openpyxl)
2. Excel→PDF 변환 (win32com COM)
3. PDF→이미지 렌더 (PyMuPDF/fitz)
4. 스캔 효과 합성 (PIL/numpy)

SRP 위반 + 테스트성 저하(Excel 로직만 테스트하려 해도 win32com/fitz 의존 끌고 옴).

> **참고**: record_view_dialog 책임 분해는 별도 사이클(PDCA #23)로 분리.

## 2. 제약 — 공개 API 비트 보존 (필수)

`ExcelExporter`는 광범위하게 사용·모킹됨:
- 호출: `data_manager`, `dhr_bulk_generator`, `manual_input_interface`, `record_view_dialog`, `dhr_record_view_dialog`
- 모킹: `patch("models.excel_exporter.ExcelExporter")` (test_dhr_bulk_generator, test_manual_input_save_export 다수)
- 실동작 검증: `test_excel_exporter.py`(export_to_excel), `test_normal_blend`/`test_signature_position`(export_to_excel+pdf)

→ **불변 유지 필수**: `models.excel_exporter.ExcelExporter` 위치, 무인자 생성자, `export_to_excel(data, include_image=False, image_path=None, include_work_time=True) -> Optional[str]`, `export_to_pdf(excel_file, effects_params) -> Optional[str]`.

## 3. 범위 (In Scope)

### Part A — ExcelWriter 추출 (`models/excel_writer.py` 신설)
Excel 작성/서식 책임 이전:
- `export_to_excel`, `_fill_excel_data`, `_format_worksheet`, `_add_image_to_worksheet`, `_delete_empty_rows`, `_apply_cell_merges`, `_apply_borders`
- 생성자: `ExcelWriter(excel_folder, template_file, cell_mapping)`

### Part B — PdfScanRenderer 추출 (`models/pdf_scan_renderer.py` 신설)
PDF 변환/스캔효과 책임 이전:
- `export_to_pdf`, `_excel_to_temp_pdf`, `_pdf_to_images`, `_apply_scan_effects`, `_images_to_final_pdf`, `_cleanup`
- 생성자: `PdfScanRenderer(pdf_folder, excel_folder)`

### Part C — ExcelExporter facade (`models/excel_exporter.py` 유지)
- `__init__`: 폴더/cell_mapping/template_file 구성(현행 유지) + `ExcelWriter`/`PdfScanRenderer` 인스턴스 보유
- `export_to_excel(...)` → `self._writer.export_to_excel(...)` 위임
- `export_to_pdf(...)` → `self._pdf.export_to_pdf(...)` 위임
- 공개 API/동작 100% 보존

## 4. 비-범위 (Out of Scope)
- record_view_dialog 분해 (#23)
- 출력 로직/스캔 파라미터/템플릿 셀 매핑 동작 변경
- image_processor 변경

## 5. 성공 기준
- [ ] `ExcelExporter` 공개 API/위치/생성자 불변, 동작 동일
- [ ] Excel/PDF 책임이 별도 모듈 2개로 분리, 각자 단독 테스트 가능
- [ ] `test_excel_exporter`/모킹 테스트 전부 통과(회귀 0)
- [ ] 전체 스위트 통과(현 123 + 신규)
- [ ] Match Rate ≥ 90%

## 6. 위험 & 완화
| 위험 | 완화 |
|---|---|
| facade 위임 누락/시그니처 변형 | 공개 메서드 시그니처 복사 + test_excel_exporter 실동작 검증 |
| win32com/fitz import가 모듈 분리로 깨짐 | import를 각 모듈로 이동, 동일 위치(함수내/모듈상단) 유지 |
| 모킹 경로(`models.excel_exporter.ExcelExporter`) 무효화 | facade를 동일 모듈·동일 이름으로 유지 |
| 폴더 생성 책임 중복 | facade가 폴더 생성 후 경로를 두 헬퍼에 주입(헬퍼는 makedirs 안 함) |

## 7. 커밋 계획
1. `refactor(models): extract ExcelWriter from ExcelExporter (PDCA #22 A)`
2. `refactor(models): extract PdfScanRenderer from ExcelExporter (PDCA #22 B)`
3. `refactor(models): make ExcelExporter a thin facade (PDCA #22 C)`
4. `test: add ExcelWriter/PdfScanRenderer focused tests (PDCA #22)`
5. `docs: PDCA #22 analysis + report`

## 8. 다음 단계
`/pdca design excel_exporter_decomposition` → 클래스 시그니처/위임 확정 → `/pdca do`.
