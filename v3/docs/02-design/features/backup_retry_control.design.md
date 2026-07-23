# Backup Retry Control 설계서

> **작성일**: 2026-06-18
> **Plan**: `v3/docs/01-plan/features/backup_retry_control.plan.md`

## Context Anchor

| Anchor | 내용 |
|---|---|
| WHY | 보존된 실패 백업을 관찰·복구할 운영 제어가 필요하다. |
| WHO | 생산 기록과 Google Sheets 백업을 관리하는 관리자 |
| RISK | 네트워크 재시도가 UI를 멈추거나 실패 큐를 유실하는 것 |
| SUCCESS | 대기량 표시, 비동기 재시도, 성공 시 비움, 실패 시 보존, 회귀 0 |
| SCOPE | 설정 다이얼로그, 관리자 진입점, UI/모델 통합 테스트 |

## 1. 설계 옵션

| 옵션 | 설명 | 복잡도 | 유지보수 | 위험 |
|---|---|---:|---:|---:|
| A 최소 변경 | 설정 창에서 동기 호출 | 낮음 | 낮음 | UI 정지 높음 |
| B 클린 아키텍처 | 별도 RetryService/상태 모델 신설 | 높음 | 높음 | 과설계 |
| **C 균형안** | 기존 Backup/Queue/FunctionWorker 재사용, UI만 조합 | **중간** | **높음** | **낮음** |

**선택: Option C.** 새 도메인 계층 없이 검증된 #33/#35 계약을 조합한다.

## 2. 구조

```text
AdminDialog
  └─ Google Sheets 백업 설정 버튼
       └─ GoogleSheetsSettingsDialog
            ├─ BackupQueue.count() → 대기 건수 표시
            └─ start_worker(...)
                 └─ GoogleSheetsBackup.backup_records([])
                      ├─ 성공: pending 전송 + queue.clear()
                      └─ 실패: pending 유지
```

## 3. 인터페이스

### GoogleSheetsSettingsDialog

- 생성자: `__init__(parent=None, backup=None)`
- `backup` 미주입 시 동일 설정 객체로 `GoogleSheetsBackup` 생성
- `_refresh_queue_status()`: `queue.count()`를 라벨/버튼 상태에 반영
- `_retry_pending()`: `start_worker`로 `backup_records([])` 호출
- `_on_retry_result((ok, message))`: 상태 갱신 후 정보/경고 표시
- `_on_retry_failed(message)`: 예외 경고 및 상태 갱신
- 실행 중 `reject`/`closeEvent` 차단

### AdminDialog

- 작업자 관리 탭의 관리자 그룹에 `Google Sheets 백업 설정` 버튼 추가
- `_open_google_sheets_settings()`에서 모달 실행

## 4. 상태 전이

| 현재 | 이벤트 | 다음 | UI |
|---|---|---|---|
| pending=0 | 화면 열기 | idle | `대기 0건`, 재시도 비활성 |
| pending>0 | 화면 열기 | ready | `대기 N건`, 재시도 활성 |
| ready | 재시도 클릭 | running | 버튼 비활성, 닫기 차단 |
| running | 성공 | idle | 대기 0건, 성공 메시지 |
| running | 실패 | ready | 대기 N건 유지, 실패 메시지 |

## 5. 오류 처리

- 구성/인증/전송 오류는 기존 `(False, message)` 결과를 그대로 표시한다.
- 워커의 예상 밖 예외는 `failed(str)` 경로로 표시한다.
- 큐 읽기 오류는 기존 `BackupQueue.count()`의 안전한 0건 폴백을 따른다.

## 6. 테스트 계획

- L1: 기존 큐/GoogleSheetsBackup 단위 테스트 전체
- L2: 설정 다이얼로그 0건/대기 건수/재시도 성공·실패/워커 위임
- L3: 관리자 버튼 → 설정 다이얼로그 진입 smoke
- L4: 전체 pytest 회귀
- L5: 성공 시 clear, 실패 시 pending 보존 기존 테스트 재검증

## 7. 구현 순서

1. 설정 다이얼로그에 의존성 주입과 상태 UI 추가
2. 비동기 재시도 및 종료 안전성 추가
3. 관리자 진입점 복원
4. UI smoke 테스트 추가
5. 타깃/전체 테스트 및 gap 반복

## 8. 추적 주석

- UI 조합부: `# Design Ref: §2 ...`
- 재시도 경로: `# Plan SC-3 ...`

## 11. Implementation Guide

### 11.3 Session Guide

| 모듈 | 파일 | 완료 조건 |
|---|---|---|
| module-1 | `google_sheets_settings_dialog.py` | 상태/재시도/종료 안전성 |
| module-2 | `admin_dialog.py` | 관리자 진입점 |
| module-3 | 신규 smoke test | SC-1~SC-5 자동 검증 |

