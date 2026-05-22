# 로직 함수 리팩토링 설계서 (PDCA #15)

> **Feature**: logic_function_refactor
> **Plan**: [../01-plan/features/logic_function_refactor.plan.md](../../01-plan/features/logic_function_refactor.plan.md)
> **Author**: AI Assistant
> **Created**: 2026-05-21
> **Status**: 🔄 Design
> **PDCA Cycle**: #15

---

## 1. 설계 원칙

순수 Extract Method (#13 패턴) + 헬퍼 추출. 동작·시그널·DB 호출 인자 불변.

- UI 빌더: 위젯/레이아웃 반환, `self.` 노출 위젯은 빌더 내부에서 그대로 할당.
- 로직 헬퍼: 명확한 입출력 시그니처, 호출 순서는 원본 유지.
- 타입 힌트는 `typing` 모듈 (Python 3.9, CLAUDE.md).

---

## 2. Part B-1: `RecordDetailDialog.init_ui` (89줄)

원본 행 44–131. 88줄.

| 신규 메서드 | 반환 | 원본 행 | 책임 |
| --- | --- | --- | --- |
| `init_ui` (오케스트레이터) | None | 44–48, 131 | layout·edit_mode 플래그·빌더 조립·setLayout |
| `_build_info_group` | `QGroupBox` | 50–81 | 제품 LOT / 작업자 / 레시피 / 배합량 / 작업일시 그리드 |
| `_build_detail_group` | `QGroupBox` | 84–108 | 배합 상세 테이블 + 데이터 채우기 |
| `_build_button_bar` | `QHBoxLayout` | 110–130 | 수정/저장/실적서/닫기 버튼 |

`self.` 노출: `edit_mode`, `worker_edit`, `amount_edit`, `table`, `edit_btn`, `save_btn`.

---

## 3. Part B-2: `RecordViewDialog.init_ui` (89줄)

원본 행 284–372.

| 신규 메서드 | 반환 | 원본 행 | 책임 |
| --- | --- | --- | --- |
| `init_ui` (오케스트레이터) | None | 286, 371–372 | layout 조립 |
| `_build_filter_group` | `QGroupBox` | 288–302 | 시작일/종료일/조회 버튼 |
| `_build_records_table` | `QTableWidget` | 304–312 | 6컬럼 기록 테이블 + 시그널 |
| `_build_aggregation_group` | `QGroupBox` | 314–332 | 품목 콤보 + 집계 |
| `_build_button_bar` | `QHBoxLayout` | 334–371 | 전체선택/해제/상세/시간체크/출력/폴더/삭제/닫기 |

`self.` 노출: `start_date`, `end_date`, `table`, `item_combo`, `agg_result_label`, `chk_include_time_export`.

---

## 4. Part B-3: `manual_input_interface._save_and_export` (82줄)

원본 행 309–390.

### 신규 헬퍼

| 헬퍼 | 시그니처 | 책임 |
| --- | --- | --- |
| `_build_details_for_export(data)` | `(data) -> List[Dict]` | 테이블 → details_data (행 16–28 추출) |
| `_persist_dhr_record(data, details_data)` | `(data, details_data) -> Optional[str]` | 제품 LOT 생성 + DB 저장 + 실패 시 critical popup. 성공 시 LOT 반환, 실패 시 None |
| `_run_export_pipeline(data, details_data)` | `(data, details_data) -> Tuple[Optional[str], Optional[str]]` | Excel/PDF 출력. 실패 시 RuntimeError raise |
| `_notify_save_result(lot, excel_path, pdf_path)` | `(lot, excel, pdf) -> None` | 결과 메시지박스(전체 성공 / 부분 성공) |

### 오케스트레이터 (`_save_and_export`)
```
if not _validate(): return
_recalc_theory()
data = _collect_data()
details_data = _build_details_for_export(data)
saved_lot = _persist_dhr_record(data, details_data)
if saved_lot is None: return  # DB 실패, 이미 popup 표시됨
data["product_lot"] = saved_lot
try:
    excel_path, pdf_path = _run_export_pipeline(data, details_data)
    _notify_save_result(saved_lot, excel_path, pdf_path)
except (RuntimeError, OSError) as e:
    # 부분 성공 popup
```

기존 5개 단위 테스트(`test_manual_input_save_export.py`)로 D1(정상)/D2(Excel
실패)/D3(PDF 실패) 자동 회귀 감지.

---

## 5. Part C-0: `dhr_bulk_generator` 단위 테스트 보강

### 신규 테스트 파일: `tests/unit/test_dhr_bulk_generator.py`

| # | 케이스 | 검증 |
| --- | --- | --- |
| T1 | 빈 entries → 0 반환 | early return |
| T2 | 단일 entry, include_time=False, export=False | DB 1회 저장, export 미호출, work_time 빈 문자열 |
| T3 | 단일 entry, include_time=True (첫 날짜) | `_get_base_time_for_date` 호출, work_time 채워짐 |
| T4 | 동일 날짜 2개 entry, include_time=True | 두 번째는 last_time + 20~40분 증분 |
| T5 | LOT 누락된 자재 → ValueError | `_validate_material_lots_for_date` 실패 경로 |
| T6 | `_export_record` 정상 (mock Exporter 성공) | `last_export_failures` 비어 있음 |
| T7 | `_export_record` Excel 실패 | `last_export_failures`에 항목 추가, `RuntimeError` catch |
| T8 | `_export_record` PDF 실패 | `last_export_failures`에 항목 추가 |
| T9 | `_export_record` finally 임시 이미지 정리 | `os.remove` 호출 (signed 이미지 생성 성공 케이스) |

`dhr_db`, `lot_manager`는 `MagicMock`으로 주입. `ExcelExporter`/`ImageProcessor`는
`unittest.mock.patch`로 차단. random 고정(`random.seed` 또는 monkeypatch).

---

## 6. Part C-1: `dhr_bulk_generator.generate` (82줄)

원본 행 49–130.

| 헬퍼 | 시그니처 | 책임 |
| --- | --- | --- |
| `_collect_unique_dates(entries)` | `(List[Dict]) -> List[str]` | 유일 날짜 추출 (순서 보존) |
| `_build_lot_map_by_date(unique_dates, materials)` | `(dates, materials) -> Dict[str, Dict[str, str]]` | 날짜별 LOT 맵 (실패 시 ValueError) |
| `_resolve_work_time(product_name, work_date, last_time_by_date, include_time)` | `(...) -> str` | 작업시간 계산 + last_time_by_date 갱신 (in-place) |
| `_build_record_and_details(product_lot, product_name, worker, work_date, work_time, amount, materials, lot_map)` | `(...) -> Tuple[Dict, List[Dict]]` | record_data + details_data |

`generate` 오케스트레이터: validate → collect dates → lot map → loop(time → record/details → save → optional export → count) → return.

---

## 7. Part C-2: `dhr_bulk_generator._export_record` (70줄)

원본 행 132–201.

| 헬퍼 | 시그니처 | 책임 |
| --- | --- | --- |
| `_prepare_signed_image(worker, base_dir, signature_options)` | `(worker, base_dir, options) -> Tuple[Optional[str], Optional[str]]` | `(image_to_embed, signed_image_path)` 생성 또는 (None, None) |
| `_build_bulk_export_data(...)` | `(product_lot, product_name, worker, work_date, work_time, include_time, amount, details_data) -> Dict` | export_data 빌드 |
| `_run_bulk_export(exporter, export_data, scan_effects, include_time)` | `(exporter, data, effects, include_time) -> Tuple[str, str]` | Excel + PDF 실행 (각 실패 시 RuntimeError) |
| `_cleanup_signed_image(image_to_embed, signed_image_path)` | `(embed, path) -> None` | finally에서 호출, signed_image면 삭제 시도 |

`_export_record` 오케스트레이터: try (헬퍼 호출들) / except → failure 기록 / finally → cleanup.

---

## 8. 구현 순서

1. Part C-0: dhr_bulk_generator 테스트 9건 작성 (회귀 안전망 확보).
2. Part B-3: `_save_and_export` 헬퍼 추출 (기존 테스트로 즉시 검증).
3. Part B-1/B-2: `record_view_dialog` 두 `init_ui` (UI 빌더 패턴, 스모크).
4. Part C-1: `generate` 헬퍼 추출 (T1~T5로 검증).
5. Part C-2: `_export_record` 헬퍼 추출 (T6~T9로 검증).

각 단계 후 `py_compile` + 관련 테스트 실행.

---

## 9. 검증 (DoD — Plan 6장 확장)

- [ ] `grep -r RecipeManagerDialog v3` 0건 (Part A 검증, 이미 통과)
- [ ] 대상 메서드 4종 각 ≤40줄: `RecordDetailDialog.init_ui`, `RecordViewDialog.init_ui`, `_save_and_export`, `generate`, `_export_record`
- [ ] 모든 추출 헬퍼/빌더 ≤40줄
- [ ] `python tests/run_tests.py` — 기존 65건 + 신규 dhr_bulk_generator 9건 = **74건** 통과
- [ ] 위젯 스모크 — `RecordDetailDialog`/`RecordViewDialog` 생성 + 노출 위젯 검증

---

**작성일**: 2026-05-21
**버전**: 1.0
