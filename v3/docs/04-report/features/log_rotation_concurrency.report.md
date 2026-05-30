# log_rotation_concurrency — Completion Report (PDCA #21)

> **Feature**: log_rotation_concurrency
> **Author**: AI Assistant
> **Created**: 2026-05-31
> **Status**: ✅ Completed
> **Match Rate**: 100%
> **Plan**: [../../01-plan/features/log_rotation_concurrency.plan.md](../../01-plan/features/log_rotation_concurrency.plan.md)
> **Design**: [../../02-design/features/log_rotation_concurrency.design.md](../../02-design/features/log_rotation_concurrency.design.md)
> **Analysis**: [../../03-analysis/features/log_rotation_concurrency.analysis.md](../../03-analysis/features/log_rotation_concurrency.analysis.md)

---

## 1. 요약

PDCA #20 §8이 남긴 잔여 관찰(동시 테스트 시 로그 로테이션 `os.rename` WinError 32 stderr 노이즈)을 종결.

- **Part A**: `SafeTimedRotatingFileHandler` — 롤오버 rename 실패를 견디고(현재 파일 유지 + 다음 주기 자가 재시도) traceback 덤프를 제거. 프로덕션 단단화.
- **Part B**: `MIXING_LOG_DIR` 환경변수 오버라이드 + `tests/conftest.py`로 테스트 로그를 프로세스별 임시 경로로 격리 → 공유 프로덕션 로그 경합 **근본 제거**.

의존성 추가 없이 stdlib만으로 해결.

## 2. 변경 (커밋, origin/main 반영)

| 커밋 | 내용 |
|---|---|
| `add9378` | Part A: `SafeTimedRotatingFileHandler.doRollover`(OSError tolerate + stream 재오픈 + rolloverAt advance), `_add_file_handlers` 적용 |
| `12019e7` | Part B: `settings.LOG_FOLDER` env 오버라이드 + `tests/conftest.py` 신설 + `run_tests.py` 일관성 |
| `bdfd98b` | 테스트 3종(rename 실패 tolerate / 실패 후 emit / env override) |

## 3. 검증

- 신규 `test_logging_rotation.py` **3 passed**.
- `pytest tests/unit tests/integration` → **123 passed**(120→123), hang 0, **4.75s**(로그 격리로 더 빨라짐).
- **stderr 로테이션 노이즈 0건** (`Logging error`/`WinError 32`/`doRollover` grep 0).
- gap-detector **Match Rate 100%**, 무영향 보장(프로덕션 경로·error.log 불변) 확인.

## 4. 성공 기준 달성 (Plan §4)

- [x] 롤오버 rename 실패 시 traceback 덤프 없이 로깅 지속 (silent tolerate)
- [x] 테스트 로그가 임시 경로로 격리(프로덕션 로그 미접촉)
- [x] 전체 스위트 통과 + stderr 로테이션 노이즈 0
- [x] 프로덕션 동작 불변
- [x] Match Rate ≥ 90% (100%)

## 5. 교훈

1. **로깅 인프라는 절대 앱을 죽이지 않아야** — 롤오버 실패를 삼키고 자가치유하는 것이 정석. doRollover는 emit 경로 내부라 실패 시 경고 로깅조차 재진입 위험 → **silent tolerate**가 옳음(Plan→Design에서 번복).
2. **테스트는 공유 프로덕션 자원을 건드리면 안 됨** — 고정 로그 경로가 멀티프로세스 경합의 근원. env 오버라이드 + conftest 선(先) 설정으로 근본 격리. 부수 효과로 스위트가 더 빨라짐(13.85s→4.75s).
3. **conftest는 프로젝트 import 전에 env를 세팅할 수 있는 가장 이른 훅** — settings가 import 시 env를 읽도록 설계하면 깔끔히 연동.
4. **Plan→Design 결정 번복은 문서에 흔적을 남겨야** — "경고 1회 로그"가 Design에서 폐기됐음을 Plan에 주석으로 표기(gap-detector 지적 반영).

## 6. 결론

PDCA #21 완료. 동시 테스트 환경의 로그 로테이션 노이즈를 근절하고, 로깅 핸들러를 멀티프로세스 경합에 견고하게 만듦. 코드 검토(2026-05-29)에서 시작된 후속 정리 항목이 모두 종결됨. 다음은 `/pdca archive log_rotation_concurrency`로 #21 문서 이관 가능.
