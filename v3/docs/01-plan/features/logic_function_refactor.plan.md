# 로직 함수 리팩토링 + 데드 코드 정리 계획서 (PDCA #15)

> **Feature**: logic_function_refactor
> **Summary**: `improvement.plan.md #9` 잔여 — 데드 파일 1개 삭제 + 라이브 긴 함수 3종 분해
> **Author**: AI Assistant
> **Created**: 2026-05-21
> **Status**: ✅ Plan 승인됨 (2026-05-21, 확장 범위: dhr_bulk_generator 포함)
> **PDCA Cycle**: #15 (결합 — 데드 정리 + 라이브 리팩토링)

---

## 1. 배경

`improvement.plan.md` 마지막 잔여 항목 #9(긴 함수 리팩토링) 착수.
PDCA #14 교훈을 적용해 **사용처 사전 검증**을 먼저 수행했고, 두 가지가 드러났다:

1. `ui/recipe_manager_dialog.py`(`RecipeManagerDialog`)가 **데드 코드**
   — 후보 함수 중 가장 큰 둘(`init_ui` 91 / `save_to_excel` 94)이 여기 있음.
2. 라이브 후보 중 절반은 테스트 미보유 → 모두 한 사이클에 욱여넣지 않고
   **테스트 있는 / UI 빌더 패턴 / 간접 보장**된 것만 #15 범위로 한정.

---

## 2. 범위

### Part A — 데드 파일 삭제 (`#14` 패턴 반복)

| 파일 | 처리 |
| --- | --- |
| `ui/recipe_manager_dialog.py` | **삭제** (≈510줄, 외부 참조 0) |

### Part B — 라이브 로직/UI 빌더 분해

| 대상 | LOC | 분류 | 안전장치 |
| --- | --- | --- | --- |
| `record_view_dialog.py::RecordDetailDialog.init_ui` | 89 | UI 빌더 (#13 패턴) | 위젯 스모크 |
| `record_view_dialog.py::RecordViewDialog.init_ui` | 88 | UI 빌더 (#13 패턴) | 위젯 스모크 |
| `manual_input_interface.py::_save_and_export` | 82 | 로직 분기 | ✅ 단위 테스트 보유 (`test_manual_input_save_export.py`) |

### Part C — dhr_bulk_generator (테스트 보강 선행)

확장 범위 추가. 테스트 0건이므로 **리팩토링 전에 단위 테스트를 먼저 추가**.

| 대상 | LOC | 작업 |
| --- | --- | --- |
| `dhr_bulk_generator.generate` | 82 | 단위 테스트 보강 → 헬퍼 추출 |
| `dhr_bulk_generator._export_record` | 70 | 단위 테스트 보강 → 헬퍼 추출 |

### 이연 (PDCA #16 후보)

| 함수 | LOC | 이연 사유 |
| --- | --- | --- |
| `record_view_dialog.save_changes` | 64 | 단위 테스트 0건, #15 범위 초과 |
| `database.save_mixing_record` | 57 | 간접 커버리지(via data_manager), #15 범위 초과 |

---

## 3. 목표 (Goals)

- 각 대상 메서드 ≤40줄.
- **동작 0 변경** — 위젯 트리·시그널·DB 호출 인자 동일.
- 65개 단위 테스트 + 위젯 스모크 통과 유지.
- 코드베이스 −510줄 + 리팩토링 분량.

### 비목표

- 이연 항목 — #16에서 처리.
- 사용 패턴/API 변경 — 순수 Extract Method 범위.

---

## 4. 접근

### Part A
`#14`와 동일: `git rm` 후 `grep` 잔존 0건·테스트·import 스모크.

### Part B (UI 빌더 2종)
`#13` 패턴: `init_ui` → 얇은 오케스트레이터 + `_build_*` 섹션 빌더.
`self.` 노출 위젯 목록을 Design에서 명시. 위젯 생성 스모크로 노출 위젯 누락 검증.

### Part B (`_save_and_export`)
`_save_and_export`의 책임을 단계별 헬퍼로 추출:
- `_collect_export_inputs() -> tuple[record_data, details_data]`
- `_persist_dhr_record(record_data, details_data) -> Optional[str]`
- `_run_export_pipeline(export_data, effects_params, include_time) -> tuple[excel_path, pdf_path]`
- `_show_save_result(lot, excel_path, pdf_path)`

`_save_and_export`는 오케스트레이션만 수행, 각 헬퍼 ≤40줄. 기존 테스트로
DB 실패·Excel 실패·PDF 실패 경로 회귀 감지.

---

## 5. 리스크 / 대응

| 리스크 | 수준 | 대응 |
| --- | --- | --- |
| `record_view_dialog` 테스트 부재 | 중 | UI 빌더 패턴(분기 0)이라 #13 동일 안전장치(스모크) 적용 |
| `_save_and_export` 분기 손상 | 중 | 기존 5건 단위 테스트로 D1/D2/D3 회귀 자동 감지 |
| 데드 파일 삭제 회귀 | 저 | `#14`와 동일 검증(grep·테스트·import 스모크) |

---

## 6. 검증 기준 (DoD)

- [ ] `grep -r RecipeManagerDialog v3` — 잔존 0건
- [ ] 대상 메서드 4종 각 ≤40줄
- [ ] 추출 헬퍼/빌더 각 ≤40줄
- [ ] `python tests/run_tests.py` 65/65 통과
- [ ] 위젯 스모크 — `RecordDetailDialog`/`RecordViewDialog` 생성·노출 위젯 확인

---

## 7. 단계

확장 범위로 단계 분할:

1. **Part A** 즉시 처리 (저위험 데드 삭제, `#14` 패턴).
2. **체크포인트** — Part B/C는 분량 크므로 사용자 승인 후 진행.
3. Part C 테스트 보강 → Part C 리팩토링.
4. Part B UI 빌더 분해 + `_save_and_export` 헬퍼 추출.
5. Analyze → Report → Archive.

---

**작성일**: 2026-05-21
