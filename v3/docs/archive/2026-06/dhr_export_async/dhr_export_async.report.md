# DHR 수기입력·대량생성 출력 비동기화 — 완료 보고서

> PDCA Feature: `dhr_export_async` (**PDCA #36**)
> 기간: 2026-06-10 (1일) · 최종 Match Rate: **99%** (1차 통과) · 테스트: **346/346**

## 1. 무엇을 해결했나

#33이 의도적으로 후속 분리했던 **마지막 UI 멈춤 2개 경로**를 해소했다.
이로써 **앱에서 UI 스레드를 막는 무거운 작업이 0**이 되었다 (#33 + #36 완성).

| 경로 | Before | After |
|------|--------|-------|
| A 수기 입력 "저장 및 출력" | Excel COM PDF 변환 동안 UI 정지 (수초~수십초) | DB 저장·LOT 표시는 즉시(동기), 출력만 워커 — 버튼만 busy |
| B "일괄 생성 및 출력" | N건 × (DB+서명+Excel+COM PDF) 루프 — **분 단위 완전 정지** | 루프 전체가 워커 — 생성 중에도 다른 화면 사용 가능 |

## 2. 구현 내역

- **신규 인프라 0** — #33의 `start_worker`/`use_com`/`wait_for_workers` 그대로 재사용
- **분할선 원칙**: A는 "영속화 동기 + 무거운 후처리 비동기" (LOT 즉시 표시 필요),
  B는 DB 포함 전체 비동기 (루프 중간 위젯 갱신 없음, SQLite 호출별 연결로 스레드 안전)
- **위젯 무접근 보장**: A의 `_run_export_pipeline` 내부 `scan_effects_panel.get_data()` 호출을
  **effects_params 파라미터로 끌어올림** — 잠재 스레드 위반 1건을 이번 사이클에서 제거.
  B는 위젯 값 4종(include_time/scan_effects/signature/worker_name)을 클로저 캡처 전 스냅샷
- **결과 묶음 계약**: B의 `generate` 반환(count)과 `last_export_failures`(인스턴스 속성)를
  워커 클로저에서 `(count, failures)` 튜플로 묶어 시그널 1회 전달
- **메시지 비트 보존**: Done / Partial Success(preview 3건+more) / critical 기존 문구 그대로
- **종료 안전**: `MainWindow.closeEvent`가 3-owner(메인/수기/일괄) 워커를 대기 (getattr 가드)
- **models 계층 변경 0**: `DhrBulkGenerator`/`ExcelExporter` 무변경 — Qt 비의존이라 워커 실행 가능

## 3. PDCA 사이클 기록

| 단계 | 결과 |
|------|------|
| Plan | #33 잔여 2경로 특정, 진행률 바·취소 버튼은 후속 분리 |
| Design | 분할선·스냅샷·결과 묶음·closeEvent 확장 설계 |
| Do | UI 2파일 + main_window + 기존 테스트 7개 갱신 + 신규 5개 |
| Check | **99% 1차 통과** — 워커 위젯 접근 정밀 검사 위반 0 |

## 4. 교훈 (Lessons Learned)

1. **"영속화 동기, 후처리 비동기" 분할선의 일반화**: #33(배합 저장)과 동일한 분할선이
   수기 입력에도 그대로 적용됐다 — 결과를 위젯에 즉시 반영해야 하는 작업까지가 동기 경계.
   반대로 중간 UI 갱신이 없는 배치(일괄 생성)는 DB까지 통째로 워커가 옳다.
2. **숨은 위젯 접근은 시그니처로 봉인**: 파이프라인 함수 내부의 `panel.get_data()` 호출은
   동기일 땐 무해하지만 워커화 순간 스레드 위반이 된다. 위젯 값을 파라미터로 받게
   시그니처를 바꾸면 컴파일 수준에서 재발이 차단된다.
3. **인스턴스 속성 결과는 워커 경계에서 값으로 묶기**: `last_export_failures` 같은
   부수 속성은 클로저에서 튜플로 복사해 시그널에 실어야 슬롯-워커 간 상태 공유가 없어진다.

## 5. 후속 과제

- 일괄 생성 진행률 바 + 취소 버튼 — FunctionWorker에 progress 시그널 추가 필요 (별도 사이클)
- 잔여 내실 후보: 레시피 SSOT 이원화 해소, DataManager InventoryService 분리,
  대형 UI 파일 분해, 백업 "지금 재시도" 버튼

## 6. 산출물

- 코드: `manual_input_interface.py`, `bulk_creation_interface.py`, `main_window.py`
- 테스트: `test_bulk_creation_async.py`(신규 5) + `test_manual_input_save_export.py`(동기 스텁 갱신) — 총 346 통과
- 문서: plan / design / analysis / report
