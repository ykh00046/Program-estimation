# UI 스레드 분리 (비동기 워커 오프로드) — 완료 보고서

> PDCA Feature: `async_worker_offload` (**PDCA #33**)
> 기간: 2026-06-10 (1일) · 최종 Match Rate: **~99%** · 테스트: **295/295 통과**

## 1. 무엇을 해결했나

전체 코드 검토(2026-06-10)에서 확인된 **Critical 이슈 2건** — 배합 저장 시 Google Sheets
백업(네트워크 블로킹)과 Excel COM PDF 변환(수초~수십초)이 UI 스레드에서 동기 실행되어
작업 중 앱 전체가 멈추던 문제를 해소했다.

**Before**: 저장 버튼 클릭 → 네트워크 지연만큼 정지 / PDF 출력 → "응답 없음"
**After**: 저장 알림 즉시 표시, 백업·변환은 백그라운드 — UI는 계속 응답

## 2. 구현 내역

### 신규 인프라 — `v3/ui/workers.py`
- `FunctionWorker(QThread)`: 임의 함수 실행, `result_ready`/`failed` 시그널
  (내장 `finished`와 충돌 방지), `use_com=True` 시 스레드별 CoInitialize/CoUninitialize
- `start_worker(owner, fn, ...)`: busy 위젯 가드 + `owner._active_workers` 추적(GC 방지)
- `wait_for_workers(owner)`: 창 닫기/앱 종료 시 잔여 워커 대기
- **스레드 안전 핵심**: 위젯 복원/정리는 `FunctionWorker._on_finished` 바운드 메서드 —
  PySide6에서 클로저 슬롯은 워커 스레드에서 직접 실행되므로 QObject 바운드 메서드로
  GUI 스레드 queued 실행을 보장

### 적용 경로 (5곳)
| 경로 | 파일 | COM |
|------|------|:---:|
| 저장 시 Sheets 백업 | `data_manager.py`(auto_backup 파라미터 + `backup_lot_to_sheets`) + `controllers.py`(backup_runner 주입) + `main_window.py`(워커 발사/상태 표시) | — |
| 기록 일괄 출력 | `record_view_dialog.py` (`_ops.export_records` 배치 전체 워커화) | ✅ |
| 기록 단건 재출력 | `record_view_dialog.py` (`RecordDetailDialog.export_report`) | ✅ |
| DHR 실적서 출력 | `dhr_record_view_dialog.py` (`_collect_export_job` 스냅샷 → `_run_dhr_export_job` 워커) | ✅ |
| 대시보드 Excel/PDF | `dashboard_panel.py` (`_start_export_worker`) | PDF만 |

### 설계 보존 원칙
- models 계층 Qt 비의존 유지 (워커 생성은 ui 계층 전용)
- 저장 순서 불변: DB 저장 → 재고 차감(동기) → 백업(비동기) — best-effort 의미 유지
- 백업 실패는 비모달(상태바), 출력 실패는 기존 QMessageBox UX 그대로
- `auto_backup=True` 기본값으로 기존 호출자/테스트 동작 완전 보존

## 3. PDCA 사이클 기록

| 단계 | 결과 |
|------|------|
| Plan | Critical 2건 정의, 범위 확정 (DHR 수기입력/대량생성·COM 탈피는 후속 분리) |
| Design | 워커 계약·5경로 적용·테스트 전략 설계 |
| Do | 7파일 수정 + 1파일 신규 + 테스트 19개 신규 |
| Check (1차) | **89%** — 갭 3건: 다이얼로그 closeEvent 2건 누락, 단건 출력 busy 가드 누락 |
| Act | 갭 3건 즉시 수정 + 설계 문서 5곳 정렬 → **~99%** |

## 4. 교훈 (Lessons Learned)

1. **PySide6 슬롯 스레드 어피니티**: 시그널을 클로저/일반 함수에 연결하면 워커 스레드에서
   직접 실행된다. UI를 만지는 슬롯은 반드시 QObject 바운드 메서드로 — 이번 사이클의
   가장 중요한 기술적 발견이며 `workers.py` docstring에 규약으로 명문화함.
2. **headless 테스트에서 실제 QThread 기동 금지**: 1차 테스트에서 실스레드+위젯 조합이
   프로세스 크래시(exit 9)를 유발. 설계에 이미 경고했던 패턴 — `FunctionWorker.start`를
   동기 패치하는 방식으로 배선만 결정적으로 검증하는 것이 옳았다.
3. **워커 owner의 생명주기 = 종료 안전의 전부**: 다이얼로그가 워커를 소유하면 닫기 시
   wait가 필수 (COM 작업 중 owner 파괴 → QThread 비정상 종료 위험). gap-detector가
   이 누락을 정확히 잡아냄 — Check 단계의 가치 입증.

## 5. 후속 과제 (다음 사이클 후보)

- **#34 재고 reconcile**: 저장-차감 분리 트랜잭션의 부분 실패 복구 유틸 (전체 검토 High)
- **#35 백업 견고화**: Sheets 컬럼 매핑 고정 + 실패 시 로컬 큐 재시도
- **DHR 수기 입력/대량 생성 비동기화**: 이번 사이클 Out of Scope 분
- **Excel COM 탈피**(reportlab 등): UI 멈춤의 근본 제거 + Excel 미설치 PC 지원 (혁신 후보)
- **LOT 양방향 추적성**: 전체 검토에서 혁신 1순위로 제안된 기능

## 6. 산출물

- 코드: `v3/ui/workers.py`(신규), `data_manager.py`, `controllers.py`, `main_window.py`,
  `dashboard_panel.py`, `record_view_dialog.py`, `dhr_record_view_dialog.py`
- 테스트: `test_workers.py`(10), `test_data_manager_backup.py`(5),
  `test_save_controller_backup.py`(3) 신규 + 스모크 2파일 갱신 — 총 295개 통과
- 문서: plan / design / analysis / report (PDCA 4종 세트)
