# record_view_dialog 책임 분해 (PDCA #23)

> **Feature**: record_view_dialog_decomposition
> **Author**: AI Assistant
> **Created**: 2026-05-31
> **Status**: ✅ Plan
> **PDCA Cycle**: #23 (코드 검토 SRP 후보 — 마지막)

---

## 1. 배경

코드 검토(2026-05-29)에서 `ui/record_view_dialog.py`(671 LOC)가 **조회·표시·수정·재출력·삭제**를 한 곳에서 담당하고 `except Exception` 8곳이 있음이 지적됨. 두 다이얼로그가 UI 구성과 **데이터 오케스트레이션**(특히 일괄 출력/삭제의 성공·실패 집계 루프)을 뒤섞고 있어 테스트성이 낮다.

가장 큰 SRP 부채는 `export_selected_record`/`delete_selected_record`의 **일괄 처리 tally 루프**가 `QMessageBox`와 엉켜 Qt 없이는 검증 불가하다는 점.

## 2. 범위 (In Scope)

### Part A — RecordOpsController 추출 (`ui/record_ops_controller.py` 신설)
일괄 데이터 작업의 집계 로직을 Qt 비의존 컨트롤러로 분리:
- `BatchResult` 데이터클래스: `total`, `success_count`, `fail_count`, `failed_lots`
- `export_records(lots, effects_params, include_work_time) -> BatchResult`
- `delete_records(lots) -> BatchResult`
- 공통 `_run_batch(lots, op)` 헬퍼로 export/delete의 동일 루프(try/성공·실패 집계/로그) 통합(DRY)
- 생성자: `RecordOpsController(data_manager)`

### Part B — 다이얼로그 위임 (`record_view_dialog.py`)
- `export_selected_record`/`delete_selected_record`: 선택 검사 + 확인 다이얼로그(뷰 책임) 후 controller 호출 → `BatchResult`로 요약 메시지 렌더 + 폴더 열기/새로고침(뷰 책임).
- tally 루프·data_manager 직접 호출 제거(컨트롤러로 이동).
- 메시지 문구/동작은 **현행 보존**(무동작변경).

### Part C — 테스트 (`tests/unit/test_record_ops_controller.py` 신설)
- mock data_manager로 export/delete의 전체 성공 / 부분 실패 / 예외 발생 시 `BatchResult` 집계 검증(Qt 불필요).

## 3. 비-범위 (Out of Scope)
- `RecordDetailDialog.save_changes`는 이미 `data_manager.update_record`로 깔끔히 위임 → 변경 안 함.
- UI 빌더(`_build_*`)·집계(aggregate_by_item)·로드(load_records)는 뷰 고유 책임이라 유지.
- 두 다이얼로그 클래스 물리 분리(파일 split)는 비-범위.
- `except Exception`의 UI 이벤트 경계 협소화(의도적, 보류).

## 4. 성공 기준
- [ ] 일괄 출력/삭제 집계 로직이 Qt 비의존 컨트롤러로 분리, 단독 테스트 가능
- [ ] 다이얼로그는 선택검사·확인·메시지·폴더열기만(데이터 루프 제거)
- [ ] 메시지/동작 현행 보존(무동작변경)
- [ ] 전체 스위트 통과(현 128 + 신규) + 시각 스모크(RecordViewDialog 인스턴스화)
- [ ] Match Rate ≥ 90%

## 5. 위험 & 완화
| 위험 | 완화 |
|---|---|
| 요약 메시지 문구 변경(무동작변경 위반) | 문구는 뷰에 유지, 컨트롤러는 집계 수치만 반환. 현행 문자열 보존 |
| export/delete 예외 처리 동작 변화 | 컨트롤러가 per-item try/except로 현행과 동일하게 실패 집계 |
| 다이얼로그 시각 회귀 | offscreen 스모크로 RecordViewDialog/RecordDetailDialog 인스턴스화 확인 |
| controller가 effects_params/include_work_time 누락 | export 시그니처에 동일 인자 전달 |

## 6. 커밋 계획
1. `feat(ui): add RecordOpsController for batch export/delete (PDCA #23 A)`
2. `refactor(ui): delegate batch export/delete to RecordOpsController (PDCA #23 B)`
3. `test: RecordOpsController batch result tests (PDCA #23)`
4. `docs: PDCA #23 analysis + report`

## 7. 다음 단계
`/pdca design record_view_dialog_decomposition` → BatchResult/컨트롤러 시그니처 + 다이얼로그 위임 코드 확정 → `/pdca do`.
