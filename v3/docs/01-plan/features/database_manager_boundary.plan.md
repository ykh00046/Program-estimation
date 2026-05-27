# 두 DB 매니저 책임 경계 명문화 계획서 (PDCA #18)

> **Feature**: database_manager_boundary
> **Summary**: `models/database.py`(`DatabaseManager`)와 `models/dhr_database.py`(`DhrDatabaseManager`)의 공통 인프라를 베이스 클래스로 추출하고, 명명·문서로 책임 경계를 명문화한다. 물리 DB 통합은 하지 않는다.
> **Author**: AI Assistant
> **Created**: 2026-05-27
> **Status**: ✅ Plan
> **PDCA Cycle**: #18 (리팩토링 — 두 매니저의 DRY/명명/책임 경계)

---

## 1. 배경

PDCA #17까지의 코드 리뷰에서 두 DB 매니저 병존이 "가장 영향도가 큰 부채"로 지목됐다. 그러나 코드를 정독한 결과 **실제 통합은 잘못된 답**이다:

- `database.py`는 **`mixing_records.db`** (배합 작업 기록 + 레거시 레시피)
- `dhr_database.py`는 **`dhr_records.db`** (DHR 기록 + DHR 전용 레시피/분류 마스터)
- 두 파일은 **물리적으로 분리된 SQLite 파일**, **다른 스키마**, **다른 라이프사이클**
- DhrDB는 명시적으로 "Google Sheets 백업 없음" (개인정보·민감성 차이)

**진짜 문제는 세 가지**:

1. **공통 인프라 중복** — `__init__`, `_ensure_database_exists`, `get_connection` 컨텍스트 매니저가 거의 동일하게 두 파일에 존재 (DRY 위반, `improvement.plan #10`).
2. **`DatabaseManager`라는 모호한 명명** — 두 매니저가 다 "Database Manager"인데 한쪽만 일반 이름을 차지하고 있어, 신규 개발자가 어느 쪽을 써야 할지 즉시 알 수 없다.
3. **책임 경계 미문서화** — 어떤 데이터가 어느 DB에 들어가는지 코드/주석에 명시되지 않음.

---

## 2. 범위 (In Scope)

### Part A — 공통 베이스 추출 (`models/_sqlite_base.py` 신규)

신규 모듈 `models/_sqlite_base.py`에 `SqliteManagerBase` 추상 클래스 정의:

- `__init__(self, db_path: str)` — 경로 저장 + `_ensure_database_exists()` 호출
- `_ensure_database_exists(self) -> None` — 디렉토리 생성
- `get_connection(self)` — `@contextmanager`로 PRAGMA/row_factory/rollback/close 처리
- `_create_tables(self) -> None` — abstractmethod (서브클래스에서 구현 강제)

언더스코어 접두(`_sqlite_base`)로 **내부 인프라**임을 명시. 외부 모듈은 직접 import 하지 않음.

### Part B — `database.py` 적용 + 명명 명료화

- `DatabaseManager`를 `MixingDatabaseManager`로 **rename** (책임이 `mixing_records`임을 명시).
- 단, 외부 호출이 `from models.database import DatabaseManager`인 경우가 1건(`data_manager.py`) + 테스트 2건 — 모두 동시 수정.
- 모듈 docstring에 "이 매니저는 `mixing_records.db`만 다룬다. DHR 데이터는 `models.dhr_database.DhrDatabaseManager`를 사용하라"는 책임 경계 명시.
- `SqliteManagerBase` 상속 → 중복 메서드 제거.
- `_migrate_legacy_db()`는 `DatabaseManager`(=mixing) **고유 책임**으로 잔존 (DhrDB는 레거시 마이그레이션 없음).

### Part C — `dhr_database.py` 적용

- `DhrDatabaseManager`는 명명 그대로 유지 (이미 명확).
- 모듈 docstring에 "이 매니저는 `dhr_records.db`만 다룬다. 일반 배합 기록은 `models.database.MixingDatabaseManager`를 사용하라" 명시.
- `SqliteManagerBase` 상속 → 중복 메서드 제거.

### Part D — 테스트 & 회귀 검증

- `tests/unit/test_sqlite_base.py` 신규: `get_connection` 트랜잭션/rollback/PRAGMA 검증, `_ensure_database_exists` 디렉토리 자동 생성 검증.
- `run_tests.py` 전체 실행 → 회귀 0건 확인 (현재 98 테스트 기준).

---

## 3. 범위 외 (Out of Scope)

- **물리 DB 통합** — 다른 도메인이므로 통합 안 함.
- **스키마 마이그레이션** — 변경 없음.
- **API 변경** — public 메서드 시그니처 보존 (`DatabaseManager` → `MixingDatabaseManager`는 별칭으로 후방 호환 유지 가능하지만, 사용처가 모두 v3 내부이고 적으므로 **alias 없이 모두 동시 수정** 채택).
- **DhrDatabaseManager 리네임** (`MixingDatabaseManager`와 대구가 되려면 이미 충분히 명확).

---

## 4. 단계별 작업

| Step | 산출물 | LOC 변동 |
|---|---|---|
| A | `models/_sqlite_base.py` 신규 (~50 LOC) | +50 |
| B | `database.py`: 클래스 rename + 베이스 상속 + 모듈 docstring | -30 ~ -40 |
| B' | `data_manager.py`, 테스트 2건의 import 수정 | ±0 |
| C | `dhr_database.py`: 베이스 상속 + 모듈 docstring | -25 ~ -35 |
| D | `tests/unit/test_sqlite_base.py` 신규 | +50 |

전체적으로 LOC 감소(중복 제거) + 신규 테스트로 약 +20~30 LOC 순증가, 그러나 **두 매니저 본문은 도메인 메서드만 남아 가독성 향상**.

---

## 5. 위험 & 완화

| 위험 | 영향 | 완화 |
|---|---|---|
| `DatabaseManager` rename 누락 호출자 | ImportError | grep로 사전 점검 완료(3건 확정). PyInstaller hidden_imports 변경 불필요(클래스명이지 모듈명 아님). |
| 베이스 클래스의 `get_connection` 통합으로 DHR/Mixing 둘 중 한쪽의 PRAGMA 누락 | 트랜잭션 무결성 | 두 코드 모두 PRAGMA가 동일(`foreign_keys = ON`)이므로 안전. 테스트로 검증. |
| `@handle_exceptions` 데코레이터가 베이스의 메서드와 충돌 | 런타임 무한 래핑 | 베이스는 raw 메서드만 제공, 데코레이터는 서브클래스에서만 적용. |

---

## 6. 성공 기준

1. `models/_sqlite_base.py`에 `SqliteManagerBase` 정의되고 두 매니저가 상속.
2. `DatabaseManager` → `MixingDatabaseManager`로 rename, 호출 3건 모두 수정.
3. 두 모듈에 책임 경계가 docstring으로 명문화.
4. `run_tests.py` 전 테스트 통과 (현재 98+신규 N건).
5. 두 파일의 LOC 합산 감소.

---

## 7. 다음 사이클 후보 (PDCA #19)

본 사이클 종료 후 — 분석에서 도출된 후보 중 **자재 재고 임계값 알림**(사용자 가치) 또는 **`record_view_dialog.py`(579 LOC) 분해**(부채) 중 사용자 선택.

---

**작성일**: 2026-05-27
**버전**: 1.0
**Status**: Plan ✅
