# DHR 수기입력·대량생성 출력 비동기화 — Plan

> PDCA Feature: `dhr_export_async` (PDCA #36)
> 작성일: 2026-06-10 · Level: Starter (Desktop / PySide6)

## 1. 배경 / 문제 정의

PDCA #33이 의도적으로 후속 분리한 잔여분. 앱에서 **UI가 멈추는 마지막 2개 경로**:

| # | 경로 | 위치 | 증상 |
|---|------|------|------|
| A | DHR 수기 입력 저장+출력 | `manual_input_interface.py:313` (`_run_export_pipeline`) | 저장 버튼 → Excel COM PDF 변환 동안 UI 정지 (단건, 수초~수십초) |
| B | DHR 일괄 생성 및 출력 | `bulk_creation_interface.py:267` (`generator.generate`) | N건 루프 × (DB 저장+서명 합성+Excel+COM PDF) — **수십 건이면 분 단위 완전 정지** |

#33의 `ui/workers.py` 인프라(start_worker/use_com/wait_for_workers)를 그대로 재사용한다.
이 사이클이 끝나면 **앱에서 UI 스레드를 막는 무거운 작업이 0**이 된다.

## 2. 목표 (Goals)

| # | 요구사항 | 충족 방법 |
|---|----------|-----------|
| 1 | 수기 입력 출력이 UI를 막지 않음 | DB 저장(동기, LOT 즉시 표시) 후 Excel+PDF 파이프라인만 워커로 |
| 2 | 일괄 생성이 UI를 막지 않음 | `generator.generate` 전체(DB+출력 루프)를 워커로 — generator는 Qt 비의존이라 안전 |
| 3 | 워커 함수의 위젯 접근 0 | 위젯 값(effects/signature/include_time 등)을 워커 시작 전 스냅샷 — 특히 A의 `_run_export_pipeline` 내부 `scan_effects_panel.get_data()` 호출(`:380`)을 호출부로 끌어올림 |
| 4 | 중복 실행 방지 | 저장/생성 버튼 busy_widgets (#33 패턴) |
| 5 | 결과/부분실패 알림 기존 UX 유지 | on_result/on_failed 슬롯이 기존 QMessageBox 분기(Done/Partial Success/오류) 그대로 수행 |
| 6 | 종료 안전 | MainWindow.closeEvent의 wait 대상에 manual/bulk 인터페이스 추가 |

## 3. 범위 (Scope)

### In Scope
- **A 수기 입력**: `_save_and_export` 분리 — 검증·DB 저장·LOT 표시(동기) → 출력 파이프라인(워커, use_com=True).
  `_run_export_pipeline`을 위젯 무접근 형태로 리팩토링(effects_params 파라미터화)
- **B 일괄 생성**: 검증·파싱·위젯 스냅샷(동기) → `generate(...)` 워커 실행(use_com=True).
  결과는 `(count, export_failures)` 튜플로 워커 fn에서 묶어 반환
- 버튼 busy 가드 (수기 저장 버튼, 일괄 생성 버튼 — 로컬 변수면 `self.` 승격)
- `MainWindow.closeEvent` wait 대상 확장 (manual/bulk 인터페이스 워커)
- 기존 테스트 갱신(`test_manual_input_save_export` — start_worker 동기 스텁 패치) + 신규 배선 테스트
- 기존 341개 회귀 없음

### Out of Scope (후속)
- 일괄 생성 진행률 바/건별 진행 표시 — FunctionWorker에 progress 시그널 추가가 필요해 별도 사이클
  (이번엔 #33과 동일하게 busy 표시까지)
- 일괄 생성 취소 버튼 — 진행률과 같은 사이클에서 함께
- `DhrBulkGenerator` 자체 리팩토링 (이미 #15에서 정리됨)

## 4. 핵심 설계 결정 (요약 — 상세는 Design)

1. **A의 DB 저장은 동기 유지**: 빠르고(SQLite 단건), 결과 LOT이 즉시 위젯에 표시되어야 함
   (`product_lot_edit.setText`). #33 저장 경로와 동일한 분할선 — "영속화 동기, 무거운 후처리 비동기".
2. **B는 DB 저장까지 워커에 포함**: N건 루프라 DB 저장조차 누적되면 길고, 루프 중간 결과를
   위젯에 표시할 필요 없음. SQLite는 호출별 연결이라 워커 스레드 안전(#33 §1 확인 사실).
3. **generator 결과 묶음**: `generate` 반환(count)과 `last_export_failures`(인스턴스 속성)를
   워커 클로저에서 `(count, failures)`로 묶어 시그널 1회로 전달 — 슬롯에서 속성 재접근 금지
   (워커 종료 후에도 안전하지만 명시적 전달이 계약상 깨끗).
4. **검증 실패는 워커 이전에**: 입력 오류 QMessageBox는 기존처럼 동기 경로에서 즉시.

## 5. 영향 범위 (변경 파일 예상)

| 파일 | 변경 |
|------|------|
| `v3/ui/panels/manual_input_interface.py` | `_save_and_export` 분리 + 워커 적용 + busy |
| `v3/ui/panels/bulk_creation_interface.py` | `_bulk_create` 분리 + 워커 적용 + busy (generate_btn `self.` 승격) |
| `v3/ui/main_window.py` | closeEvent wait 대상 확장 |
| `v3/tests/unit/test_manual_input_save_export.py` | start_worker 동기 스텁 패치 |
| `v3/tests/unit/` 신규/보강 | 일괄 생성 배선 테스트 (워커 mock) |

> models 계층 변경 없음 (`DhrBulkGenerator`/`ExcelExporter` 그대로 — Qt 비의존이라 워커 실행 가능).

## 6. 리스크 / 완화

| 리스크 | 영향 | 완화 |
|--------|------|------|
| `_run_export_pipeline` 내부 위젯 접근 잔존 | 높음 (스레드 위반) | effects_params 파라미터화 + 워커 fn 위젯 무접근 원칙(#33 규약) 준수 검증 |
| 기존 수기 입력 테스트 7개 동기 가정 | 중 | `start_worker` 동기 스텁 패치 (#33 스모크 패턴 재사용) |
| 일괄 생성 중 사용자가 다른 탭 조작 | 저 | 허용 (UI 응답이 목표). DB 쓰기는 호출별 연결로 안전. 생성 버튼만 busy |
| 종료 시 일괄 생성 워커 잔류 (분 단위 작업) | 중 | closeEvent wait(기본 3초) — 진행 중 COM은 renderer finally가 Quit 보장. 한계는 Design에서 명시 |
| Python 3.9 호환 | 중 | typing 준수 |

## 7. 완료 기준 (Definition of Done)

- [ ] 요구사항 1~6 구현
- [ ] 수기 저장/일괄 생성 중 UI 응답 유지
- [ ] gap-detector 일치율 ≥ 90%
- [ ] 신규/갱신 테스트 통과 + 기존 341개 회귀 없음
- [ ] 완료 보고서 작성

## 8. 다음 단계

→ `/pdca design dhr_export_async`
