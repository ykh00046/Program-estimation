# 로그 로테이션 동시성 Gap 분석 (PDCA #21)

> **Feature**: log_rotation_concurrency
> **Plan**: [../../01-plan/features/log_rotation_concurrency.plan.md](../../01-plan/features/log_rotation_concurrency.plan.md)
> **Design**: [../../02-design/features/log_rotation_concurrency.design.md](../../02-design/features/log_rotation_concurrency.design.md)
> **Author**: AI Assistant
> **Created**: 2026-05-31
> **Status**: ✅ Match Rate 100%
> **PDCA Cycle**: #21

---

## 1. 분석 개요
- 대상: SafeTimedRotatingFileHandler(Part A) + MIXING_LOG_DIR 테스트 격리(Part B)
- 구현 커밋: `add9378`(Part A), `12019e7`(Part B), `bdfd98b`(테스트)
- 검증: bkit:gap-detector (설계 ↔ 구현 대조)

## 2. 종합 점수

| 항목 | 점수 |
|---|:---:|
| 설계 일치도 | 100% |
| 아키텍처/무영향 보장 | 100% |
| 컨벤션 준수 | 100% |
| **종합** | **100%** |

누락/추가/변경 Gap 0건.

## 3. 항목별 결과

### Part A — SafeTimedRotatingFileHandler (일치)
- `doRollover`가 `except OSError`로 삼키고 `stream` 재오픈 + `rolloverAt` advance (`logger.py:19-25`). 설계 §2와 라인 단위 일치.
- `_add_file_handlers`가 실제 이 핸들러 사용 (`logger.py:66`), 인자(when/interval/backupCount=30/encoding) 보존.
- `PermissionError`(WinError 32)는 `OSError` 하위라 포착됨.

### Part B — 테스트 격리 (일치)
- `LOG_FOLDER = os.environ.get("MIXING_LOG_DIR", USER_LOG_DIR)` (`settings.py:135`).
- `tests/conftest.py`가 프로젝트 import 없이 상단에서 `setdefault`로 env 설정 → settings import 전 반영.
- `run_tests.py`도 동일 env(`import tempfile` 추가).

### 테스트 (일치)
- 3종 모두 존재(메서드명 축약은 클래스 컨텍스트로 의미 보존): rename 실패 tolerate / 실패 후 emit 지속 / env override(원복 포함).

### 무영향 보장 (확인)
- env 미설정 프로덕션 경로 = `USER_LOG_DIR` 불변.
- `error.log`의 `FileHandler`는 미변경(롤오버 안 함 → 동일 이슈 없음).

### silent tolerate 결정 (Design이 Plan 대체)
- Plan은 "경고 1회 로그", Design §2가 logging 재진입 위험으로 **silent tolerate**로 번복. 구현은 except 블록에 로깅 호출 없음 → Design과 일치. (Plan 성공기준 문구에 번복 주석 추가 완료)

## 4. 실행 검증 (정적 분석 외 실측)
- `tests/unit/test_logging_rotation.py` 3 passed.
- `pytest tests/unit tests/integration` → **123 passed, hang 0, 4.75s**.
- **stderr 로테이션 노이즈 0건** (`Logging error`/`WinError 32`/`doRollover` grep 0).

## 5. 결론
Match Rate **100%** (≥90%) → `/pdca report` 진행 가능. 즉시 조치 Gap 없음. Plan 문서 정합(번복 주석) 반영 완료.
