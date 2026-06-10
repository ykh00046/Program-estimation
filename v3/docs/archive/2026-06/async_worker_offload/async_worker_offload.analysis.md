# UI 스레드 분리 (비동기 워커 오프로드) — Gap 분석

> PDCA Feature: `async_worker_offload` (PDCA #33)
> 분석일: 2026-06-10 · 도구: gap-detector Agent + 수동 검증
> 설계: `docs/02-design/features/async_worker_offload.design.md`

## 1. 분석 요약

| 구분 | 내용 |
|------|------|
| 1차 Match Rate | **89%** (gap-detector) — 90% 문턱 근소 미달 |
| 발견 갭 | 실질 갭 3건 + 명명/표기 차이 4건 |
| Act 조치 | 실질 갭 3건 즉시 수정 + 설계 문서 5곳 정렬 |
| 최종 Match Rate | **~99%** (갭 해소 후 재산정) |
| 테스트 | 295개 전부 통과 (기존 276 + 신규 19, 회귀 0) |

## 2. 항목별 검증 결과 (1차)

| 설계 항목 | 1차 | 비고 |
|-----------|:---:|------|
| §2.1 워커 인프라 계약 (시그널명/use_com/busy/owner 추적) | ✅ 100% | `_on_finished` 바운드 메서드는 의도적 개선 (아래 4.1) |
| §2.2 저장 경로 (auto_backup 회귀 보존, backup_lot_to_sheets, 비모달 실패) | ✅ 100% | |
| §2.3 내보내기 경로 | ⚠️ 88% | 단건 재출력 busy 가드 누락 (갭 G3) |
| §2.4 종료 안전 (closeEvent) | ❌ 33% | 다이얼로그 2파일 누락 (갭 G1/G2) |
| §3 오류 처리 정책 | ✅ 100% | |
| §4 테스트 계획 | ✅ 100% | 테스트 위치만 신규 파일로 재배치 |
| §6 호환성 (Py3.9/스타일/20줄) | ✅ 100% | |

## 3. 실질 갭과 Act 조치 (모두 해소됨)

| # | 갭 | 영향 | 조치 |
|---|----|------|------|
| G1 | `record_view_dialog.py`에 closeEvent/wait_for_workers 부재 | 높음 — 출력 중 닫기 시 COM 워커 조기 파괴 위험 | `RecordDetailDialog`·`RecordViewDialog` 양쪽에 `closeEvent → wait_for_workers(self)` 추가 |
| G2 | `dhr_record_view_dialog.py`에 closeEvent 부재 | 높음 — 동일 | 워커 소유 클래스 `DhrRecordDetailDialog`에 closeEvent 추가 (`DhrRecordViewDialog`는 워커를 소유하지 않아 대상 아님 — 상세 다이얼로그가 실제 owner) |
| G3 | `RecordDetailDialog.export_report` busy_widgets 미전달 → 출력 중 재클릭 시 중복 워커 기동 가능 | 중간 — 요구사항 #3 부분 미충족 | `export_btn`을 `self.` 승격 후 `busy_widgets=(self.export_btn,)` 전달 |

## 4. 의도적 변경 (설계 ≠ 구현, 설계 문서에 역반영 완료)

1. **busy 복원/정리 위치**: 설계의 start_worker 클로저 → `FunctionWorker._on_finished` 바운드 메서드.
   근거: PySide6에서 클로저(비-QObject) 슬롯은 워커 스레드에서 직접 실행되어 위젯 접근이
   스레드 위반이 됨. QThread 객체(GUI 스레드 소속)의 바운드 메서드 연결로 queued 실행 보장.
2. 슬롯/함수 명명: `_show_batch_result→_show_export_result`, `_run_export_job→_run_dhr_export_job`.
3. 일괄 출력 인자: 위치 인자 → args/kwargs 분리 (기능 동일, 더 명시적).
4. auto_backup 테스트 위치: `test_data_manager.py` 보강 → 신규 `test_data_manager_backup.py` (응집도↑).
5. 추가 헬퍼 `_is_auto_backup_active()` — 동기/비동기 백업 가드 DRY 공유.
6. 보너스 범위: 단건 재출력(`RecordDetailDialog.export_report`)도 워커화 (설계엔 일괄만 명시).

## 5. 테스트 증적

- `tests/unit/test_workers.py` 10개 — run() 동기 계약(성공/예외/kwargs), COM 초기화 3케이스,
  start_worker 배선 4케이스 (FunctionWorker.start 동기 패치 — 설계 §4의 "실스레드 기동 회피" 준수.
  1차 시도에서 실스레드 기동 테스트가 headless 크래시(exit 9)를 일으켜 설계대로 회귀)
- `tests/unit/test_data_manager_backup.py` 5개 — auto_backup 회귀 가드, backup_lot_to_sheets 페이로드/예외
- `tests/unit/test_save_controller_backup.py` 3개 — backup_runner 위임, 검증 실패 시 미발사
- 기존 스모크 2파일 갱신 — `start_worker` 동기 스텁 패치로 배선 검증 유지 + 대시보드 실패 경로 1개 추가
- **전체 295개 통과, 회귀 0**

## 6. 결론

핵심 아키텍처(워커 계약, COM 스레드 안전, 저장-백업 분리, 오류 정책, Py3.9 호환)는 설계와
100% 일치하며, 1차에서 미달했던 종료 안전(§2.4)과 중복 실행 가드는 Act에서 전부 해소되었다.

**최종 Match Rate ~99% (≥90%)** → `/pdca report async_worker_offload` 진행 가능.
