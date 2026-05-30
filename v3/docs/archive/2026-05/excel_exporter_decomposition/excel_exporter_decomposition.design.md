# ExcelExporter 책임 분해 설계서 (PDCA #22)

> **Feature**: excel_exporter_decomposition
> **Plan**: [../../01-plan/features/excel_exporter_decomposition.plan.md](../../01-plan/features/excel_exporter_decomposition.plan.md)
> **Author**: AI Assistant
> **Created**: 2026-05-31
> **Status**: ✅ Design (gap-detector 98% 반영: facade 재동기화 코드블록 명시)
> **PDCA Cycle**: #22

---

## 1. 설계 원칙
- **공개 API 비트 보존**: `models.excel_exporter.ExcelExporter`(무인자 생성자 + `export_to_excel`/`export_to_pdf`)는 facade로 유지. 모킹/호출 전부 무영향.
- **무동작변경**: 로직(셀 매핑, 스캔 파라미터 기본값, 예외 처리, 로그 메시지) 그대로 이동.
- **폴더 생성은 facade 단일 책임**: facade가 makedirs 후 경로를 헬퍼에 주입. 헬퍼는 디렉토리 생성 안 함(주입 경로 신뢰).
- **Python 3.9 / typing 유지.**

## 2. 모듈/클래스 구조

```
models/excel_writer.py        ExcelWriter      (openpyxl 작성/서식)
models/pdf_scan_renderer.py   PdfScanRenderer  (win32com→fitz→PIL 파이프라인)
models/excel_exporter.py      ExcelExporter    (facade, 기존 위치/이름 유지)
```

### 2.1 ExcelWriter (`models/excel_writer.py`)
```python
class ExcelWriter:
    def __init__(self, excel_folder: str, template_file: str, cell_mapping: Dict) -> None
    def export_to_excel(self, data, include_image=False, image_path=None, include_work_time=True) -> Optional[str]
    # 이하 private 그대로 이동
    def _fill_excel_data(self, ws, data, include_work_time=True) -> None
    def _format_worksheet(self, ws, data_end_row) -> None
    def _add_image_to_worksheet(self, ws, image_path) -> bool
    def _delete_empty_rows(self, ws, data_end_row) -> None
    def _apply_cell_merges(self, ws, data_end_row) -> None
    def _apply_borders(self, ws, data_end_row) -> None
```
- import: `os, shutil, warnings, typing, openpyxl(load_workbook, OpenpyxlImage, Border/Side/Alignment), logger`.
- `self.excel_folder/self.template_file/self.cell_mapping` 사용 위치는 현행과 동일.

### 2.2 PdfScanRenderer (`models/pdf_scan_renderer.py`)
```python
class PdfScanRenderer:
    def __init__(self, pdf_folder: str, excel_folder: str) -> None  # excel_folder는 temp_ 파일 위치
    def export_to_pdf(self, excel_file, effects_params) -> Optional[str]
    def _excel_to_temp_pdf(self, excel_path, pdf_path) -> None       # win32com
    def _pdf_to_images(self, pdf_path, params) -> List["Image.Image"] # fitz
    def _apply_scan_effects(self, image, params) -> "Image.Image"     # PIL/numpy
    def _images_to_final_pdf(self, image_list, output_path) -> None
    def _cleanup(self, files) -> None
```
- import: `os, typing, win32com.client, fitz, PIL(Image/ImageEnhance/ImageFilter), numpy, logger`.
- `export_to_pdf`의 `final_pdf_path`(self.pdf_folder), `temp_pdf_path`(self.excel_folder) 계산 현행 유지.

### 2.3 ExcelExporter facade (`models/excel_exporter.py`)
```python
from models.excel_writer import ExcelWriter
from models.pdf_scan_renderer import PdfScanRenderer

class ExcelExporter:
    def __init__(self) -> None:
        base_path = config.get("paths.output", "실적서")
        self.excel_folder = os.path.join(base_path, "excel")
        self.pdf_folder = os.path.join(base_path, "pdf")
        for folder in [self.excel_folder, self.pdf_folder]:
            os.makedirs(folder, exist_ok=True)
        self.cell_mapping = config.get("excel.cell_mapping", {})
        self.template_file = os.path.join("resources", "template.xlsx")
        self._writer = ExcelWriter(self.excel_folder, self.template_file, self.cell_mapping)
        self._pdf = PdfScanRenderer(self.pdf_folder, self.excel_folder)
        logger.debug(...)  # 기존 메시지 유지

    def export_to_excel(self, data, include_image=False, image_path=None, include_work_time=True):
        # 공개 속성의 사후 변경(예: 테스트가 exporter.template_file 교체)을 존중
        self._writer.excel_folder = self.excel_folder
        self._writer.template_file = self.template_file
        self._writer.cell_mapping = self.cell_mapping
        return self._writer.export_to_excel(data, include_image, image_path, include_work_time)

    def export_to_pdf(self, excel_file, effects_params):
        self._pdf.pdf_folder = self.pdf_folder
        self._pdf.excel_folder = self.excel_folder
        return self._pdf.export_to_pdf(excel_file, effects_params)
```
- 기존 public 속성(`excel_folder`, `pdf_folder`, `cell_mapping`, `template_file`)도 유지(혹시 직접 접근하는 테스트/코드 대비).

## 3. 테스트 설계

### 3.1 기존 회귀 (변경 없이 통과해야)
- `test_excel_exporter.py`(export_to_excel 실동작) — facade 위임으로 동일 결과.
- `test_dhr_bulk_generator`/`test_manual_input_save_export`(facade 모킹) — 위치/이름 불변이라 그대로.

### 3.2 신규 `tests/unit/test_excel_writer.py`
- ExcelWriter를 직접 생성(`ExcelWriter(tmp_excel, template, mapping)`)하여 win32com/fitz 의존 없이 export_to_excel 단독 테스트(템플릿 없으면 None, 정상 시 파일 생성). 기존 test_excel_exporter의 setup 패턴 재사용.

### 3.3 신규 `tests/unit/test_pdf_scan_renderer.py`
- `_apply_scan_effects`(PIL 이미지 입력→출력 크기 동일), `_cleanup`(존재 파일 삭제/미존재 무시) 등 win32com 불필요한 순수 부분 단위 테스트.
- `export_to_pdf`의 "excel_file 없음→None" early-return은 win32com 없이 검증 가능.

### 3.4 전체 회귀
- `pytest tests/unit tests/integration` 통과(현 123 + 신규), stderr 노이즈 0.

## 4. 위험 재확인
| 위험 | 결정 |
|---|---|
| facade 위임 시그니처 변형 | 위치·인자·기본값 복사, test_excel_exporter 실동작으로 보증 |
| 모킹 경로 무효화 | facade 동일 모듈·이름 유지 — `patch("models.excel_exporter.ExcelExporter")` 유효 |
| win32com/fitz 미설치 환경 테스트 | 신규 테스트는 해당 의존 불필요 부분만(or import 가드) |
| 폴더 생성 중복 | facade만 makedirs, 헬퍼는 경로 주입받아 사용 |

## 5. 커밋 계획
1. `refactor(models): extract ExcelWriter (PDCA #22 A)`
2. `refactor(models): extract PdfScanRenderer (PDCA #22 B)`
3. `refactor(models): make ExcelExporter a thin facade (PDCA #22 C)`
4. `test: focused ExcelWriter/PdfScanRenderer tests (PDCA #22)`
5. `docs: PDCA #22 analysis + report`

## 6. 다음 단계
`/pdca do excel_exporter_decomposition` — 커밋 1부터, 각 단계 후 test_excel_exporter + 전체 스위트.
