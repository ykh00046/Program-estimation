# 자재 재고 임계값 알림 — Gap 분석 (PDCA #27)

> feature: `inventory_threshold_alert` · Level: Starter · 분석일: 2026-06-01
> Plan: `docs/01-plan/features/inventory_threshold_alert.plan.md`
> Design: `docs/02-design/features/inventory_threshold_alert.design.md`
> 구현: `models/inventory_alert.py`, `models/database.py`, `models/data_manager.py`,
>       `ui/panels/dashboard_panel.py`, `ui/dialogs/stock_settings_dialog.py`

## 1. 분석 개요

| 항목 | 내용 |
|---|---|
| 분석 대상 | inventory_threshold_alert (자재 재고 임계값 알림) |
| 기준 문서 | Design (실제 구현 정합 기준으로 작성됨) |
| 핵심 설계 결정 | 신규 `material_inventory` 미생성, 기존 `material_stock` 테이블을 SSOT로 재사용 (중복 테이블 안티패턴 회피, PDCA #18 교훈) |
| 검증 상태 | 전체 스위트 198 passed, 회귀 0 (2026-06-01) |

## 2. 종합 점수

| 분류 | 점수 | 상태 |
|---|:---:|:---:|
| Design 정합 (Part A~D) | 100% | ✅ |
| 아키텍처(4계층 분리) 준수 | 100% | ✅ |
| 컨벤션(타입힌트/snake_case/UITheme SSOT/Py3.9) 준수 | 100% | ✅ |
| **종합** | **100%** | ✅ |

> 성공 기준 §5-5(gap-detector Match ≥ 90%) 충족.

## 3. Part별 Design ↔ 구현 대조

### Part A — 데이터 모델 (material_stock 재사용)
| Design 항목 | 구현 위치 | 정합 |
|---|---|:---:|
| `material_stock` 테이블 (7컬럼 + UNIQUE(material_code)) | `database.py:102-113` | ✅ |
| `idx_material_stock_code` 인덱스 | `database.py:116` | ✅ |
| `get_all_material_stock()` (name ASC) | `database.py:696-707` | ✅ |
| `get_low_stock_materials(default_threshold=0.0)` (SQL 평가, shortage 정렬) | `database.py:709-735` | ✅ |
| `upsert_material_stock(...)` ON CONFLICT DO UPDATE | `database.py:737-764` | ✅ |
| `seed_material_stock_from_history() -> int` | `database.py:766-790` | ✅ |
| DataManager 위임 (get_all/upsert/seed/get_inventory_alerts) | `data_manager.py:466-490` | ✅ |
| get_default_min_threshold / set_default_min_threshold | `data_manager.py:492-505` | ✅ |
| get_low_stock_materials 위임 (전역 기본 임계값 적용) | `data_manager.py:507-514` | ✅ |

### Part B — 순수 평가 로직 (`models/inventory_alert.py`)
| Design 항목 | 구현 | 정합 |
|---|---|:---:|
| `LEVEL_OUT`/`LEVEL_LOW`, `MaterialAlert`(6필드) | 존재 | ✅ |
| 판정규칙(미설정 제외 / current≤0 OUT / 0<current≤thr LOW / current>thr 제외) | 존재 | ✅ |
| 전역 기본 임계값 fallback (`default_threshold`) — SQL 경로와 parity | 존재 | ✅ |
| shortfall = max(0, threshold-current), 내림차순 정렬 | 존재 | ✅ |
| 결측/문자열 안전(`_coerce_float`), Qt·DB 무의존 | 존재 | ✅ |

### Part C — UI 연동
| Design 항목 | 구현 위치 | 정합 |
|---|---|:---:|
| `재고 설정` 버튼 → `_open_stock_settings` | `dashboard_panel.py:114-117` | ✅ |
| `_build_low_stock_section()` (period bar 아래·KPI 위) | `dashboard_panel.py:63-64,127-161` | ✅ |
| empty 라벨 / container(hidden) / more 라벨 | `dashboard_panel.py:140-159` | ✅ |
| `_refresh_low_stock_alerts()` (`get_low_stock_materials`, `_MAX_ALERT_CARDS=6`) | `dashboard_panel.py:125,170-191` | ✅ |
| `refresh()` 맨 앞 호출 + try/except 보호 | `dashboard_panel.py:430-439` | ✅ |
| `_make_alert_card` (current≤0→ERROR_COLOR, else WARNING_COLOR) | `dashboard_panel.py:201-209` | ✅ |
| `_clear_alert_cards()` (stretch 유지) | `dashboard_panel.py:193-199` | ✅ |
| `StockSettingsDialog` (_load_data: seed→default→get_all) | `stock_settings_dialog.py` | ✅ |
| `_on_save` (set_default + 행별 upsert, `_parse_num` 음수·비숫자→0) | `stock_settings_dialog.py:166-188` | ✅ |
| UIStyles/UITheme 토큰 사용 | 확인 | ✅ |

### Part D — 테스트
| 파일 | 케이스 | 정합 |
|---|---|:---:|
| `test_inventory_alert.py` | 순수 평가 경계/정렬/안전 (10) | ✅ |
| `test_material_stock_db.py` | DB CRUD/seed/필터 (8) | ✅ |
| `test_material_stock.py` | 위임·임계값·기본값 (9) | ✅ |
| `test_stock_alert_dashboard.py` | 패널·다이얼로그 스모크 (5) | ✅ |

## 4. 발견된 차이 (Gap)

- 🔴 누락 기능(Design O, 구현 X): **없음**
- 🟡 추가 기능(Design X, 구현 O): **없음** (전역 기본 임계값 get/set·SQL 위임은 Design §2.3·§4.2에 반영됨)
- 🔵 변경(Minor 1건): 다이얼로그 저장 스모크가 `_FakeDataManager`→실제 DB upsert→패널 재평가 통합 경로로 검증(다이얼로그 직접 exec 미수행). 기능 등가 — 저위험.

### Plan ↔ 구현 명칭 차이 (gap 아님 — 문서화된 설계 결정)
| Plan 표현 | 구현 | 판정 |
|---|---|---|
| `material_inventory` 신규 테이블 / `get/set/delete_material_inventory` | `material_stock` 재사용 / `get_all/upsert/seed` | Design §5~7에서 SSOT 재사용으로 명시 재정렬 — 의도적, gap 아님 |
| `delete_material_inventory(code)` | 삭제 미구현(편집·재시드만) | Design 기준 정합(삭제는 0/0 upsert + threshold≤0 자동 제외로 등가) |

## 5. 권장 조치
- **즉시 조치 없음.** Design 대비 정합 100%, 회귀 0.
- (선택) Plan §3의 `material_inventory`/`delete_*` 잔재 표현은 Design에서 무효화됨 — 이력 보존상 수정 불요.

## 6. 결론
- **Match Rate: 100%** (성공 기준 ≥90% 충족).
- Part A~D 전 항목 구현 존재. 4계층 분리(표현/위임/영속/순수) + 컨벤션 준수.
- Critical/Major gap 0건, Minor 1건(테스트 방식 표현, 기능 등가).
- 다음 단계: `/pdca report inventory_threshold_alert`.
