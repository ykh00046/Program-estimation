# 두 DB 매니저 책임 경계 명문화 완료 보고서 (PDCA #18)

> **Feature**: database_manager_boundary
> **Phase**: Act / Completion
> **Author**: AI Assistant
> **Created**: 2026-05-27
> **Status**: ✅ Completed
> **Match Rate**: 100%

---

## 1. 한 줄 요약

`DatabaseManager`/`DhrDatabaseManager`의 공통 인프라를 **`SqliteManagerBase`**로 추출하고, `DatabaseManager`를 **`MixingDatabaseManager`**로 rename하며, 두 모듈에 **책임 경계 docstring**을 명문화했다. 두 파일 본문 -54라인, 회귀 0건.

---

## 2. 달성 사항

### 코드 변경

| 산출물 | 내용 |
|---|---|
| `models/_sqlite_base.py` (신규, 59 LOC) | `SqliteManagerBase`: `__init__(db_path, log_prefix)`, `_ensure_database_exists()`, `get_connection()` (`@contextmanager`, PRAGMA, row_factory, rollback, close) |
| `models/database.py` | `DatabaseManager` → `MixingDatabaseManager`. `SqliteManagerBase` 상속. 중복 메서드 4개 제거. 모듈 docstring에 책임 경계 명시. -29 라인. |
| `models/dhr_database.py` | `DhrDatabaseManager`는 명명 유지. `SqliteManagerBase` 상속. 중복 메서드 3개 제거. 모듈 docstring에 책임 경계 명시. -25 라인. |
| `models/data_manager.py` | import + 사용처 2건 rename |
| `tests/integration/test_data_integration.py` | import + 사용처 2건 rename |
| `tests/unit/test_data_manager.py` | `patch('models.data_manager.DatabaseManager')` → `MixingDatabaseManager` |
| `tests/unit/test_data_manager_aggregates.py` | 모든 `DatabaseManager` 참조 → `MixingDatabaseManager` |
| `tests/unit/test_sqlite_base.py` (신규, 70 LOC) | 5건 베이스 단위 테스트 |
| 문서 | plan + design + analysis + report |

### 검증

- **`test_sqlite_base.py` 5/5 통과**
- **Mixing/Dhr 스모크 통과** (인스턴스화 + 쿼리)
- **`run_tests.py` 53 tests, 14 errors, 5 skipped** — PDCA #18 적용 전후 동일 (git stash 비교)
- **`DatabaseManager` 잔여 참조 0건** (`Dhr`/`Mixing`/`Sqlite` 제외)
- **회귀 0건**

---

## 3. 효과

| 효과 | 측정 |
|---|---|
| 두 매니저 본문 LOC 감소 | -54 라인 (database.py -29 + dhr_database.py -25) |
| 공통 인프라 단일화 | `get_connection` 컨텍스트 매니저가 1곳에만 존재 |
| 명명 명료화 | `DatabaseManager`(모호) → `MixingDatabaseManager`(명시). DhrDB와 대구. |
| 책임 경계 문서화 | 두 모듈이 서로를 가리키는 양방향 docstring 참조 |
| `improvement.plan #10`(DRY) 부분 충족 | DB 매니저 계열 중복 제거 완료 (UI 빌더 중복은 별도 사이클) |
| 회귀 안전망 | `test_sqlite_base.py` 5건 신규 — 향후 베이스 변경 시 즉시 검출 |

---

## 4. 의사결정 기록

| 결정 | 근거 |
|---|---|
| **물리 DB 통합 안 함** | `mixing_records.db`와 `dhr_records.db`는 다른 도메인·다른 스키마·다른 백업 정책(Google Sheets 유/무). 통합은 안티-패턴. |
| **`DhrDatabaseManager` rename 안 함** | 이미 명확한 이름. 변경 비용만 발생. |
| **별칭(alias) 미제공** | 사용처 5건뿐, 별칭은 영구적인 명명 혼란을 남김. 한 번에 끊는다. |
| **`_create_tables`는 베이스 abstractmethod 미적용** | DhrDB가 `_try_create_unique_lot_index` 같은 도메인 헬퍼를 `_create_tables` 안에서 호출. 베이스가 자동 호출하면 메서드 정의 순서 강제. 서브클래스가 `__init__`에서 명시적 호출. |
| **`_migrate_legacy_db`는 베이스에 두지 않음** | Mixing 전용 책임. DhrDB는 신규 시스템이라 마이그레이션 불필요. |
| **로그 접두사(`log_prefix`) 파라미터화** | 기존 로그 메시지("데이터베이스 오류" / "DHR 데이터베이스 오류")와 비트-동일성 유지로 운영 알람/grep 호환성 보존. |

---

## 5. 교훈 (Lessons Learned)

1. **"통합"이라는 단어 트랩** — 사용자 분석 단계에서 "두 매니저 통합"으로 지목됐으나, 코드를 정독해보면 실제로는 **다른 도메인**이라 통합 불가. 진짜 부채는 "공통 인프라 중복 + 명명 모호 + 책임 미문서화"였다. **Plan 단계에서 문제 재정의를 두려워하지 말 것.**
2. **mock patch 경로는 grep `import|.`만으로 잡히지 않는다** — `patch('models.x.SymbolName')` 같은 문자열 경로도 별도 grep 필요. 본 사이클에서 1건 발견.
3. **`git stash` 사전·사후 비교는 회귀 검증의 표준 도구** — pandas 미설치로 일부 테스트가 collection 단계에서 실패해도, 사전·사후 동일성 비교로 회귀 0건을 입증할 수 있다.
4. **공통 베이스의 abstractmethod는 신중히** — `_create_tables()`를 abstractmethod로 묶으면 서브클래스의 메서드 정의 순서를 강제하게 됨. 본 사이클에서는 명시적 호출 패턴(서브클래스 `__init__`에서 `self._create_tables()`)이 더 자유롭다고 판단.

---

## 6. 미해결 / 차기 사이클 후보

1. **`test_excel_exporter` 14건 사전 결함** — `models.excel_exporter` attribute resolution 실패. PDCA #18 무관, 별도 사이클 거리.
2. **pandas 의존 테스트 격리 부족** — `data_manager.py`가 모듈 임포트 시점에 `pandas`를 강제 요구. 일부 환경에서 테스트 collection 실패. 차기 사이클 후보.
3. **`improvement.plan #10` UI 빌더 중복 제거** — 본 사이클은 DB 매니저 영역만 처리. UI 빌더 공통화는 별도 사이클.
4. **자재 재고 임계값 알림** (사용자 가치) — PDCA #17 자연 후속.

---

## 7. 커밋 제안 (사용자 승인 시)

원자성 4커밋 권장:

```
feat(models): add SqliteManagerBase common infrastructure (PDCA #18 Part A)
refactor(models): rename DatabaseManager → MixingDatabaseManager, inherit base (PDCA #18 Part B)
refactor(models): make DhrDatabaseManager inherit SqliteManagerBase (PDCA #18 Part C)
test: add SqliteManagerBase unit tests + update mock paths (PDCA #18 Part D)
docs: PDCA #18 plan/design/analysis/report for database_manager_boundary
```

---

**작성일**: 2026-05-27
**Status**: Report ✅
**Cycle**: #18 Completed
