# RecordDetailDialog 복구 설계서 (PDCA #24)

> **Feature**: record_detail_dialog_fix
> **Plan**: [../../01-plan/features/record_detail_dialog_fix.plan.md](../../01-plan/features/record_detail_dialog_fix.plan.md)
> **Author**: AI Assistant
> **Created**: 2026-05-31
> **Status**: 🔄 Design
> **PDCA Cycle**: #24

---

## 1. 설계 원칙
- **복구 only**: 본래 의도(기본정보 + 자재상세 + 수정/저장 바)로 되돌림. 신규 레이아웃/기능 없음.
- **죽은/오배선 코드 제거**: RecordViewDialog에서 복사된 목록용 메서드 삭제.
- **기존 정상 메서드 보존**: `_build_info_group`/`_build_detail_group`/상세용 `_build_button_bar`/`toggle_edit_mode`/`save_changes`/`export_report` 등은 유지.
- **Python 3.9.**

## 2. 변경 (`ui/record_view_dialog.py`, RecordDetailDialog만)

### 2.1 `__init__` — edit_mode 초기화
```python
self.parent_dialog = parent
self.edit_mode = False          # toggle_edit_mode가 참조 (신규 초기화)
self.setWindowTitle(...)
```

### 2.2 `init_ui` — 상세 위젯으로 재배선
```python
def init_ui(self):
    """UI 초기화 (기본정보 + 자재상세 + 수정/저장 바)."""
    layout = QVBoxLayout()
    layout.addWidget(self._build_info_group())
    layout.addWidget(self._build_detail_group())
    layout.addLayout(self._build_button_bar())
    self.setLayout(layout)
```

### 2.3 삭제 (RecordDetailDialog 내 복사-붙여넣기 잔재)
- `_build_filter_group` (목록 검색필터)
- `_build_records_table` (목록 6열 테이블 — self.table 잘못 생성)
- `_build_aggregation_group` (목록 집계)
- 첫 번째 `_build_button_bar` (목록용 전체선택/출력/삭제 — 두 번째에 의해 이미 죽은 코드)

> 삭제 후 `self.table`은 `_build_detail_group`가 생성하는 자재상세 테이블(품목코드/품목명/자재LOT/배합비율/이론계량/실제배합)이 됨. `_collect_material_updates_from_rows`의 인덱스(0=code,2=lot,3=ratio,4=theory,5=actual)와 정합.

### 2.4 보존 확인
- `_build_button_bar`(상세용): 수정모드/저장/실적서출력/닫기 → `toggle_edit_mode`/`save_changes`/`export_report`/`close`.
- `save_changes`→`_collect_edit_form`→`self.worker_edit`/`self.amount_edit`(info_group 생성)/`self.table`(detail_group 생성).

## 3. 참조 안전성
- 삭제 메서드는 RecordDetailDialog 전용(목록 기능은 RecordViewDialog가 자체 보유). grep으로 외부 참조 0 확인.
- RecordViewDialog는 변경 없음.

## 4. 테스트 설계

### 4.1 `tests/integration/test_record_detail_dialog_smoke.py` (신설, offscreen)
- `test_constructs_without_crash`: `RecordDetailDialog(df, dm, params)` 생성 성공 + `worker_edit`/`amount_edit`/`table` 존재 + `edit_mode is False`.
- `test_single_button_bar_is_detail_variant`: 닫기 외 수정/저장/실적서 버튼 구성(목록용 전체선택/삭제 버튼 부재) — 위젯 텍스트로 확인.
- `test_toggle_edit_mode_no_crash`: QMessageBox patch 후 `toggle_edit_mode()` 호출 → `edit_mode True`, 위젯 ReadOnly 해제.
- `test_detail_table_columns`: self.table 헤더가 자재상세 6열인지.

### 4.2 회귀
- 기존 `test_record_view_dialog_helpers`(_collect_material_updates_from_rows) 통과 유지.
- 전체 스위트 통과(현 136 + 신규).

## 5. 위험 재확인
| 위험 | 결정 |
|---|---|
| self.table 의미 변경(목록→상세) | save 경로 컬럼 인덱스 정합 확인 + 스모크 |
| edit_mode 미초기화 잔존 | __init__에서 False 초기화 |
| 삭제 메서드 외부 참조 | grep 0 확인 후 삭제 |

## 6. 커밋 계획
1. `fix(ui): repair RecordDetailDialog to render info/detail widgets (PDCA #24)`
2. `test: RecordDetailDialog construction + edit toggle smoke (PDCA #24)`
3. `docs: PDCA #24 analysis + report`

## 7. 다음 단계
`/pdca do record_detail_dialog_fix` — 구현 후 전체 스위트 + 시각 스모크.
