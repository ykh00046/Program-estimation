# 로그 로테이션 동시성 안정화 (PDCA #21)

> **Feature**: log_rotation_concurrency
> **Author**: AI Assistant
> **Created**: 2026-05-31
> **Status**: ✅ Plan
> **PDCA Cycle**: #21 (PDCA #20 §8 잔여 관찰 종결)

---

## 1. 배경

PDCA #20에서 전체 테스트 스위트 hang을 근절했으나, 동시 테스트 실행 시 stderr에 다음 노이즈가 남았다:

```
--- Logging error ---
PermissionError: [WinError 32] 다른 프로세스가 파일을 사용 중 ...
  os.rename('mixing_program.log' -> 'mixing_program.log.2026-05-29')
  (logging/handlers.py doRollover)
```

### 근본 원인

- `utils/logger.py`의 `TimedRotatingFileHandler`가 **고정 공유 경로**(`config.settings.LOG_FOLDER` = `%LOCALAPPDATA%\MixingProgram\logs\mixing_program.log`)에 기록.
- 날짜 경계(자정/날짜 변경)에 롤오버 발생 시 `os.rename(현재→.YYYY-MM-DD)` 수행.
- **Windows에서 다른 프로세스가 파일을 점유 중이면 rename이 WinError 32로 실패** → `Handler.handleError`가 traceback을 stderr로 덤프.
- 프로덕션은 단일 인스턴스(Windows Mutex)라 안전. **문제는 멀티프로세스 = 테스트(또는 앱+테스트 동시 구동)** 상황.

## 2. 범위 (In Scope)

### Part A — 내견(resilient) 롤오버 핸들러 (프로덕션 단단화)
- `SafeTimedRotatingFileHandler(TimedRotatingFileHandler)` 신설: `doRollover()`에서 rename 실패(`OSError`/`PermissionError`)를 **삼키고 경고 로그 후 현재 파일에 계속 기록**, `rolloverAt`을 다음 주기로 advance하여 매 emit 재시도(스팸) 방지.
- `_add_file_handlers`가 이 핸들러를 사용.

### Part B — 테스트 로그 격리 (근본 경합 제거)
- `config/settings.py`: `LOG_FOLDER`가 `MIXING_LOG_DIR` 환경변수를 우선 사용(`os.environ.get("MIXING_LOG_DIR", USER_LOG_DIR)`).
- `tests/conftest.py` 신설: 프로젝트 import 이전에 `MIXING_LOG_DIR`을 **프로세스별 임시 디렉토리**로 설정 → 테스트가 공유 프로덕션 로그를 건드리지 않음.
- `tests/run_tests.py`(unittest 러너): `_bootstrap_environment`에서도 동일 env 설정(러너 일관성).

## 3. 비-범위 (Out of Scope)
- `concurrent-log-handler` 등 신규 의존성 도입 (버전 고정 정책 — 도입 안 함)
- 로그 포맷/레벨/보관수(backupCount) 정책 변경
- error.log(`FileHandler`)의 롤오버화 (롤오버 안 하므로 동일 이슈 없음)

## 4. 성공 기준
- [ ] 롤오버 rename 강제 실패 상황에서 traceback 덤프 없이 로깅 지속 (※ Design §2에서 "경고 1회 로그"는 logging 재진입 위험으로 **silent tolerate**로 번복)
- [ ] 테스트 실행 시 로그가 임시 경로로 격리(프로덕션 로그 파일 미접촉)
- [ ] `pytest tests/unit tests/integration` 120 passed, stderr에 `--- Logging error ---`/WinError 32 노이즈 0
- [ ] 프로덕션 동작 불변(실제 플랫폼·단일 인스턴스 경로 영향 없음)
- [ ] Match Rate ≥ 90%

## 5. 위험 & 완화
| 위험 | 완화 |
|---|---|
| doRollover 오버라이드가 stdlib 내부 상태 깨뜨림 | 실패 시 `stream` 재오픈 보장 + `rolloverAt` advance. 강제 실패 단위 테스트로 검증 |
| conftest env 설정 시점이 settings import보다 늦음 | conftest 최상단(프로젝트 import 전)에서 `os.environ` 설정. settings는 import 시 env 조회 |
| MIXING_LOG_DIR 오버라이드가 프로덕션에 누출 | env 미설정 시 기존 `USER_LOG_DIR` 폴백 — 프로덕션은 env 없음 |

## 6. 커밋 계획
1. `feat(logging): add SafeTimedRotatingFileHandler tolerant of rollover rename failure (PDCA #21 A)`
2. `feat(config): allow MIXING_LOG_DIR override + isolate test logs via conftest (PDCA #21 B)`
3. `test: add rollover-failure + log-isolation tests (PDCA #21)`
4. `docs: PDCA #21 analysis + report`

## 7. 다음 단계
`/pdca design log_rotation_concurrency` → 핸들러 doRollover 오버라이드 시그니처/conftest 시점 확정 → `/pdca do`.
