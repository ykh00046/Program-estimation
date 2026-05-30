# RecordDetailDialog 복구 (PDCA #24)

> **Feature**: record_detail_dialog_fix
> **Author**: AI Assistant
> **Created**: 2026-05-31
> **Status**: ✅ Plan
> **PDCA Cycle**: #24 (PDCA #23 gap-detector 범위 외 관찰 → 실 버그로 확대)

---

## 1. 배경 — 단순 중복이 아닌 깨진 다이얼로그

PDCA #23에서 `RecordDetailDialog._build_button_bar` 중복 정의가 관찰됨. 조사 결과 더 심각한 **복사-붙여넣기 결함**:

- `RecordDetailDialog.init_ui`가 `RecordViewDialog`(목록)에서 복사된 `_build_filter_group`/`_build_records_table`/`_build_aggregation_group` + 첫 `_build_button_bar`를 호출.
- 본래 상세 위젯 `_build_info_group`/`_build_detail_group`은 **호출되지 않음**.
- `_build_button_bar` **2회 정의**(목록용 :103, 상세용 :196) → 두 번째만 유효, 첫 번째 죽은 코드.
- `_build_filter_group`가 `self.load_records`에 connect하지만 RecordDetailDialog엔 해당 메서드가 **없음**.

### 재현 (before)
```
RecordDetailDialog(df, dm, params)
→ AttributeError: 'RecordDetailDialog' object has no attribute 'load_records'
```
→ `show_detail`(record_view_dialog.py:584)의 `except Exception`이 "상세 정보를 표시하는 중 오류"로 흡수. **상세조회가 항상 실패**해 왔다.

추가 잠재 결함: `self.edit_mode`가 `__init__`에서 초기화되지 않아, 수정 버튼 클릭 시 `toggle_edit_mode`의 `not self.edit_mode`가 AttributeError.

## 2. 범위 (In Scope)

### Part A — init_ui 재배선 + 죽은 코드 제거
- `init_ui`: `_build_info_group()` + `_build_detail_group()` + `_build_button_bar()`(상세용) 호출로 교체.
- RecordDetailDialog에서 **복사된 목록용 메서드 삭제**: `_build_filter_group`, `_build_records_table`, `_build_aggregation_group`, 첫 `_build_button_bar`(:103).
- `__init__`에 `self.edit_mode = False` 초기화 추가.

### Part B — 테스트
- `RecordDetailDialog` 생성이 크래시 없이 성공(info/detail 위젯 존재) 검증.
- `toggle_edit_mode` 1회 호출이 크래시 없이 동작(edit_mode 토글).
- `_build_button_bar`가 1개만 남고 수정/저장/실적서/닫기 구성인지.
- 기존 `_collect_material_updates_from_rows`가 detail 테이블 컬럼(0/2/3/4/5)과 정합.

## 3. 비-범위 (Out of Scope)
- `RecordViewDialog`(목록) 변경 없음 — 정상 동작 중.
- 상세 다이얼로그의 신규 기능/레이아웃 디자인 변경(복구만).
- `save_changes`/`export_report` 로직 변경(이미 올바름, self.table만 올바른 테이블로 교정됨).

## 4. 성공 기준
- [ ] `RecordDetailDialog(df, dm, params)` 생성 크래시 0 (info+detail+수정/저장 바 렌더)
- [ ] `_build_button_bar` 단일 정의, 죽은 목록 메서드 제거
- [ ] `toggle_edit_mode`/`save_changes` 경로 크래시 0 (edit_mode 초기화)
- [ ] 전체 스위트 통과(현 136 + 신규) + 시각 스모크
- [ ] Match Rate ≥ 90%

## 5. 위험 & 완화
| 위험 | 완화 |
|---|---|
| init_ui 재배선이 self.table을 detail 테이블로 바꿔 save 경로 영향 | _collect_material_updates_from_rows 컬럼(0/2/3/4/5)이 detail 헤더와 일치 확인 + 스모크 |
| 삭제한 메서드를 다른 곳이 참조 | RecordDetailDialog 내부 전용(목록은 RecordViewDialog가 별도 보유) — grep 확인 |
| QMessageBox 모달(수정모드 안내) 스모크 블록 | 스모크에서 QMessageBox patch |

## 6. 커밋 계획
1. `fix(ui): repair RecordDetailDialog to render info/detail widgets (PDCA #24)` — init_ui 재배선 + 죽은 메서드 삭제 + edit_mode 초기화
2. `test: RecordDetailDialog construction + edit toggle smoke (PDCA #24)`
3. `docs: PDCA #24 analysis + report`

## 7. 다음 단계
`/pdca design record_detail_dialog_fix` → init_ui 최종형/삭제 목록 확정 → `/pdca do`.
