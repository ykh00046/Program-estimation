# 배합 이력 대시보드 계획서 (PDCA #17)

> **Feature**: material_usage_dashboard
> **Summary**: 누적된 `mixing_records` / `mixing_details`를 시각화하는 신규 패널 추가 (월별 생산량, 자재 사용량 TOP-N, 작업자별 통계)
> **Author**: AI Assistant
> **Created**: 2026-05-25
> **Status**: ✅ Plan
> **PDCA Cycle**: #17 (신규 기능 — 첫 사용자 가치 추가 기능)

---

## 1. 배경

PDCA #7~#16은 모두 **리팩토링/품질 개선** 사이클이었다. 이미 DB에 다음 데이터가 누적돼 있으나 **소비 UI가 전혀 없다**:

- `mixing_records` (배합 1건당 1행): 작업일, 작업자, 레시피, 총량
- `mixing_details` (배합 1건당 N행): 자재 코드/이름, 비율, 이론량, 실제량

현재 "기록 조회"는 `record_view_dialog`로 행 단위 검색만 제공. **집계/추세 시각화가 없어** 다음 질문에 즉시 답할 수 없다:

1. 이번 달 vs 지난 달 생산량 비교
2. 가장 많이 쓰는 자재 TOP 10 (재고 계획에 직결)
3. 작업자별 처리 건수 / 평균 배합량
4. 레시피별 실행 빈도

---

## 2. 범위 (In Scope)

### Part A — DB 집계 쿼리 추가 (`data_manager`)

`DataManager`에 신규 메서드 4종 추가. SQL은 기존 인덱스로 충분하므로 스키마 변경 없음.

| 메서드 | 반환 | 기간 파라미터 |
|---|---|---|
| `get_monthly_production_stats(months: int = 6)` | `List[Dict]` (year_month, record_count, total_amount) | 최근 N개월 |
| `get_top_materials(limit: int = 10, start_date, end_date)` | `List[Dict]` (material_code, material_name, total_actual, use_count) | 날짜 범위 |
| `get_worker_stats(start_date, end_date)` | `List[Dict]` (worker, record_count, total_amount, avg_amount) | 날짜 범위 |
| `get_recipe_frequency(limit: int = 10, start_date, end_date)` | `List[Dict]` (recipe_name, run_count, total_amount) | 날짜 범위 |

### Part B — DashboardPanel 신규 추가 (`ui/panels/dashboard_panel.py`)

`QWidget#DashboardPage` (styles.py에 이미 object_name 등록되어 있음) 으로 등록.

레이아웃 (수직 스택):
1. **상단 KPI 카드 4종** (당월 생산 건수 / 당월 총 배합량 / 활성 작업자 수 / 누적 레시피 종류)
2. **월별 생산량 막대 차트** (최근 6개월) — `PySide6.QtCharts.QBarSeries`
3. **자재 사용량 TOP 10 테이블** (자재명 / 총 사용량(g) / 사용 횟수)
4. **작업자별 통계 테이블** (작업자 / 건수 / 총량 / 평균)
5. 기간 선택 콤보 (최근 30일/90일/6개월/전체) + 새로고침 버튼

### Part C — 사이드바 등록 + 통합

| 위치 | 변경 |
|---|---|
| `ui/builders.py::register_sidebar_interfaces` | 4번(DHR 관리)과 5번(기록 조회) 사이에 "대시보드" 항목 추가, `FIF.PIE_SINGLE` 아이콘 |
| `ui/main_window.py::_create_panels` | `self.dashboard_panel = DashboardPanel(self.services.data_manager)` 추가 |

### Part D — 테스트

| 테스트 | 위치 | 항목 |
|---|---|---|
| 단위 — `DataManager` 집계 메서드 | `tests/unit/test_data_manager_aggregates.py` | 4종 메서드 빈DB/샘플DB 동작 |
| 단위 — `DashboardPanel` 헬퍼 | `tests/unit/test_dashboard_panel.py` | KPI 카드 텍스트, 테이블 셀 포맷 |
| 통합 — 패널 스모크 | `tests/integration/test_dashboard_panel_smoke.py` | offscreen Qt, panel 인스턴스화 |

---

## 3. 비-범위 (Out of Scope)

- 자재 재고 임계값 알림 (PDCA #18 후보)
- PDF/Excel 보고서 출력 (PDCA #19 후보)
- 다중 사용자별 권한 분리 (장기 후보)
- 외부 BI 연동

---

## 4. 의존성 / 제약

- **Python 3.9** 유지 — `typing.Optional/List/Dict` 사용
- **PySide6.QtCharts** 신규 의존 — PySide6에 기본 포함 (별도 패키지 불필요). PyInstaller `hidden-imports`에 자동 포함되는지 빌드 검증 단계에서 확인
- **UITheme 토큰만 사용** — 신규 색 도입 금지
- 차트 데이터가 0건일 때 placeholder ("아직 기록이 없습니다") 표시 필수
- SQL 인덱스 추가 불필요 (현 DB 규모 < 10K rows 가정)

---

## 5. 성공 기준

- [ ] 4종 신규 집계 메서드 단위 테스트 통과
- [ ] DashboardPanel 사이드바에서 진입 가능, 차트/테이블 정상 렌더
- [ ] 기존 79건 테스트 회귀 0건
- [ ] Match Rate >= 90%
- [ ] 빈 DB에서도 크래시 없음

---

## 6. 일정

| 단계 | 예상 |
|---|---|
| Plan + Design | 30분 |
| Do (Part A → B → C → D) | 2시간 |
| QA + Iterate | 30분 |
| Report + Archive | 15분 |

---

## 7. 위험 & 완화

| 위험 | 영향 | 완화 |
|---|---|---|
| QtCharts PyInstaller 미포함 | exe 빌드 시 import 에러 | `build.py`에 `--hidden-import=PySide6.QtCharts` 명시 (필요 시) |
| 대용량 DB에서 집계 느림 | UI 멈춤 | 1차는 동기 호출, 10K행 이상 데이터 누적 시 PDCA #18에서 비동기화 |
| 신규 색 추가 유혹 | SSOT 위반 | 디자인 검토에서 UITheme 토큰만 사용 강제 |
