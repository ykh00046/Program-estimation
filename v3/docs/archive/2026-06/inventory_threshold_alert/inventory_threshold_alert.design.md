# 자재 재고 임계값 알림 — 설계 (PDCA #27)

> feature: `inventory_threshold_alert` · Level: Starter · 작성일: 2026-06-01
> 선행 Plan: `docs/01-plan/features/inventory_threshold_alert.plan.md`
> 설계 결정: Plan §2 "경량 수동 재고 모델"을 따르되, **기존에 구현된 `material_stock`
> 테이블/메서드를 SSOT로 재사용**한다(신규 `material_inventory` 테이블을 만들지 않음 —
> 중복 테이블은 안티패턴, PDCA #18 교훈).

## 1. 아키텍처 개요

```
┌────────────────────────────┐
│ MaterialInventoryDialog     │  현재고/임계값 수동 입력·저장
│ (ui/dialogs)                │
└──────────────┬──────────────┘
               │ upsert (저장 시)               settings_updated
               ▼                                  │
┌────────────────────────────┐                   ▼
│ DataManager (위임)          │        ┌────────────────────────┐
│  get_all_material_stock /   │◀──────▶│ DashboardPanel          │
│  upsert_material_stock /    │        │  refresh() →            │
│  seed_.../get_inventory_    │        │  _refresh_inventory_    │
│  alerts()                   │        │  alerts() → 배너 렌더    │
└──────────────┬──────────────┘        └───────────┬────────────┘
               │                                    │ evaluate
               ▼                                    ▼
┌────────────────────────────┐        ┌────────────────────────┐
│ MixingDatabaseManager       │        │ inventory_alert.py      │
│  material_stock 테이블 CRUD  │        │  evaluate_inventory_    │
│  (기존 자산, 재사용)         │        │  alerts() (순수 함수)    │
└─────────────────────────────┘        └────────────────────────┘
```

- **표현(패널/다이얼로그)** / **위임(DataManager)** / **영속(DB)** / **순수 로직(inventory_alert)** 4계층 분리.
- 기존 대시보드(#17) 계층 규약과 동일: 패널은 표현만, 집계/평가는 위임·순수 함수.

## 2. Part A — 데이터 모델 (기존 자산 재사용)

### 2.1 테이블 `material_stock` (`models/database.py::_create_tables`, **이미 존재**)
```sql
CREATE TABLE IF NOT EXISTS material_stock (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    material_code       TEXT NOT NULL,
    material_name       TEXT NOT NULL,
    current_stock       REAL NOT NULL DEFAULT 0,
    min_stock_threshold REAL NOT NULL DEFAULT 0,
    unit                TEXT NOT NULL DEFAULT 'g',
    updated_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(material_code)
);  -- + idx_material_stock_code
```
- 신규 테이블 생성 없음. 기존 스키마가 Plan의 모든 컬럼 요구를 충족.

### 2.2 DB 메서드 (`MixingDatabaseManager`, **이미 존재** — 위임만 신규)
| 메서드 | 시그니처 | 동작 |
|---|---|---|
| `get_all_material_stock` | `() -> List[Dict]` | 전체 행, `material_name ASC` |
| `get_low_stock_materials` | `(default_threshold=0.0) -> List[Dict]` | SQL 평가(**UI 1차 경로**). 자재별 임계값 0이면 default 적용 |
| `upsert_material_stock` | `(code, name, current_stock, min_stock_threshold, unit='g') -> bool` | `ON CONFLICT(material_code) DO UPDATE` |
| `seed_material_stock_from_history` | `() -> int` | 배합 이력 자재를 0/0으로 시드, 신규 건수 |

### 2.3 DataManager 위임 래퍼 (신규)
`get_all_material_stock()`, `upsert_material_stock(...)`, `seed_material_stock_from_history()`,
`get_low_stock_materials(default_threshold=None)`,
`get_default_min_threshold()`, `set_default_min_threshold(value)`,
`get_inventory_alerts() -> List[MaterialAlert]`
(= `get_all_material_stock` → `evaluate_inventory_alerts(default_threshold=전역기본)`).

**전역 기본 임계값**: 자재별 `min_stock_threshold`=0이면 설정값
`inventory_alert.default_min_threshold`(`config.set_value`/`get`) 적용. SQL 경로
(`get_low_stock_materials`)와 순수 함수 경로(`evaluate_inventory_alerts`)는 **동일 판정
규칙(parity)** — 테스트 `test_pure_and_sql_paths_agree`로 보장.

## 3. Part B — 순수 평가 로직 (`models/inventory_alert.py` 신설)

```python
LEVEL_OUT = "OUT_OF_STOCK"   # 현재고 <= 0
LEVEL_LOW = "LOW_STOCK"      # 0 < 현재고 <= 임계값

class MaterialAlert(NamedTuple):
    material_code: str
    material_name: str
    current_stock: float
    threshold: float
    shortfall: float   # max(0, threshold - current_stock)
    level: str         # LEVEL_OUT | LEVEL_LOW

def evaluate_inventory_alerts(
    inventory_rows: List[Dict], default_threshold: float = 0.0
) -> List[MaterialAlert]: ...
```

### 3.1 판정 규칙
유효 임계값 = 자재별 `min_stock_threshold`>0 이면 그 값, 아니면 `default_threshold`.

| 조건(유효 임계값 기준) | level | 포함? |
|---|---|---|
| 유효 임계값 <= 0 (미설정·기본도 0) | — | 제외 |
| `current_stock <= 0` | `OUT_OF_STOCK` | 포함 |
| `0 < current_stock <= threshold` | `LOW_STOCK` | 포함 |
| `current_stock > threshold` | (OK) | 제외 |

- 정렬: `shortfall` 내림차순(가장 부족한 자재 먼저).
- 입력 결측/형변환 실패 → `0.0` 안전 처리(`.get()` + try/except `_coerce_float`).
- Qt·DB·전역 상태 무의존 → 단독 단위 테스트 가능.

## 4. Part C — UI 연동 (실제 구현 정합)

### 4.1 DashboardPanel 변경 (`ui/panels/dashboard_panel.py`)
- **period bar**: 버튼 행에 `재고 설정` 버튼(`self.stock_settings_btn`,
  `UIStyles.get_secondary_button_style()`). 클릭 → `_open_stock_settings()`.
- **재고 부족 알림 섹션**: `_build_low_stock_section()`(QFrame 카드)을 period bar 아래·KPI 위에 삽입.
  - `self.low_stock_empty_label`("✅ 모든 자재 재고가 정상입니다."), `self.low_stock_container`
    (가로 카드 레이아웃), `self.low_stock_more_label`("+N건 더 …"). 초기 컨테이너 `hidden`.
  - `_refresh_low_stock_alerts()`: `data_manager.get_low_stock_materials()` →
    `_clear_alert_cards()` → 0건이면 empty 라벨 표시·컨테이너 숨김, 1건↑이면 카드 생성.
    최대 `_MAX_ALERT_CARDS`(=6) 표시, 초과분은 more 라벨로 요약.
  - `refresh()` **맨 앞**에 호출(나머지 섹션 try/except로 보호 → 회귀 영향 최소화).
- **알림 카드**(`_make_alert_card(item: Dict)`, `QFrame#StockAlertCard`):
  - 레벨 색 — 현재고 ≤ 0 → `UITheme.ERROR_COLOR`(소진), 그 외 → `UITheme.WARNING_COLOR`(임박).
  - dict 키: `current_stock` / `threshold` / `shortage` / `unit` / `material_name`.
  - 카드 스타일은 `SURFACE_ALT` + `BORDER_SUBTLE` + `CARD_BORDER_RADIUS` 토큰 재사용(요구사항 5).
- 순수 평가 경로(`get_inventory_alerts` → `evaluate_inventory_alerts`)는 SQL 경로와
  **동일 판정(parity)** 을 보장하는 프로그램 API로 병존(패널은 SQL 필터 경로 사용).

### 4.2 StockSettingsDialog (`ui/dialogs/stock_settings_dialog.py` 신설)
- `QDialog`, 모달. `_init_ui` → 기본 임계값 입력 행 + 자재 테이블 + 버튼 행.
- `_load_data()`: `seed_material_stock_from_history()` → `get_default_min_threshold()`
  → `get_all_material_stock()` → 테이블 채움.
- `QTableWidget`: 자재명/코드 + `현재 재고` + `최소 임계값` 편집.
- 버튼: `재시드`(`_on_reseed` → seed + 재로드), `저장`(`_on_save`), `닫기`.
  - `_on_save`: `set_default_min_threshold(...)` + 각 행 `upsert_material_stock(code,name,current,threshold,unit)`
    (`_parse_num` 음수/비숫자→0). 완료 후 패널 `refresh()`.
- 스타일: 기존 `UIStyles`/`UITheme` 토큰 사용(요구사항 5).

## 5. Part D — 테스트 설계 (실제 파일)

| 파일 | 종류 | 케이스 |
|---|---|---|
| `tests/unit/test_inventory_alert.py` | 순수 | OUT/LOW/OK 경계, 미설정(≤0) 제외, 빈/None 입력 `[]`, shortfall 계산, 정렬 desc, 결측/문자열 안전 |
| `tests/unit/test_material_stock_db.py` | DB | upsert→get round-trip, 갱신, seed, 빈 DB `[]` (임시 DB + `LEGACY_DB_PATH` patch) |
| `tests/unit/test_material_stock.py` | 위임/통합 | data_manager 위임, `get_low_stock_materials` 임계값 평가, 기본 임계값 |
| `tests/integration/test_stock_alert_dashboard.py` | 스모크 | 패널 알림 섹션 표시/숨김, 다이얼로그 생성·저장 위임(offscreen, QMessageBox patch) |

## 6. 영향도 / 회귀 가드
- 신규 파일 2개(`models/inventory_alert.py`, `ui/dialogs/stock_settings_dialog.py`)
  + 기존 수정(`models/database.py` 테이블·CRUD, `models/data_manager.py` 위임,
  `ui/panels/dashboard_panel.py` 알림 섹션) + 테스트.
- 기존 대시보드 mock DM 패턴에 `get_low_stock_materials.return_value=[]` 추가(회귀 방지).
- DashboardExporter·export 무영향(패널 레이아웃만 변경).
- Python 3.9 호환(`typing`), UTF-8, 함수 20줄·타입힌트·`logger` 규약 준수.
- **전체 스위트 198 passed, 회귀 0 (2026-06-01 검증).**

## 7. 다음 단계
→ 구현(Do) → `tests/run_tests.py` → `/pdca analyze` → `/pdca report`
