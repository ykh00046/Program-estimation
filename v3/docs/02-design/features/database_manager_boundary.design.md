# 두 DB 매니저 책임 경계 명문화 설계서 (PDCA #18)

> **Feature**: database_manager_boundary
> **Author**: AI Assistant
> **Created**: 2026-05-27
> **Status**: ✅ Design
> **PDCA Cycle**: #18

---

## 1. 현황 다이어그램

```
┌──────────────────────────────┐  ┌──────────────────────────────┐
│ models/database.py           │  │ models/dhr_database.py        │
│                              │  │                               │
│ class DatabaseManager:       │  │ class DhrDatabaseManager:     │
│   __init__(db_path)          │  │   __init__(db_path)           │
│   _ensure_database_exists()  │  │   _ensure_database_exists()   │
│   _migrate_legacy_db()       │  │   get_connection() [@ctx]     │
│   get_connection() [@ctx]    │  │   _create_tables()            │
│   _create_tables()           │  │   ...DHR 도메인 메서드        │
│   ...mixing 도메인 메서드    │  │                               │
└──────────────────────────────┘  └──────────────────────────────┘
        ↑ data_manager.py + 테스트2        ↑ UI 6 + 테스트2
```

**문제점**: 위쪽 4개 메서드(`__init__`, `_ensure_database_exists`, `get_connection`, `_create_tables` 골격)는 거의 동일하게 두 곳에 복제돼 있다.

---

## 2. 목표 다이어그램

```
                  ┌──────────────────────────────────────┐
                  │ models/_sqlite_base.py                │
                  │                                       │
                  │ class SqliteManagerBase:              │
                  │   __init__(db_path)                   │
                  │   _ensure_database_exists()           │
                  │   get_connection() [@ctx]             │
                  │   _create_tables() [abstractmethod]   │
                  └────────────────┬─────────────────────┘
                                   │ inherits
              ┌────────────────────┴────────────────────┐
              │                                         │
┌─────────────▼──────────────┐         ┌────────────────▼───────────────┐
│ models/database.py         │         │ models/dhr_database.py         │
│                            │         │                                │
│ class MixingDatabaseManager│         │ class DhrDatabaseManager        │
│   _migrate_legacy_db()     │         │   _try_create_unique_lot_index │
│   _create_tables() (impl)  │         │   _create_tables() (impl)       │
│   save_mixing_record()     │         │   save_dhr_record()             │
│   ...mixing 도메인 only    │         │   ...DHR 도메인 only            │
└────────────────────────────┘         └────────────────────────────────┘
```

---

## 3. `SqliteManagerBase` API

```python
# models/_sqlite_base.py
"""
SQLite 매니저 공통 베이스.
프로젝트 내 모든 SQLite DB 매니저는 이 클래스를 상속한다.
외부 모듈은 _ 접두 모듈을 직접 import 하지 않는다 — 매니저 서브클래스를 통해 사용.
"""
import os
import sqlite3
from abc import abstractmethod
from contextlib import contextmanager
from typing import Iterator

from utils.logger import logger
from utils.error_handler import DatabaseError


class SqliteManagerBase:
    """SQLite 기반 DB 매니저의 공통 인프라.

    서브클래스는 `_create_tables()`를 구현해야 하며,
    `__init__`에서 base의 `__init__`을 호출한 뒤 `self._create_tables()`를 호출한다.
    """

    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        self._ensure_database_exists()
        # 주의: _create_tables()는 서브클래스에서 호출한다
        # (베이스 __init__ 종료 후 서브클래스 추가 초기화를 끝낸 뒤)

    def _ensure_database_exists(self) -> None:
        db_dir = os.path.dirname(self.db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)

    @contextmanager
    def get_connection(self) -> Iterator[sqlite3.Connection]:
        conn = None
        try:
            conn = sqlite3.connect(self.db_path)
            conn.execute("PRAGMA foreign_keys = ON")
            conn.row_factory = sqlite3.Row
            yield conn
        except sqlite3.Error as e:
            if conn:
                conn.rollback()
            logger.error(f"데이터베이스 오류({self.db_path}): {e}")
            raise DatabaseError(f"데이터베이스 연결 오류: {e}")
        finally:
            if conn:
                conn.close()

    @abstractmethod
    def _create_tables(self) -> None:
        """서브클래스에서 도메인 테이블/인덱스를 생성한다."""
        raise NotImplementedError
```

### 설계 결정

| 결정 | 근거 |
|---|---|
| **`_create_tables()`는 base가 자동 호출하지 않음** | DhrDB는 `_try_create_unique_lot_index` 같은 도메인 메서드를 `_create_tables` 안에서 부른다. base가 자동 호출하면 메서드 정의 순서를 강제하게 됨. |
| **`_migrate_legacy_db`는 base에 두지 않음** | Mixing 전용 책임. DhrDB는 처음부터 새 경로에 생성됨. |
| **`abstractmethod` 사용하되 `abc.ABC` 비상속** | 기존 코드가 클래스 인스턴스화 시점에 abstractmethod 강제 검증을 받지 않아도 됨. 단순히 "구현 강제" 신호로만 활용. (Python의 abstractmethod는 ABC 상속 없으면 런타임 강제 안 함 — 의도된 선택.) |
| **`_ensure_database_exists`만 base에서 호출** | `__init__` 분할 책임. 서브클래스가 자기 초기화를 끝낸 뒤 `self._create_tables()` 명시적 호출. |

---

## 4. 서브클래스 적용 패턴

### `MixingDatabaseManager`

```python
class MixingDatabaseManager(SqliteManagerBase):
    """`mixing_records.db`만 다루는 매니저.

    이 매니저는 일반 배합 작업의 `mixing_records`/`mixing_details`/`recipes` 테이블만 다룬다.
    DHR(Device History Record) 데이터는 `models.dhr_database.DhrDatabaseManager`를 사용하라.
    """

    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            db_path = DB_FILE
        super().__init__(db_path)
        self._migrate_legacy_db()
        self._create_tables()
        logger.info(f"데이터베이스 초기화 완료: {self.db_path}")

    # _migrate_legacy_db 그대로 유지
    # _create_tables 그대로 유지 (mixing_records, mixing_details, recipes)
    # 도메인 메서드 그대로 유지
```

### `DhrDatabaseManager`

```python
class DhrDatabaseManager(SqliteManagerBase):
    """`dhr_records.db`만 다루는 매니저.

    이 매니저는 DHR(Device History Record) 전용 테이블만 다룬다.
    일반 배합 기록은 `models.database.MixingDatabaseManager`를 사용하라.
    Google Sheets 백업은 의도적으로 미지원(민감성 차이).
    """

    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            db_path = DHR_DB_FILE
        super().__init__(db_path)
        self._create_tables()
        logger.info(f"DHR 데이터베이스 초기화 완료: {self.db_path}")
```

---

## 5. Rename 영향 분석

`DatabaseManager` → `MixingDatabaseManager` 변경 영향:

| 파일 | 변경 |
|---|---|
| `v3/models/database.py` | `class DatabaseManager` → `class MixingDatabaseManager` |
| `v3/models/data_manager.py:14` | `from models.database import DatabaseManager` → `MixingDatabaseManager` |
| `v3/models/data_manager.py` 본문 | 클래스 사용 지점 모두 수정 |
| `v3/tests/integration/test_data_integration.py:16` | import 수정 |
| `v3/tests/unit/test_data_manager_aggregates.py:20` | import 수정 |

**별칭 미제공 결정**: 사용처가 v3 내부 5개 지점뿐이고, 별칭은 "어느 쪽 이름이 정식인가" 혼란을 영구히 남긴다. 한 번에 끊는다.

---

## 6. 테스트 설계

`v3/tests/unit/test_sqlite_base.py` (신규):

| 테스트 | 검증 사항 |
|---|---|
| `test_ensure_database_creates_directory` | 존재하지 않는 디렉토리 경로 → 자동 생성 |
| `test_get_connection_yields_row_factory` | conn.row_factory == sqlite3.Row |
| `test_get_connection_enables_foreign_keys` | `PRAGMA foreign_keys`가 ON |
| `test_get_connection_rolls_back_on_sqlite_error` | sqlite3.Error 발생 시 rollback + DatabaseError로 래핑 |
| `test_get_connection_closes_on_normal_exit` | 정상 종료 후 conn.close() 호출됨 |

테스트는 임시 디렉토리에 _DummyManager(SqliteManagerBase)를 만들어 검증 (실제 매니저 의존성 없음).

---

## 7. 검증 체크리스트

- [ ] `models/_sqlite_base.py` 신규
- [ ] `database.py`: `MixingDatabaseManager`로 rename + 베이스 상속
- [ ] `data_manager.py` import/사용처 수정
- [ ] `dhr_database.py`: 베이스 상속
- [ ] 두 모듈에 책임 경계 docstring 추가
- [ ] `test_sqlite_base.py` 5건 통과
- [ ] `run_tests.py` 회귀 0건
- [ ] `git grep "import DatabaseManager"` 결과 0건 (rename 누락 점검)

---

**작성일**: 2026-05-27
**버전**: 1.0
**Status**: Design ✅
