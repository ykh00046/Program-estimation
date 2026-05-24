# 배합 이력 대시보드 완료 보고서 (PDCA #17)

> **Feature**: material_usage_dashboard
> **PDCA Cycle**: #17 (신규 기능 — 첫 사용자 가치 추가 사이클)
> **Author**: AI Assistant
> **Period**: 2026-05-25
> **Status**: ✅ Completed (Match Rate 100%)

---

## 1. 요약

PDCA #7~#16이 모두 리팩토링/품질 개선이었던 흐름을 깨고 **첫 신규 기능 사이클**을 완료했다. 누적된 `mixing_records`/`mixing_details` 데이터에 처음으로 **소비 UI(대시보드 패널)** 를 붙였다.

### 결과

- 신규 사이드바 항목 "대시보드" (FIF.PIE_SINGLE)
- KPI 카드 4종 (당월 건수/배합량/작업자 수/누적 레시피)
- 최근 6개월 월별 생산량 막대 차트 (QtCharts)
- 자재 사용량 TOP-10 + 작업자별 통계 테이블
- 기간 콤보 (30일/90일/6개월/전체)
- DB 집계 메서드 4종 (스키마 변경 0건)

---

## 2. 산출물

| 카테고리 | 파일 | LOC | 설명 |
|---|---|---|---|
| 신규 | `v3/ui/panels/dashboard_panel.py` | ~360 | DashboardPanel + KPI/차트/테이블 빌더 |
| 신규 | `v3/tests/unit/test_data_manager_aggregates.py` | ~210 | 집계 쿼리 단위 테스트 8건 |
| 신규 | `v3/tests/unit/test_dashboard_panel.py` | ~120 | `_format_amount` + 패널 스모크 10건 |
| 신규 | `v3/docs/01-plan/features/material_usage_dashboard.plan.md` | — | Plan |
| 신규 | `v3/docs/02-design/features/material_usage_dashboard.design.md` | — | Design |
| 신규 | `v3/docs/03-analysis/features/material_usage_dashboard.analysis.md` | — | Gap 분석 |
| 신규 | (this) | — | Report |
| 수정 | `v3/models/database.py` | +~120 | 집계 메서드 4종 추가 |
| 수정 | `v3/models/data_manager.py` | +~40 | 위임 메서드 4종 추가 |
| 수정 | `v3/ui/main_window.py` | +3 | import + 패널 인스턴스 |
| 수정 | `v3/ui/builders.py` | +3 | 사이드바 등록 |

---

## 3. 테스트

```
Ran 98 tests in 1.542s
OK
```

- 기존 80건 회귀 0건
- 신규 18건 (집계 8 + 패널 10) 통과
- 실 운영 DB 스모크 통과 (월별 1행, 자재 5건, 작업자 4명, 레시피 4종)

---

## 4. 결정 사항 / 교훈

### 4.1 임시 DB 격리에 `LEGACY_DB_PATH` 패치 필요

집계 메서드 단위 테스트 작성 시 `DatabaseManager(db_path=tmp_path)`만 호출하면 `_migrate_legacy_db()`가 운영 DB를 임시 경로에 복사해 테스트가 실 데이터에 의존하게 됨. **`patch("models.database.LEGACY_DB_PATH", "<nonexistent>")`** 가 깔끔한 해결책. 향후 DB-직결 단위 테스트는 이 패턴 사용.

### 4.2 `QtCharts` ImportError 폴백

PyInstaller 빌드에서 QtCharts가 누락될 가능성을 대비해 `try/except ImportError` + `_CHARTS_AVAILABLE` 플래그로 placeholder 표시. 빌드 차단 회피. **단, exe 빌드 후 실제 차트 표시 여부는 후속 검증 필요**.

### 4.3 통합 테스트 1회 작성 → 단위로 흡수

Design 단계에서 `tests/integration/test_dashboard_panel_smoke.py` 계획했으나, `test_dashboard_panel.py`가 offscreen Qt + MagicMock으로 동일 시나리오를 이미 커버. **YAGNI 적용** — Plan에 있어도 중복이면 단위 테스트로 통합. 가벼운 PDCA에서 굳어가는 패턴.

### 4.4 SSOT 준수 (UITheme)

신규 색 도입 없이 `MINT_ACCENT`(앰버 골드) + `SURFACE_ALT`/`BORDER_SUBTLE`/`TEXT_*` 토큰만 사용. KPI 카드는 `SURFACE_ALT` + `CARD_BORDER_RADIUS`로 기존 카드와 시각 일관성 유지.

---

## 5. 커밋 흐름

| 순서 | 메시지 | 파일 |
|---|---|---|
| 1 | `feat(db): add aggregate queries for dashboard (PDCA #17 Part A)` | database.py, data_manager.py, test_data_manager_aggregates.py |
| 2 | `feat(ui): add DashboardPanel (PDCA #17 Part B)` | dashboard_panel.py |
| 3 | `feat(ui): wire dashboard into sidebar (PDCA #17 Part C)` | main_window.py, builders.py |
| 4 | `test: add dashboard panel smoke tests (PDCA #17 Part D)` | test_dashboard_panel.py |
| 5 | `docs: PDCA #17 plan/design/analysis/report for material_usage_dashboard` | 4 문서 |

---

## 6. 다음 사이클 후보

| # | 후보 | 비고 |
|---|---|---|
| 18 | 자재 재고 임계값 알림 | 대시보드 데이터 기반, KPI 옆 토스트 |
| 19 | 대시보드 PDF/Excel 출력 | reportlab/openpyxl, 기존 excel_exporter 재사용 |
| 20 | 레시피 즐겨찾기/태그 | DB 컬럼 추가 + 검색 단축 |
| 21 | improvement.plan #10 DRY 재정의 | 패널판 ↔ 다이얼로그판 빌더 공통화 |
| 22 | improvement.plan #2 .venv 정리 | integration.plan과 통합 |

---

## 7. 결론

**Match Rate 100%**, 회귀 0건, 실 데이터 스모크 통과로 PDCA #17 완료. 첫 신규 기능 사이클이 정착된 PDCA 인프라(Plan/Design/Analysis/Report) 위에서 큰 마찰 없이 마무리됐고, **테스트-우선 격리 패턴 (`LEGACY_DB_PATH` 패치)** 이 새 교훈으로 남았다.
