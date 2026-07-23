# Backup Retry Control Gap Analysis

> **분석일**: 2026-06-18
> **PDCA Cycle**: #41
> **최종 Match Rate**: **100%**

## Context Anchor

| WHY | WHO | RISK | SUCCESS | SCOPE |
|---|---|---|---|---|
| 실패 백업의 관찰·즉시 복구 | 관리자 | UI 정지·큐 유실 | 상태/비동기/보존/회귀 | 설정 UI·관리자 진입·테스트 |

## 1. 전략 및 성공 기준 검증

| 기준 | 상태 | 근거 |
|---|:---:|---|
| SC-1 관리자 진입점 | 충족 | `admin_dialog.py:151-153,343-346` |
| SC-2 대기 상태/버튼 연동 | 충족 | `google_sheets_settings_dialog.py:96-102`; UI tests |
| SC-3 FunctionWorker 비동기 경로 | 충족 | `google_sheets_settings_dialog.py:104-120` |
| SC-4 성공 0건/실패 보존 표시 | 충족 | `test_google_sheets_settings_dialog_smoke.py:57-70` |
| SC-5 회귀 없음 | 충족 | unit+integration **384 passed** |

## 2. Design 대 구현 Gap

| 설계 항목 | 구현 | 결과 |
|---|---|:---:|
| 관리자 버튼 | `google_sheets_btn` | Match |
| 대기 건수 표시 | `_refresh_queue_status` | Match |
| 수동 flush | `backup_records([])` | Match |
| 비동기/중복 방지 | `start_worker`, 버튼 disable | Match |
| 종료 안전성 | `reject`, `closeEvent` guard | Match |
| 성공/실패 피드백 | `_on_retry_result`, `_on_retry_failed` | Match |

추가 기능, 누락, 계약 편차는 없다. 모델/큐 스키마 변경도 없다.

## 3. 1차 Check 및 Iterate

1차 구현은 기능 요구를 충족했으나 `result_ready`가 `QThread.finished`보다 먼저 발생하여,
성공 뒤 공통 busy 복원이 재시도 버튼을 잘못 활성화할 가능성을 발견했다.

- 수정: 재시도 버튼은 직접 disable하고 `worker.finished`에 `_refresh_queue_status` 연결
- 결과: 최종 큐 상태가 워커 종료 후 단일 진실로 반영됨
- 재검증: 타깃 **25/25**, 전체 **384/384** 통과

## 4. Match Rate

| 축 | 점수 | 근거 |
|---|---:|---|
| Structural | 100% | 설계 파일/진입점/메서드 전부 존재 |
| Functional | 100% | 0건·대기·성공·실패·진입 흐름 검증 |
| Contract | 100% | 기존 `backup_records([]) -> (bool, str)` 무변경 |
| Runtime | 100% | offscreen PySide6 UI 및 전체 회귀 실행 |
| **Overall** | **100%** | Critical/Important gap 0 |

## 5. Decision Record Verification

| 결정 | 준수 | 결과 |
|---|:---:|---|
| Option C, 기존 자산 조합 | 예 | 신규 서비스/스키마 없이 완료 |
| 네트워크는 UI 스레드 밖 | 예 | `FunctionWorker` 사용 |
| 실패 큐 보존 | 예 | #35 기존 테스트 재통과 |

