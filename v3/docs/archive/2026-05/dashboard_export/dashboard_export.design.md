# 대시보드 PDF/Excel 출력 설계서 (PDCA #25)

> **Feature**: dashboard_export
> **Plan**: [../../01-plan/features/dashboard_export.plan.md](../../01-plan/features/dashboard_export.plan.md)
> **Author**: AI Assistant
> **Created**: 2026-05-31
> **Status**: ✅ Design (gap-detector 97% 반영: 버튼 예시를 QPushButton+UIStyles로 정정, 단위 테스트 7종)
> **PDCA Cycle**: #25

---

## 1. 설계 원칙
- **데이터 재사용**: #17의 집계 메서드 4종을 그대로 호출, 로직 중복 없음.
- **테스트성**: `export_excel`은 openpyxl만 의존(win32com/fitz 무관) → mock data_manager로 단독 검증.
- **빈 데이터 안전**: 모든 섹션 0행 허용, "기록 없음" 표기.
- **SSOT 출력 경로**: `config.get("paths.output")` 재사용(excel_exporter와 동일 규약).
- **Python 3.9 / typing.**

## 2. 집계 데이터 형태 (기존, #17)
| 메서드 | 반환 키 |
|---|---|
| `get_monthly_production_stats(months)` | `year_month`, `record_count`, `total_amount` |
| `get_top_materials(limit, start_date, end_date)` | `material_code`, `material_name`, `total_actual`, `use_count` |
| `get_worker_stats(start_date, end_date)` | `worker`, `record_count`, `total_amount`, `avg_amount` |
| `get_recipe_frequency(limit, start_date, end_date)` | `recipe_name`, `run_count`, `total_amount` |

KPI(대시보드와 동일): 당월 생산건수/총량(monthly months=1에서 year_month==당월[:7] 매칭), 활성 작업자수(=len worker_stats(start=당월1일)), 누적 레시피 종류(=len recipe_frequency(limit=10000)).

## 3. DashboardExporter (`models/dashboard_exporter.py` 신설)

```python
class DashboardExporter:
    def __init__(self, data_manager, output_folder: str) -> None: ...

    def export_excel(self, start_date: Optional[str], end_date: Optional[str],
                     filename: Optional[str] = None) -> Optional[str]:
        """4섹션 단일 시트 워크북 생성 후 경로 반환(실패 시 None)."""

    def export_pdf(self, start_date: Optional[str], end_date: Optional[str]) -> Optional[str]:
        """export_excel 후 win32com으로 일반 PDF 변환(스캔효과 없음)."""

    # 내부
    def _build_workbook(self, start, end): ...        # openpyxl Workbook 구성
    def _compute_kpis(self) -> Dict: ...              # 당월 KPI 4종(now 기반)
    def _excel_to_pdf(self, xlsx, pdf) -> None: ...   # win32com ExportAsFixedFormat(0)
    @staticmethod
    def _period_label(start, end) -> str: ...         # 파일명/머리글용("전체" 또는 "start~end")
```

### 3.1 워크시트 레이아웃 (단일 시트 "대시보드", 인쇄/PDF 친화)
```
A1  배합 이력 대시보드 보고서            (제목, 굵게)
A2  기간: {start}~{end} | 생성일: {now}   (부제)
A4  [요약]
A5  당월 생산 건수 | {n}
A6  당월 총 배합량(g) | {amount}
A7  활성 작업자 수 | {n}
A8  누적 레시피 종류 | {n}
A10 [월별 생산량 (최근 6개월)]
A11 연월 | 생산건수 | 총배합량(g)        (헤더)
A12.. 데이터행
..  [자재 사용량 TOP 10]
    순위 | 품목코드 | 품목명 | 총사용량(g) | 사용횟수
..  [작업자 통계]
    작업자 | 건수 | 총량(g) | 평균(g)
```
- 수치는 **원시 숫자(g)** 로 기록(Excel 정렬/합계 가능). 헤더 굵게 + 얇은 테두리(openpyxl Border/Alignment — excel_writer 패턴 참고하되 독립 구현).
- 각 섹션 데이터 0행이면 헤더 아래 "기록 없음" 1행.
- 섹션 시작행은 이전 섹션 길이에 따라 동적 계산(헬퍼 `_write_section(ws, start_row, title, headers, rows) -> next_row`).

### 3.2 파일명 / 경로
- `output_folder = os.path.join(config.get("paths.output","실적서"), "dashboard")`, makedirs.
- 기본 파일명: `대시보드_{_period_label}.xlsx` (period_label: "전체" 또는 "{start}_{end}"). 동일 기간 재출력 시 덮어씀(단순).
- PDF: 동일 stem `.pdf`.

### 3.3 export_pdf
```python
def export_pdf(self, start, end):
    xlsx = self.export_excel(start, end)
    if not xlsx: return None
    pdf = xlsx[:-5] + ".pdf"
    try:
        self._excel_to_pdf(xlsx, pdf); return pdf
    except Exception as e:
        logger.error(...); return None
```
`_excel_to_pdf`는 win32com Dispatch→Open→Worksheets(1).ExportAsFixedFormat(0, pdf)→Close/Quit (PdfScanRenderer 보일러플레이트와 동형이나 스캔효과 없음, 독립 구현).

## 4. UI 연동 (`ui/panels/dashboard_panel.py`)

### 4.1 `_build_period_bar`에 버튼 추가
기간 콤보 + 새로고침 우측에 (기존 패널 컨벤션인 QPushButton + UIStyles 사용):
```python
self.export_excel_btn = QPushButton("Excel 내보내기")
self.export_excel_btn.setStyleSheet(UIStyles.get_secondary_button_style())
self.export_excel_btn.clicked.connect(self._export_excel)
self.export_pdf_btn = QPushButton("PDF 내보내기")
self.export_pdf_btn.setStyleSheet(UIStyles.get_secondary_button_style())
self.export_pdf_btn.clicked.connect(self._export_pdf)
```

### 4.2 핸들러
```python
def _export_excel(self):
    start, end = self._current_date_range()
    path = self._exporter.export_excel(start, end)
    self._notify_export(path)

def _export_pdf(self):
    start, end = self._current_date_range()
    path = self._exporter.export_pdf(start, end)
    self._notify_export(path)

def _notify_export(self, path):
    if path:
        reply = QMessageBox.question(self, "내보내기 완료",
            f"파일이 생성되었습니다.\n{path}\n\n폴더를 여시겠습니까?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
        if reply == QMessageBox.Yes:
            os.startfile(os.path.dirname(path))   # Windows
    else:
        QMessageBox.warning(self, "내보내기 실패", "파일 생성에 실패했습니다.")
```
- `__init__`에서 `self._exporter = DashboardExporter(data_manager, <output_folder>)`. output_folder는 config 기반(exporter 내부에서 구성하므로 data_manager만 주입 + exporter가 경로 결정). → 생성자: `DashboardExporter(data_manager)` 로 단순화하고 내부에서 config 경로 구성(테스트는 output_folder 주입 가능하도록 선택 인자).

수정: 생성자 `DashboardExporter(data_manager, output_folder: Optional[str] = None)` — None이면 config 경로.

## 5. 테스트 설계

### 5.1 `tests/unit/test_dashboard_exporter.py` (win32com 무의존)
mock data_manager + tempfile output_folder:
- `test_export_excel_creates_file`: 파일 생성 + openpyxl 재오픈 가능.
- `test_sections_and_headers`: "[요약]"/"[월별 생산량...]"/자재/작업자 섹션 머리글 + 헤더행 존재(셀 값 스캔).
- `test_top_materials_rows`: mock 3행 → 해당 행 수/값 기록.
- `test_empty_data_safe`: 모든 집계 []→ "기록 없음" 표기, 크래시 0.
- `test_period_label`: (None,None)→"전체", (s,e)→"s_e".

### 5.2 대시보드 패널 스모크 (offscreen, QMessageBox/exporter patch)
- 내보내기 버튼 2개 존재.
- `_export_excel`/`_export_pdf` 호출 시 `self._exporter.export_excel/pdf` 위임 + path 있을 때/None일 때 분기(os.startfile patch).

### 5.3 회귀
- 전체 스위트 통과(현 144 + 신규).

## 6. 위험 재확인
| 위험 | 결정 |
|---|---|
| win32com PDF 환경 의존 | export_excel가 핵심·테스트, export_pdf는 best-effort(None+경고), os.startfile/win32com은 스모크에서 patch |
| KPI 당월 now() 비결정성 | _compute_kpis는 now 기반이나 테스트는 mock 행을 당월로 맞추거나 작업자/레시피 수(len) 위주 검증 |
| 빈 데이터 | 섹션별 "기록 없음" 행 |
| os.startfile 비-Windows | Windows 전용 앱 — 그대로. 스모크는 patch |

## 7. 커밋 계획
1. `feat(models): add DashboardExporter.export_excel (PDCA #25 A)`
2. `feat(models): add DashboardExporter.export_pdf via win32com (PDCA #25 B)`
3. `feat(ui): add dashboard export buttons (PDCA #25 C)`
4. `test: DashboardExporter excel + dashboard export smoke (PDCA #25 D)`
5. `docs: PDCA #25 analysis + report`

## 8. 다음 단계
`/pdca do dashboard_export` — 커밋 1부터, 각 단계 후 단위 테스트 + 패널 스모크 + 전체 스위트.
