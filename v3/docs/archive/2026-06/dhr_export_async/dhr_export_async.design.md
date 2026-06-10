# DHR 수기입력·대량생성 출력 비동기화 — Design

> PDCA Feature: `dhr_export_async` (PDCA #36)
> 작성일: 2026-06-10 · Plan: `docs/01-plan/features/dhr_export_async.plan.md`

## 1. 아키텍처 개요

#33의 `ui/workers.py` 인프라 그대로 재사용. 신규 인프라 없음.

```
[A 수기 입력]  검증 → DB 저장 → LOT 표시  (동기, UI 스레드)
                  └→ start_worker(출력 파이프라인, use_com=True, busy=save_btn)
                        on_result → _notify_save_result (기존 Done/Partial 분기)
                        on_failed → Partial Success warning (기존 문구)

[B 일괄 생성]  검증·파싱·위젯 스냅샷  (동기, UI 스레드)
                  └→ start_worker(generate 전체, use_com=True, busy=generate_btn)
                        on_result((count, failures)) → 기존 Done/Partial 분기
                        on_failed → 기존 critical
```

분할선 원칙(#33): **A는 영속화 동기 + 무거운 후처리 비동기** (LOT 즉시 표시 필요),
**B는 DB 포함 전체 비동기** (루프 중간 위젯 갱신 없음, SQLite 호출별 연결로 스레드 안전).

## 2. 컴포넌트 설계

### 2.1 A — `manual_input_interface.py`

**(a) `_run_export_pipeline` 위젯 무접근화** — 시그니처 변경:
```python
def _run_export_pipeline(self, data: dict, details_data: list,
                         effects_params: dict) -> tuple:
    # 기존 본문에서 effects_params = self.scan_effects_panel.get_data() (현 :380) 제거,
    # 파라미터 사용. 나머지(ExcelExporter excel→pdf, RuntimeError) 비트 동일.
```
> self 바운드지만 워커에서 위젯을 만지지 않게 됨 — config/exporter 접근만 잔존(스레드 안전).

**(b) `_save_and_export` 분리** (현 `:298-322`):
```python
def _save_and_export(self):
    # 검증 → _collect_data → _build_details_for_export → _persist_dhr_record
    # → product_lot 반영 (여기까지 기존 그대로, 동기)
    effects_params = self.scan_effects_panel.get_data()   # 위젯 스냅샷 (UI 스레드)
    self._exporting_lot = saved_lot
    start_worker(self, self._run_export_pipeline,
                 args=(data, details_data, effects_params),
                 use_com=True, busy_widgets=(self.save_btn,),
                 on_result=self._on_export_done, on_failed=self._on_export_failed)

def _on_export_done(self, result) -> None:
    excel_path, pdf_path = result
    self._notify_save_result(self._exporting_lot, excel_path, pdf_path)   # 기존 분기 재사용

def _on_export_failed(self, message: str) -> None:
    # 기존 "Partial Success" warning 문구 유지 (DB 저장은 이미 성공)
    QMessageBox.warning(self, "Partial Success",
                        f"DB save succeeded but export failed.\n\nLOT: {self._exporting_lot}\n{message}")
```
- 기존 try/except(`:312-322`)는 워커의 failed 경로로 대체 — 메시지 의미 동일
- busy 해제는 `_on_finished`(#33)가 자동 처리. `save_btn`은 검증 게이트(`_update_actions...`)와
  무관한 독립 버튼이라 단순 복원으로 충분

### 2.2 B — `bulk_creation_interface.py`

**(a) `generate_btn` self 승격** (현 `:179` 로컬) → `self.generate_btn` (busy 대상).

**(b) `_bulk_create` 분리** (현 `:243-292`):
```python
def _bulk_create(self):
    # 제품명/엔트리 검증 + 파싱 (기존 그대로 — 실패 시 즉시 warning, 워커 미기동)
    include_time = self.chk_include_time.isChecked()          # ┐
    scan_effects = self.scan_effects_panel.get_data()         # │ 위젯 스냅샷
    signature_options = self.signature_panel.get_data()       # ┘ (UI 스레드)
    generator = DhrBulkGenerator(self.dhr_db, self.lot_manager)

    def job() -> tuple:                                       # 워커 실행체 — 위젯 무접근
        count = generator.generate(entries=..., product_name=..., materials=...,
                                   worker=self.worker_name, include_time=include_time,
                                   scan_effects=scan_effects,
                                   signature_options=signature_options, export=True)
        return count, list(generator.last_export_failures)    # 결과 묶음 (설계 결정 3)

    start_worker(self, job, use_com=True,
                 busy_widgets=(self.generate_btn,),
                 on_result=self._on_bulk_done, on_failed=self._on_bulk_failed)

def _on_bulk_done(self, result) -> None:
    count, export_failures = result
    # 기존 Done / Partial Success 분기 비트 동일 (preview 3건 + more)

def _on_bulk_failed(self, message: str) -> None:
    logger.error(f"DHR 일괄 생성 실패: {message}")
    QMessageBox.critical(self, "오류", f"일괄 생성 중 오류가 발생했습니다.\n{message}")
```
- `_build_lot_map_by_date`의 ValueError(자재 LOT 누락)는 워커 안에서 발생 →
  failed 시그널 → `_on_bulk_failed` critical. 기존엔 generate 호출 try/except가 받던 것 —
  표시 형식 동일(critical), 타이밍만 비동기.
- `worker_name`은 str 속성 읽기(위젯 아님) — 클로저 캡처 허용.

### 2.3 종료 안전 — `main_window.py`

```python
def closeEvent(self, event):
    for owner in (self, self.manual_interface, self.bulk_interface):
        wait_for_workers(owner)
    super().closeEvent(event)
```
- `getattr(self, "...", None)` 가드: `__init__` 조기 종료(작업자 미선택) 시 인터페이스 미생성 가능.
- **한계 명시**: 일괄 생성은 분 단위일 수 있어 wait(3초)로 완료 보장은 안 됨 —
  COM 프로세스는 renderer/exporter의 finally가 Quit을 보장하므로 좀비 Excel은 없음.
  완전한 종료 대기/취소는 진행률 사이클(후속)에서.

## 3. 오류 처리 정책

| 경로 | 표시 | 비고 |
|------|------|------|
| A 출력 실패 (Excel 실패 RuntimeError 포함) | "Partial Success" warning (기존 문구) | DB 저장은 성공 상태 |
| A PDF만 실패 (excel, None 반환) | on_result 경로 → `_notify_save_result`의 기존 Partial 분기 | 예외 아님 — 기존 의미 보존 |
| B 자재 LOT 누락 (ValueError) / 기타 예외 | critical (기존 문구) | 워커 failed 경로 |
| B 건별 출력 실패 | Partial Success (failures preview 3건, 기존 문구) | generate 내부 best-effort 유지 |
| 입력 검증 실패 (A/B) | 기존 warning — **워커 미기동** | |

## 4. 테스트 계획

| 테스트 | 파일 | 검증 |
|--------|------|------|
| 기존 수기 입력 오케스트레이션 7개 | `test_manual_input_save_export.py` 갱신 | `start_worker` 동기 스텁 패치(#33 패턴) — 호출 순서/부분 실패 분기 기존 단언 유지 |
| `_run_export_pipeline` 파라미터화 | 〃 | effects_params 인자로 전달됨 (scan_effects_panel.get_data가 파이프라인 내부에서 미호출) |
| B 배선 | `test_bulk_creation_async.py` (신규, 워커 동기 스텁 + generator mock) | 검증 실패 시 워커 미기동 / 성공 시 (count, failures) 분기 Done·Partial / 예외 시 critical / generate_btn busy 전달 |
| closeEvent 확장 | 단위 또는 검수 | wait_for_workers가 3개 owner에 호출 |
| 회귀 | `run_tests.py` | 기존 341개 통과 (특히 test_dhr_bulk_generator 9개 — generator 무변경이므로 그대로) |

## 5. 구현 순서

1. A: `_run_export_pipeline` 파라미터화 → `_save_and_export` 워커 분리 → 기존 테스트 갱신
2. B: `generate_btn` 승격 → `_bulk_create` 워커 분리 → 신규 배선 테스트
3. `main_window.closeEvent` 확장
4. 전체 회귀 + 보고

## 6. 호환성 체크리스트

- [ ] models 계층 변경 0 (`DhrBulkGenerator`/`ExcelExporter` 무변경)
- [ ] 사용자 대면 메시지 문구 비트 보존 (Done/Partial Success/오류)
- [ ] Python 3.9 typing
- [ ] 신규 색/스타일 없음 (busy=setEnabled만)
- [ ] 함수 20줄 이내 / 타입 힌트

## 7. 다음 단계

→ `/pdca do dhr_export_async`
