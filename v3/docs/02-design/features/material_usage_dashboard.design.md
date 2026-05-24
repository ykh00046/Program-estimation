# 배합 이력 대시보드 설계서 (PDCA #17)

> **Feature**: material_usage_dashboard
> **Plan**: [../../01-plan/features/material_usage_dashboard.plan.md](../../01-plan/features/material_usage_dashboard.plan.md)
> **Author**: AI Assistant
> **Created**: 2026-05-25
> **Status**: 🔄 Design
> **PDCA Cycle**: #17

---

## 1. 설계 원칙

- **SRP**: 데이터 집계는 `DataManager` / `DatabaseManager`, 표현은 `DashboardPanel`. 둘 사이에 비즈니스 로직 없음.
- **순수 함수 분리**: `_format_amount(g)`, `_format_kpi_value(v)` 등 표현 변환은 panel 내부 `@staticmethod`로 분리 → Qt/DB 의존 없이 단위 테스트 가능.
- **SSOT 준수**: 색·간격·radius는 `UITheme`. 차트 시리즈 색도 `UITheme.MINT_ACCENT` 단일 색 + 알파 변주.
- **Python 3.9**: `typing.Optional/List/Dict/Tuple` 사용, `|` 유니온 금지.
- **20줄/3중첩 룰**: 각 `_build_*` 빌더는 위젯 조립만, 데이터 바인딩은 별도 `_refresh_*` 메서드로.

---

## 2. DB 계층 변경 (Part A)

### 2.1 `DatabaseManager` 신규 메서드 (database.py)

```python
def get_monthly_production_stats(self, months: int = 6) -> List[Dict]:
    """최근 N개월 월별 생산 통계.

    Returns: [{"year_month": "2026-05", "record_count": int, "total_amount": float}, ...]
    오래된 순 정렬 (차트 X축 자연순).
    """

def get_top_materials(
    self,
    limit: int = 10,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> List[Dict]:
    """기간 내 자재 사용량 TOP-N (actual_amount 합 기준).

    Returns: [{"material_code", "material_name", "total_actual": float, "use_count": int}, ...]
    """

def get_worker_stats(
    self,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> List[Dict]:
    """기간 내 작업자별 통계.

    Returns: [{"worker", "record_count", "total_amount", "avg_amount"}, ...]
    건수 desc 정렬.
    """

def get_recipe_frequency(
    self,
    limit: int = 10,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> List[Dict]:
    """기간 내 레시피 실행 빈도 TOP-N.

    Returns: [{"recipe_name", "run_count", "total_amount"}, ...]
    """
```

### 2.2 SQL 패턴

모두 `@handle_exceptions(default_return=[])` 데코레이터 적용. 기간 파라미터는 `get_mixing_records` 패턴 그대로 (`WHERE 1=1` + 동적 AND).

```sql
-- 월별 (sqlite strftime)
SELECT strftime('%Y-%m', work_date) AS year_month,
       COUNT(*) AS record_count,
       COALESCE(SUM(total_amount), 0) AS total_amount
FROM mixing_records
WHERE work_date >= date('now', ?)  -- ? = '-6 months'
GROUP BY year_month
ORDER BY year_month ASC;

-- 자재 TOP-N (mixing_details JOIN mixing_records 기간 필터)
SELECT d.material_code,
       d.material_name,
       SUM(d.actual_amount) AS total_actual,
       COUNT(DISTINCT d.mixing_record_id) AS use_count
FROM mixing_details d
JOIN mixing_records r ON d.mixing_record_id = r.id
WHERE 1=1
  [AND r.work_date >= ?]
  [AND r.work_date <= ?]
GROUP BY d.material_code, d.material_name
ORDER BY total_actual DESC
LIMIT ?;

-- 작업자
SELECT worker,
       COUNT(*) AS record_count,
       SUM(total_amount) AS total_amount,
       AVG(total_amount) AS avg_amount
FROM mixing_records
WHERE 1=1 [AND work_date >= ?] [AND work_date <= ?]
GROUP BY worker
ORDER BY record_count DESC;

-- 레시피 빈도
SELECT recipe_name,
       COUNT(*) AS run_count,
       SUM(total_amount) AS total_amount
FROM mixing_records
WHERE 1=1 [AND work_date >= ?] [AND work_date <= ?]
GROUP BY recipe_name
ORDER BY run_count DESC
LIMIT ?;
```

### 2.3 `DataManager` 위임 (data_manager.py)

기존 `get_mixing_records` 위임 패턴과 동일하게 1:1 통과. 로직 가공 없음.

---

## 3. UI 계층 (Part B)

### 3.1 클래스 구조

```
DashboardPanel(QWidget)
├── __init__(data_manager)
├── _init_ui()                       # 오케스트레이터 (20줄 이내)
├── _build_period_bar()  -> QWidget   # 기간 콤보 + 새로고침
├── _build_kpi_row()     -> QWidget   # KPI 카드 4개
├── _build_monthly_chart() -> QWidget # 월별 막대 차트 카드
├── _build_top_materials_card() -> QWidget
├── _build_worker_stats_card()  -> QWidget
├── refresh()                          # 모든 섹션 데이터 재로드 (public)
├── _refresh_kpis()
├── _refresh_chart()
├── _refresh_top_materials()
├── _refresh_worker_stats()
├── _current_date_range() -> Tuple[Optional[str], Optional[str]]
└── @staticmethod _format_amount(g: float) -> str  # "1,234 g" / "1.23 kg"
```

### 3.2 위젯 ID 규칙

- 최상위 `QWidget`: `objectName="DashboardPage"` (styles.py에 이미 정의됨, 배경 그라데이션 자동 적용)
- KPI 카드: `objectName="KpiCard"` — 추가 스타일 필요 시 `setStyleSheet(UIStyles.get_card_style())`

### 3.3 KPI 카드 4종

| 카드 | 값 | 출처 |
|---|---|---|
| 당월 생산 건수 | `get_monthly_production_stats(1)[0]["record_count"]` | 월별 |
| 당월 총 배합량 | 동일 row의 total_amount, `_format_amount`로 g→kg 변환 | 월별 |
| 활성 작업자 수 | `len(get_worker_stats(start=당월1일))` | 작업자 |
| 누적 레시피 종류 | `len(get_recipe_frequency(limit=10000))` (전체기간) | 레시피 |

빈 결과 시 모두 "0" 표시.

### 3.4 월별 차트

- `PySide6.QtCharts.QChartView` + `QBarSeries` + `QBarSet`
- X축: `QBarCategoryAxis` (year_month 문자열)
- Y축: `QValueAxis` (자동 범위, 단위 "g")
- 색: `UITheme.MINT_ACCENT` (단일색)
- 데이터 0건 → 차트 대신 BodyLabel "아직 기록이 없습니다" 표시 (`QStackedWidget` 또는 `setVisible` 토글)

### 3.5 테이블 2종

`QTableWidget`:
- 자재 TOP 10: 컬럼 [순위, 자재코드, 자재명, 총 사용량, 횟수]
- 작업자 통계: 컬럼 [작업자, 건수, 총량, 평균]
- 스타일: `UIStyles.get_table_style()`
- 가로 스트레치: 자재명 / 작업자 컬럼
- 정렬 비활성화 (집계 결과 정렬은 SQL이 책임)

### 3.6 기간 선택

`QComboBox`:
- 옵션: ["최근 30일", "최근 90일", "최근 6개월", "전체"]
- 기본값: "최근 6개월"
- `currentIndexChanged` → `self.refresh()`
- `_current_date_range()`가 옵션을 (start_date, end_date) 튜플로 변환. "전체"는 (None, None).

---

## 4. 통합 (Part C)

### 4.1 `ui/main_window.py::_create_panels`

기존 `recipe_panel`, `work_info_panel` 등 패널 생성 블록에 1줄 추가:

```python
self.dashboard_panel = DashboardPanel(self.services.data_manager)
```

### 4.2 `ui/builders.py::register_sidebar_interfaces`

순서: 배합 → 수기 입력 → 일괄 생성 → DHR 관리 → **대시보드 (NEW)** → 기록 조회 → 설정 → 작업자 변경

```python
# 4-2. 대시보드 (NEW)
window.addSubInterface(window.dashboard_panel, FIF.PIE_SINGLE, "대시보드")
```

진입 시점에 한 번 `refresh()` 호출 — `showEvent`에서 lazy load (기본 화면 진입 속도 영향 최소화).

---

## 5. 테스트 설계 (Part D)

### 5.1 `tests/unit/test_data_manager_aggregates.py`

`fixture_db()` 헬퍼로 임시 sqlite 파일 생성 → 3건 샘플 데이터 삽입.

| 테스트 | 검증 |
|---|---|
| `test_monthly_stats_empty_db` | 빈 DB → 빈 리스트 |
| `test_monthly_stats_basic` | 1개월 데이터 → 1행, record_count/total_amount 일치 |
| `test_top_materials_orders_desc` | 자재 3종 삽입 → 사용량 desc 정렬 |
| `test_top_materials_respects_limit` | limit=2 → 2행 |
| `test_worker_stats_avg_calculation` | 동일 작업자 2건 → avg = (a+b)/2 |
| `test_recipe_frequency_count` | 동일 레시피 3회 → run_count=3 |
| `test_date_filter_excludes_out_of_range` | 범위 밖 데이터 제외 |

### 5.2 `tests/unit/test_dashboard_panel.py`

`_format_amount` 순수 함수 테스트 (Qt 의존 없음):
- 0 → "0 g"
- 999 → "999 g"
- 1000 → "1.00 kg"
- 1234567 → "1234.57 kg"

### 5.3 `tests/integration/test_dashboard_panel_smoke.py`

`_ensure_ui_test_dependencies()` 패턴으로 PySide6/qfluentwidgets 없으면 SkipTest. offscreen QApplication에서:
- DashboardPanel 인스턴스화 성공
- 빈 DB에서 refresh() 호출해도 예외 없음
- KPI 카드 4개 위젯 존재

---

## 6. 위험 재확인

| 위험 | 결정 |
|---|---|
| `QtCharts` import 실패 | `try/except ImportError` 후 placeholder 표시 — 빌드 차단 회피 |
| `strftime('%Y-%m', work_date)` 형식 의존 | work_date는 'YYYY-MM-DD' 보장 (CLAUDE.md 데이터 모델). 비표준 행이 있으면 GROUP BY 결과가 NULL — 무시 |
| Wall clock test 비결정성 | "당월" KPI 테스트는 SQL `date('now')`가 아니라 panel 헬퍼가 `datetime.now()` 사용 → 테스트는 panel 헬퍼를 우회하고 DB 직접 검증 |

---

## 7. 단계별 커밋 계획

1. `feat(db): add aggregate queries for dashboard (PDCA #17 Part A)` — database.py + data_manager.py + 단위 테스트
2. `feat(ui): add DashboardPanel (PDCA #17 Part B)` — dashboard_panel.py 신규
3. `feat(ui): wire dashboard into sidebar (PDCA #17 Part C)` — main_window.py + builders.py
4. `test: add dashboard smoke + unit tests (PDCA #17 Part D)`
5. `docs: PDCA #17 analysis + report` — 마지막
