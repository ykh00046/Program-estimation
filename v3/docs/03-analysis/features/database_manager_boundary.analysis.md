# 두 DB 매니저 책임 경계 명문화 Gap 분석 (PDCA #18)

> **Feature**: database_manager_boundary
> **Phase**: Check
> **Author**: AI Assistant
> **Created**: 2026-05-27
> **PDCA Cycle**: #18

---

## 1. Plan/Design ↔ 구현 일치 매트릭스

| 계획 항목 | Design 명세 | 실제 구현 | 일치도 |
|---|---|---|---|
| `models/_sqlite_base.py` 신규 | `SqliteManagerBase` (`__init__(db_path, log_prefix)`, `_ensure_database_exists`, `get_connection`) | ✅ 동일 | 100% |
| `DatabaseManager` → `MixingDatabaseManager` rename | 클래스명만 변경, public API 보존 | ✅ 5건 호출자 모두 동시 수정 | 100% |
| 베이스 상속 후 중복 제거 | `database.py`/`dhr_database.py` 각각 `_ensure_database_exists`/`get_connection`/PRAGMA 블록 제거 | ✅ 두 파일 합산 -92 라인 | 100% |
| 모듈 docstring 책임 경계 명문화 | "이 매니저는 X.db만 다룬다, Y는 Z를 사용하라" | ✅ 두 매니저 모두 명시 | 100% |
| `_migrate_legacy_db`는 Mixing 전용 잔존 | DhrDB는 신규 시스템이므로 미적용 | ✅ Mixing에만 유지 | 100% |
| 베이스 단위 테스트 5건 | `_ensure_database_exists`, row_factory, PRAGMA, sqlite_error 래핑, close 검증 | ✅ 5건 작성, 5건 통과 | 100% |
| 회귀 0건 | `run_tests.py` 전후 비교 | ✅ 53 tests / 14 errors / 5 skipped 사전·사후 동일 | 100% |
| 별칭(alias) 미제공 | "한 번에 끊는다" 결정 | ✅ `DatabaseManager` 잔여 참조 0건 | 100% |

### Design에 없던 추가 발견

| 항목 | 처리 |
|---|---|
| `tests/unit/test_data_manager.py`의 `patch('models.data_manager.DatabaseManager')` 숨은 mock 경로 | grep `import|.`만으로는 미검출. patch 문자열도 grep 후 수정. |
| `database_manager_boundary_clarification.{plan,design}.md` 중복 변형 | 짧은 이름으로 통일, 변형 삭제 |

---

## 2. 코드 메트릭

### LOC 변화 (`git diff --stat`)

| 파일 | 변화 |
|---|---|
| `models/database.py` | +14 / -43 (-29) |
| `models/dhr_database.py` | +14 / -39 (-25) |
| `models/data_manager.py` | +2 / -2 |
| `tests/integration/test_data_integration.py` | +8 / -11 |
| `tests/unit/test_data_manager.py` | +2 / -2 |
| `tests/unit/test_data_manager_aggregates.py` | +4 / -4 |
| **신규 `models/_sqlite_base.py`** | +59 |
| **신규 `tests/unit/test_sqlite_base.py`** | +70 |
| **합계** | **+173 / -101 (+72)** |

두 매니저 본문은 합산 **-54 라인 순감**. 베이스 추출(+59) + 테스트(+70)로 인한 총합은 +72라인이지만, **중복 제거 + 책임 경계 문서화 + 회귀 안전망 신설**이라는 가치 대비 합리적인 증가.

### 책임 경계 명문화 (docstring 1줄 검사)

- `database.py` 모듈 docstring: `"DHR 데이터는 models.dhr_database.DhrDatabaseManager를 사용하라"` ✅
- `dhr_database.py` 모듈 docstring: `"일반 배합 기록은 models.database.MixingDatabaseManager를 사용하라"` ✅
- 두 파일이 서로를 가리키는 양방향 참조 형태로 명문화됨.

---

## 3. 테스트 결과

| 테스트 | 결과 |
|---|---|
| `tests.unit.test_sqlite_base` (신규 5건) | ✅ 5/5 통과 |
| Mixing/Dhr 매니저 스모크 (인스턴스화 + `get_mixing_records`/`get_dhr_records`) | ✅ 정상 |
| `run_tests.py` 전체 (53 tests) | ✅ 사전과 동일 (errors=14, skipped=5) |
| `DatabaseManager` 잔여 참조 grep | ✅ 0건 |

### 회귀 0건 검증 방법

`git stash` → `run_tests.py` → 53/14/5 확인 → `git stash pop` → `run_tests.py` → 53/14/5 확인.
PDCA #18 변경이 기존 테스트 결과를 1건도 바꾸지 않았음을 직접 측정.

### 사전 결함 (PDCA #18 범위 밖)

`test_excel_exporter`의 14건 `AttributeError: module 'models' has no attribute 'excel_exporter'` 에러는
**PDCA #17 이전부터 존재**하는 사전 결함. 본 사이클의 책임이 아니며, 차기 PDCA(예: `test_collection_hygiene`) 후보.

---

## 4. 위험 사후 평가

| Design에서 식별한 위험 | 실제 발생 | 평가 |
|---|---|---|
| `DatabaseManager` rename 누락 호출자 | 1건 발견(`patch('models.data_manager.DatabaseManager')`), 동일 사이클에서 수정 | 완화됨 |
| 베이스의 `get_connection` 통합으로 PRAGMA 누락 | 발생 안 함 (두 매니저의 PRAGMA가 본래 동일) | 위험 해소 |
| `@handle_exceptions` 데코레이터와 베이스 메서드 충돌 | 발생 안 함 (베이스는 raw 메서드만 제공) | 위험 해소 |

---

## 5. Match Rate

**일치도: 100%** (8/8 계획 항목 + 2개 추가 발견 모두 처리).

PDCA Core Rules에 따라 ≥90% → 자동 완료 보고서 작성 단계로 진입.

---

**작성일**: 2026-05-27
**Status**: Analysis ✅ / Match Rate 100%
