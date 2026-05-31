# 대시보드 보고서 차트 임베드 설계서 (PDCA #26)

> **Feature**: chart_image_pdf_embed
> **Plan**: [../../01-plan/features/chart_image_pdf_embed.plan.md](../../01-plan/features/chart_image_pdf_embed.plan.md)
> **Author**: AI Assistant
> **Created**: 2026-05-31
> **Status**: 🔄 Design
> **PDCA Cycle**: #26

---

## 1. 설계 원칙
- **무동작변경 최소 결합**: #25 `_write_section` 시그니처 유지(4개 호출부 불변). 월별 섹션 시작행만 추적해 차트 추가.
- **네이티브 차트**: `openpyxl.chart.BarChart`로 월별 데이터 셀 참조. Qt/이미지/신규의존 없음.
- **빈 데이터 안전**: 월별 0행이면 차트 생략.
- **Python 3.9 / typing.**

## 2. 변경 (`models/dashboard_exporter.py`)

### 2.1 import
```python
from openpyxl.chart import BarChart, Reference
```

### 2.2 `_build_workbook` — 월별 섹션 직후 차트 추가
```python
monthly = self.data_manager.get_monthly_production_stats(months=6)
monthly_title_row = row
row = self._write_section(
    ws, row, "[월별 생산량 (최근 6개월)]",
    ["연월", "생산건수", "총배합량(g)"],
    [(r.get("year_month") or "", int(r.get("record_count") or 0), float(r.get("total_amount") or 0))
     for r in monthly],
)
if monthly:
    self._add_monthly_chart(ws, monthly_title_row, len(monthly))
```
- `_write_section` 레이아웃: `title_row=monthly_title_row`, `header_row=+1`, `data=+2 .. +1+count`.

### 2.3 신규 `_add_monthly_chart`
```python
def _add_monthly_chart(self, ws, title_row: int, count: int) -> None:
    header_row = title_row + 1
    data_start = title_row + 2
    data_end = data_start + count - 1
    chart = BarChart()
    chart.type = "col"
    chart.title = "월별 총 배합량(g)"
    chart.legend = None
    chart.height = 7      # cm
    chart.width = 14
    # 값: 총배합량(C열), 헤더 포함(titles_from_data) → 시리즈명
    data = Reference(ws, min_col=3, min_row=header_row, max_row=data_end)
    cats = Reference(ws, min_col=1, min_row=data_start, max_row=data_end)
    chart.add_data(data, titles_from_data=True)
    chart.set_categories(cats)
    ws.add_chart(chart, f"F{title_row}")   # 표(A~C) 우측 F열, 겹침 방지
```
- anchor `F{title_row}`: 데이터 표는 A~E열만 사용하므로 F+ 영역은 비어 충돌 없음.

### 2.4 PDF
- `export_pdf`는 변경 없음. win32com `ExportAsFixedFormat`은 시트의 네이티브 차트를 PDF에 포함하므로 자동 반영.

## 3. 중요 제약 — openpyxl 차트는 쓰기 전용
`openpyxl.load_workbook(path)`는 **차트를 다시 읽지 않는다**(write-only). 따라서 테스트는 저장본을 재오픈해 차트를 확인할 수 없고, **`_build_workbook`이 반환한 in-memory Workbook의 `ws._charts`** 로 검증해야 한다.

## 4. 테스트 설계 (`tests/unit/test_dashboard_exporter.py` 확장)
- `test_chart_present_when_monthly_data`: `exp._build_workbook(start, end)` (mock monthly 2행) → `wb.active._charts` 길이 1, 차트 title "월별 총 배합량(g)".
- `test_chart_absent_when_empty`: monthly [] → `_charts` 길이 0, export_excel 크래시 0.
- `test_export_excel_still_creates_file`: 차트 포함 워크북 save/재오픈(파일 생성) — #25 회귀.
- 기존 #25 7케이스 유지.

## 5. 위험 재확인
| 위험 | 결정 |
|---|---|
| _write_section 행 추적 오류 | title_row 기준 header/data 오프셋(+1/+2) 고정, count로 data_end 계산. 단위 테스트로 셀 범위 간접 검증(차트 존재/타이틀) |
| openpyxl 차트 재읽기 불가 | 테스트는 _build_workbook in-memory `_charts` 검증 |
| 차트-표 겹침 | anchor F열(표 A~E 밖) |
| PDF 차트 누락 | ExportAsFixedFormat 차트 포함(환경 의존, 수동/스모크 확인) |

## 6. 커밋 계획
1. `feat(models): embed monthly BarChart in dashboard report (PDCA #26)`
2. `test: dashboard report chart presence/empty-safe (PDCA #26)`
3. `docs: PDCA #26 analysis + report`

## 7. 다음 단계
`/pdca do chart_image_pdf_embed` — 구현 후 단위 테스트(_build_workbook _charts) + 전체 스위트.
