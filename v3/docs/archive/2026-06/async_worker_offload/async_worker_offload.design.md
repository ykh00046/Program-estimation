# UI 스레드 분리 (비동기 워커 오프로드) — Design

> PDCA Feature: `async_worker_offload` (PDCA #33)
> 작성일: 2026-06-10 · Plan: `docs/01-plan/features/async_worker_offload.plan.md`

## 1. 아키텍처 개요

```
[UI 스레드]                                  [워커 스레드 (QThread)]
버튼 클릭
  → 위젯 상태 스냅샷 (페이로드 수집)
  → start_worker(owner, fn, ...)
      - busy 위젯 disable                      fn(*args) 실행
      - 워커 참조 보관 (GC 방지)                 - (use_com) CoInitialize/CoUninitialize
                                               - 예외 → failed(str)
  ← result_ready(object) / failed(str)         - 성공 → result_ready(result)
      (Qt queued connection → UI 스레드 슬롯)
  → 결과 알림 / busy 위젯 복원 / 워커 정리
```

**불변 규칙**
- 워커 함수(fn)는 **QWidget을 절대 만지지 않는다**. 위젯 읽기는 시작 전, 위젯 갱신은 슬롯에서만.
- models 계층은 Qt 비의존 유지 — QThread 생성·시그널 연결은 전부 ui 계층.
- SQLite는 호출마다 새 연결(`_sqlite_base.py:47` `sqlite3.connect` per call)이므로
  워커 스레드에서의 DB 읽기/쓰기는 안전 (연결 객체 공유 없음).

## 2. 컴포넌트 설계

### 2.1 `v3/ui/workers.py` (신규)

```python
class FunctionWorker(QThread):
    """임의 함수를 백그라운드에서 실행하는 범용 워커."""
    result_ready = Signal(object)   # fn 반환값 (성공)
    failed = Signal(str)            # 사용자 표시용 오류 메시지 (실패)

    def __init__(self, fn: Callable, args: tuple = (),
                 kwargs: Optional[Dict] = None,
                 use_com: bool = False, parent=None) -> None: ...

    def run(self) -> None:
        # use_com=True → pythoncom.CoInitialize() / finally CoUninitialize()
        # 성공: result_ready.emit(fn(*args, **kwargs))
        # 예외: logger.error(exc_info=True) 후 failed.emit(str(e))
```

> ⚠ 시그널명은 `result_ready`/`failed` — QThread 내장 `finished`와 **충돌 금지**.

```python
def start_worker(owner: QWidget, fn: Callable, *,
                 args: tuple = (), kwargs: Optional[Dict] = None,
                 on_result: Callable[[object], None],
                 on_failed: Callable[[str], None],
                 use_com: bool = False,
                 busy_widgets: Sequence[QWidget] = ()) -> FunctionWorker:
```

`start_worker` 책임:
1. `busy_widgets` 전부 `setEnabled(False)`
2. `FunctionWorker(parent=owner)` 생성 + `owner._active_workers`(set)에 추가 — 이중 GC 방지
3. `result_ready → on_result`, `failed → on_failed` 연결
4. `start()` 후 워커 반환

busy 복원 + set 제거 + `deleteLater()`는 **`FunctionWorker._on_finished` 바운드 메서드**가
내장 `finished` 시그널로 수행한다 — PySide6에서 클로저(비-QObject) 슬롯은 워커 스레드에서
직접 실행되므로, QThread 객체(GUI 스레드 소속)의 바운드 메서드로 연결해야 queued 실행이
보장된다. 같은 이유로 `on_result`/`on_failed`도 QObject 바운드 메서드여야 한다.

```python
def wait_for_workers(owner: QWidget, timeout_ms: int = 3000) -> None:
    """owner의 활성 워커를 최대 timeout_ms씩 대기 (종료/닫기 시 호출)."""
```

**중복 실행 가드**: 별도 락 없음 — 트리거 버튼이 `busy_widgets`에 포함되어
실행 중 재클릭이 물리적으로 불가능한 구조로 보장.

### 2.2 저장 경로 — Sheets 백업 분리

**`v3/models/data_manager.py`**

| 변경 | 내용 |
|------|------|
| `save_record(..., auto_backup: bool = True)` | 파라미터 추가. `auto_backup=True`(기본)면 기존처럼 동기 백업 → **기존 호출자/테스트 동작 불변**. False면 백업 생략 |
| `_build_backup_records(record_data, details) -> List[Dict]` | 기존 `_backup_to_google_sheets` 내부의 페이로드 조립부(현 `data_manager.py:122-140`)를 메서드로 추출 |
| `_is_auto_backup_active() -> bool` | 백업 활성 가드(enabled + auto_on_save) DRY 추출 — 동기/비동기 양쪽이 공유 |
| `backup_lot_to_sheets(product_lot: str) -> Tuple[bool, str]` (신규 공개) | DB에서 해당 LOT의 record+details를 재조회(`export_existing_record`와 동일 조회 경로 재사용) → `_build_backup_records` → `google_sheets_backup.backup_records` 호출. **DB가 진실의 원천**이므로 저장된 내용 그대로 백업됨 |

**`v3/ui/controllers.py`** — `save_record()` (현 `:198-206`)

```python
lot = self.data_manager.save_record(**payload, auto_backup=False)
self.on_success(lot)                       # 저장 완료 알림은 즉시 (UX 불변)
self._start_backup_worker(lot)             # 백업은 비동기 발사
```

`_start_backup_worker(lot)`:
- `google_sheets_backup.is_backup_enabled()` False면 no-op
- `start_worker(main_window, dm.backup_lot_to_sheets, args=(lot,), use_com=False, ...)`
- `on_result(success, msg)`: `update_backup_status()` 호출 + 상태바 메시지
- `on_failed(msg)`: 상태바 경고 메시지 (모달 금지 — best-effort 의미 유지)
- busy_widgets 없음 (저장 버튼은 즉시 재사용 가능, 백업은 백그라운드 사실)

> 순서 보장: DB 저장 → 재고 차감은 `save_record` 내부에서 기존 그대로 **동기** 실행.
> 비동기化 대상은 네트워크 백업뿐.

### 2.3 내보내기 경로 3종

#### (a) 기록 조회 일괄 출력 — `v3/ui/record_view_dialog.py`
`RecordOpsController.export_records`는 이미 Qt 비의존(`record_ops_controller.py:27`) →
**배치 전체를 워커로**:
```python
start_worker(self, self._ops.export_records,
             args=(checked_items, effects_params),
             kwargs={"include_work_time": include_time},
             use_com=True,
             busy_widgets=(self.export_btn, self.delete_btn),
             on_result=self._show_export_result,   # 기존 집계 알림 재사용
             on_failed=self._show_export_error)
```
효과 파라미터 등 위젯 값은 호출 전 스냅샷. `BatchResult`는 그대로 슬롯에 전달.
같은 파일의 단건 재출력(`RecordDetailDialog.export_report` →
`export_existing_record`)도 동일 패턴(use_com=True, busy=출력 버튼)으로 워커화한다.

#### (b) DHR 기록 출력 — `v3/ui/dhr_record_view_dialog.py` (`export_report:85`)
2단계 분리:
- `_collect_export_job() -> Dict` (UI 스레드): 서명 옵션·스캔 효과 등 **위젯 값 스냅샷** + record/details 복사
- `_run_dhr_export_job(job) -> Optional[str]` (모듈 레벨 함수 — 위젯 비접근 보장, 워커, `use_com=True`): ImageProcessor 서명 합성(PIL)
  → `ExcelExporter.export_to_excel` → `export_to_pdf` → 서명 임시파일 정리 → 최종 PDF 경로 반환
- `on_result`: 기존 완료/실패 QMessageBox 분기 그대로, `on_failed`: 오류 QMessageBox
- busy: 출력 버튼

#### (c) 대시보드 내보내기 — `v3/ui/panels/dashboard_panel.py` (`_export_excel:256`, `_export_pdf:260`)
```python
def _export_pdf(self):
    start, end = self._current_date_range()        # 위젯 읽기 (UI 스레드)
    start_worker(self, self._exporter.export_pdf, args=(start, end),
                 use_com=True,
                 busy_widgets=(self.export_excel_btn, self.export_pdf_btn),
                 on_result=self._notify_export,     # 기존 알림 재사용
                 on_failed=self._notify_export_error)
```
Excel 내보내기는 `use_com=False` (openpyxl 순수 Python). `DashboardExporter`의 DB 조회는
워커 스레드에서 실행되나 per-call 연결이므로 안전 (§1).

### 2.4 종료 안전

- `MainWindow.closeEvent` → `wait_for_workers(self)` (백업 워커 잔류 대비)
- 다이얼로그(`record_view`, `dhr_record_view`) `closeEvent` → 동일. 내보내기 중 닫기 시
  최대 3초 대기 후 진행 (COM 프로세스는 renderer의 finally에서 Quit 보장됨)

## 3. 오류 처리 정책

| 경로 | 실패 표시 | 근거 |
|------|----------|------|
| Sheets 백업 | 상태바 + 백업 상태 라벨 (비모달) | best-effort 의미 유지, 저장 성공과 분리 |
| 일괄 출력 | 기존 BatchResult 집계 알림 (부분 실패 LOT 목록) | 기존 UX 유지 |
| DHR 출력 / 대시보드 | QMessageBox (기존과 동일) | 단건 작업, 명시적 사용자 액션 |

모든 워커 예외는 `failed` 시그널 전 `logger.error(exc_info=True)` 기록.

## 4. 테스트 계획

| 테스트 | 파일 | 검증 내용 |
|--------|------|----------|
| FunctionWorker 단위 | `tests/unit/test_workers.py` (신규) | `run()` 동기 직접 호출 — 성공 시 result_ready 1회/failed 0회, 예외 시 반대. `use_com=True` 시 CoInitialize/CoUninitialize 호출 (pythoncom monkeypatch) |
| start_worker 가드 | 〃 | busy_widgets disable → finished 후 enable, owner._active_workers 등록/해제 |
| auto_backup 파라미터 | `tests/unit/test_data_manager_backup.py` (신규) | `auto_backup=False`면 backup_records 미호출, 기본값이면 기존처럼 호출 (회귀 가드) |
| backup_lot_to_sheets | 〃 | 저장된 LOT 재조회 → backup_records에 14개 컬럼 페이로드 전달 (mock) |
| 컨트롤러 저장 흐름 | `tests/unit/` 보강 | save_record가 `auto_backup=False`로 호출되고 백업 워커가 시작됨 (start_worker mock) |
| 대시보드/다이얼로그 스모크 | 기존 smoke 보강 | 내보내기 클릭 → start_worker가 올바른 fn/args로 호출 (워커 자체는 mock, 동기 실행) |
| 회귀 | `tests/run_tests.py` | 기존 276개 전부 통과 |

> 스모크 테스트에서 실제 QThread 기동은 피한다(headless 타이밍 플레이크 방지) —
> `start_worker`를 동기 실행 스텁으로 패치하여 배선만 검증.

## 5. 구현 순서

1. `ui/workers.py` + `tests/unit/test_workers.py` — 인프라 먼저, 단독 검증
2. `data_manager.py`: `auto_backup` 파라미터 + `_build_backup_records` 추출 + `backup_lot_to_sheets` + 테스트
3. `controllers.py`: 저장 후 백업 워커 발사 + 상태 표시
4. `dashboard_panel.py`: 내보내기 2종 워커 적용
5. `record_view_dialog.py`: 일괄 출력 워커 적용
6. `dhr_record_view_dialog.py`: export_report 2단계 분리 + 워커 적용
7. 종료 가드(`wait_for_workers`) 배선 + 전체 회귀 테스트 + 수동 확인(저장/출력 중 창 드래그)

## 6. 호환성 체크리스트

- [ ] Python 3.9: `Optional`/`Callable`/`Sequence` typing 사용, `|` 유니온 금지
- [ ] PyInstaller: `pythoncom`은 기존 pywin32 의존성에 포함 — hidden import 추가 불필요 확인
- [ ] 신규 색/스타일 없음 (busy는 setEnabled만 사용)
- [ ] 함수 20줄 이내 / 타입 힌트 전체

## 7. 다음 단계

→ `/pdca do async_worker_offload` (구현)
