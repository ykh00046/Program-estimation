# 로그 로테이션 동시성 안정화 설계서 (PDCA #21)

> **Feature**: log_rotation_concurrency
> **Plan**: [../../01-plan/features/log_rotation_concurrency.plan.md](../../01-plan/features/log_rotation_concurrency.plan.md)
> **Author**: AI Assistant
> **Created**: 2026-05-31
> **Status**: 🔄 Design
> **PDCA Cycle**: #21

---

## 1. 설계 원칙
- **로깅은 앱을 죽이지 않는다**: 롤오버 실패는 삼키고 자기치유(다음 주기 재시도). traceback 덤프 금지.
- **프로덕션 무영향**: env 미설정 시 기존 경로/동작 유지. 단일 인스턴스에선 롤오버 정상.
- **테스트 근본 격리**: 공유 프로덕션 로그를 테스트가 건드리지 않게 경로 분리.
- **무의존성**: 신규 패키지 도입 없이 stdlib만 사용.
- **Python 3.9 호환**, `typing` 사용.

## 2. Part A — SafeTimedRotatingFileHandler (`utils/logger.py`)

stdlib `TimedRotatingFileHandler.doRollover`는 `self.rotate()`(=`os.rename`)에서 실패하면, **stream을 이미 닫은(None) 상태로 예외를 던지고 `rolloverAt`을 갱신하지 못한다** → `Handler.handleError`가 stderr로 traceback 덤프 + 다음 emit마다 재시도.

```python
import time

class SafeTimedRotatingFileHandler(logging.handlers.TimedRotatingFileHandler):
    """롤오버 rename 실패(멀티프로세스 파일 잠금, Windows WinError 32 등)에 견디는 핸들러.

    실패 시: 현재 파일 스트림을 재오픈해 로깅을 지속하고, rolloverAt을 다음 주기로
    advance하여 매 emit 재시도(스팸)를 막는다. 다음 주기에 자연 재시도된다.
    """
    def doRollover(self):
        try:
            super().doRollover()
        except OSError:
            # rename 실패 → 롤오버 보류. stream은 super가 이미 None으로 닫았으므로 재오픈.
            if self.stream is None:
                self.stream = self._open()
            # 다음 경계로 advance (현재 파일에 계속 기록, 다음 주기에 재시도)
            self.rolloverAt = self.computeRollover(int(time.time()))
```

- `_add_file_handlers`의 `TimedRotatingFileHandler(...)` → `SafeTimedRotatingFileHandler(...)`로 교체. 인자(when/interval/backupCount/encoding) 동일.
- **silent tolerate** 채택(경고 로그는 비채택): doRollover는 emit 경로 내부에서 호출되므로 logging 재진입 위험. 대신 조용히 보류하고 다음 주기 자가 재시도. (이벤트는 드물고 자기치유)

## 3. Part B — 테스트 로그 격리

### 3.1 `config/settings.py`
```python
# 기존
LOG_FOLDER = USER_LOG_DIR
# 변경
LOG_FOLDER = os.environ.get("MIXING_LOG_DIR", USER_LOG_DIR)
```
- env 미설정(프로덕션) → `USER_LOG_DIR` 유지. `os.makedirs(USER_LOG_DIR)`(L57)은 무해하게 잔존.

### 3.2 `tests/conftest.py` (신설)
```python
"""pytest 전역 픽스처/부트스트랩. 프로젝트 import 이전에 실행되어야 한다."""
import os
import tempfile

# 공유 프로덕션 로그와의 경합/오염 방지: 테스트 로그를 프로세스별 임시 경로로 격리.
# 프로젝트(config.settings) import 전에 설정해야 LOG_FOLDER가 이를 읽는다.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("MIXING_LOG_DIR", tempfile.mkdtemp(prefix="mixing_test_logs_"))
```
- pytest는 `tests/conftest.py`를 테스트 수집·import보다 먼저 로드 → `config.settings` import 시 env 반영.
- xdist 워커는 각자 conftest 로드 → 워커별 독립 디렉토리.
- `setdefault` 사용 → 외부에서 이미 지정 시 존중.

### 3.3 `tests/run_tests.py` (unittest 러너 일관성)
`_bootstrap_environment`에 추가:
```python
os.environ.setdefault("MIXING_LOG_DIR", tempfile.mkdtemp(prefix="mixing_test_logs_"))
```
(import tempfile 추가)

## 4. 테스트 설계

### 4.1 `tests/unit/test_logging_rotation.py` (신설)
- `test_safe_handler_tolerates_rename_failure`: `SafeTimedRotatingFileHandler`를 임시 파일로 생성 → `rotate`(또는 `self.rotate`)를 `OSError`를 던지도록 monkeypatch → `doRollover()` 직접 호출이 **예외 없이 반환**, `stream`이 None 아님, `rolloverAt`이 과거가 아님(현재 시각보다 큼) 검증.
- `test_safe_handler_emit_after_failed_rollover`: 강제 롤오버 실패 후에도 `emit`이 정상 기록되는지(파일에 라인 증가) 검증.
- `test_log_folder_honors_env_override`: `MIXING_LOG_DIR` 설정 후 `importlib.reload(config.settings)` → `LOG_FOLDER == 임시경로` 검증(원복 포함).

### 4.2 통합/회귀
- `pytest tests/unit tests/integration` → 120+ passed, **stderr에 `--- Logging error ---`/`WinError 32` 0건**.
- 기존 `test_sqlite_base`/패널/데이터 테스트 회귀 0.

## 5. 위험 재확인
| 위험 | 결정 |
|---|---|
| `super().doRollover()`가 rename 전 다른 OSError | 동일하게 tolerate(스트림 재오픈) — 로깅 지속이 우선 |
| `computeRollover` 호출 시 self.utc/atTime 상태 | super와 동일 인스턴스 메서드 사용이라 일관 |
| conftest env가 settings 선(先) import에 밀림 | conftest는 rootdir의 가장 이른 import. 프로젝트 모듈 import 문을 conftest 상단보다 뒤에 두지 않음(상단 env 설정만) |
| reload 테스트가 전역 settings 오염 | 테스트 끝에 env 원복 + `importlib.reload`로 복구 |

## 6. 커밋 계획
1. `feat(logging): SafeTimedRotatingFileHandler tolerant of rollover rename failure (PDCA #21 A)`
2. `feat(config): MIXING_LOG_DIR override + tests/conftest log isolation (PDCA #21 B)`
3. `test: rollover-failure + env-override tests (PDCA #21)`
4. `docs: PDCA #21 analysis + report`

## 7. 다음 단계
`/pdca do log_rotation_concurrency` — 커밋 1부터 순차, 각 단계 후 전체 스위트 stderr 노이즈 0 확인.
