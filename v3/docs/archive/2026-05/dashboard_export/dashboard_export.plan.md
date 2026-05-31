# 대시보드 PDF/Excel 출력 (PDCA #25)

> **Feature**: dashboard_export
> **Author**: AI Assistant
> **Created**: 2026-05-31
> **Status**: ✅ Plan
> **PDCA Cycle**: #25 (신규 기능 — 사용자 가치)

---

## 1. 배경

PDCA #17에서 대시보드(KPI 4종 + 월별 차트 + 자재 TOP-10 + 작업자 통계)를 추가했으나 **화면 조회만 가능**하고, 월간 보고/공유용 파일 출력이 없다. 집계 메서드 4종은 이미 존재(`data_manager.get_monthly_production_stats/get_top_materials/get_worker_stats/get_recipe_frequency`)하므로, 이를 파일로 내보내는 기능을 추가한다.

> **참고**: #22의 `ExcelWriter`는 배합기록 **템플릿 기반**(resources/template.xlsx + cell_mapping)이라 다중 섹션 대시보드엔 직접 재사용 불가. 동일한 "models/ exporter" 컨벤션으로 신규 `DashboardExporter`(openpyxl 직접 구성)를 만든다.

## 2. 범위 (In Scope)

### Part A — DashboardExporter.export_excel (`models/dashboard_exporter.py` 신설)
openpyxl로 워크북을 직접 구성. 입력: 기간(start_date/end_date). data_manager 집계 호출 후 섹션별 작성:
- **요약(KPI)**: 당월 생산 건수 / 당월 총 배합량 / 활성 작업자 수 / 누적 레시피 종류
- **월별 생산량**(최근 6개월): year_month / record_count / total_amount
- **자재 사용량 TOP-N**: material_code / material_name / total_actual / use_count
- **작업자 통계**: worker / record_count / total_amount / avg_amount
- 생성자: `DashboardExporter(data_manager, output_folder)` → `export_excel(start_date, end_date) -> Optional[str]`
- win32com/fitz 무의존 → **단독 테스트 가능**

### Part B — DashboardExporter.export_pdf
- Part A의 Excel을 **스캔효과 없는 일반 PDF**로 변환(win32com Excel→PDF). DHR 스캔효과 파이프라인과 무관(깔끔한 보고서).
- `export_pdf(start_date, end_date) -> Optional[str]` (내부적으로 export_excel 후 변환)
- win32com 의존 — 실 Excel 필요(테스트는 early-return/경로 계산만 검증)

### Part C — UI 연동 (`ui/panels/dashboard_panel.py`)
- 기간 바(`_build_period_bar`)에 "Excel 내보내기" / "PDF 내보내기" 버튼 추가.
- 클릭 → 현재 기간(`_current_date_range`)으로 exporter 호출 → 성공 시 결과 폴더 열기 질문, 실패 시 경고.
- 데이터 0건일 때도 빈 보고서 생성(또는 "기록 없음" 안내) — 크래시 0.

### Part D — 테스트
- `tests/unit/test_dashboard_exporter.py`: export_excel가 mock data_manager로 워크북 생성·섹션/헤더·파일 생성 검증(openpyxl 로 재오픈). 빈 데이터 안전.
- 대시보드 패널 스모크: 내보내기 버튼 존재 + 클릭 위임(QMessageBox/exporter patch).

## 3. 비-범위 (Out of Scope)
- 차트 이미지의 PDF 임베드(1차는 표/수치 중심). 차트 이미지화는 후속 후보.
- 레시피 빈도 섹션(선택) — 1차는 KPI/월별/자재/작업자 4섹션.
- 스캔 효과(대시보드 보고서는 불필요).
- 이메일/클라우드 자동 전송.

## 4. 성공 기준
- [ ] `DashboardExporter.export_excel`가 4섹션 워크북 생성, 빈 데이터에도 크래시 0
- [ ] 대시보드에서 Excel/PDF 내보내기 버튼으로 파일 생성 + 결과 폴더 안내
- [ ] export_excel 단독 단위 테스트 통과(win32com 무의존)
- [ ] 전체 스위트 통과(현 144 + 신규) + 패널 스모크
- [ ] Match Rate ≥ 90%

## 5. 위험 & 완화
| 위험 | 완화 |
|---|---|
| win32com PDF 변환이 환경 의존(실 Excel) | export_excel를 핵심·테스트 대상으로, export_pdf는 best-effort(실패 시 None+경고) |
| 빈 데이터 시 차트/표 처리 | 섹션별 0행 안전 처리, "기록 없음" 행 |
| 출력 폴더 경로 | config `paths.output` 재사용(excel_exporter와 동일 규약), makedirs |
| KPI "당월" 기준 비결정성 | export_excel는 명시 기간 인자 사용, 당월 KPI는 _current_month 헬퍼로 분리(테스트는 DB 직접 검증) |

## 6. 커밋 계획
1. `feat(models): add DashboardExporter.export_excel (PDCA #25 A)`
2. `feat(models): add DashboardExporter.export_pdf via win32com (PDCA #25 B)`
3. `feat(ui): add dashboard export buttons (PDCA #25 C)`
4. `test: DashboardExporter excel + dashboard export smoke (PDCA #25 D)`
5. `docs: PDCA #25 analysis + report`

## 7. 다음 단계
`/pdca design dashboard_export` → 워크북 섹션 레이아웃/시그니처/UI 배선 확정 → `/pdca do`.
