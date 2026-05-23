# database_save_refactor — Design

> **PDCA #16**
> **Author**: AI Assistant
> **Created**: 2026-05-23
> **Status**: 🔄 In Progress
> **Plan**: [`database_save_refactor.plan.md`](../../01-plan/features/database_save_refactor.plan.md)

---

## 1. 설계 원칙

- **Behavior-preserving**: public 시그니처(이름·인자·반환·예외)와 외부에서 관측 가능한 부작용(DB 쓰기, 로그, 다이얼로그, 시그널, UI 상태)을 보존.
- **단일 책임**: 추출된 헬퍼는 한 가지 책임만 가진다(쿼리 실행 / 데이터 수집 / UI 상태 복원).
- **테스트 가능성**: 가능하면 외부 의존(DB·Qt 위젯)이 없는 **순수 변환부**를 별도 헬퍼로 분리하여 단위 테스트화.

---

## 2. `database.save_mixing_record` 분해

### 현재(57 LOC)

```
with get_connection():
    INSERT INTO mixing_records  ← 메인 행
    record_id = cursor.lastrowid
    for detail in details:
        INSERT INTO mixing_details
    commit
    log_mixing_operation
return record_id
```

### After (메인 ≤ 15줄)

```python
def save_mixing_record(self, record_data: Dict, details: List[Dict]) -> int:
    """배합 기록을 저장합니다. (시그니처 동일)"""
    with self.get_connection() as conn:
        record_id = self._insert_mixing_record_row(conn, record_data)
        self._insert_mixing_detail_rows(conn, record_id, details)
        conn.commit()
        self._log_record_saved(record_data, record_id)
    return record_id
```

### 신규 헬퍼

| 헬퍼 | 입력 | 반환 | 책임 |
| --- | --- | --- | --- |
| `_insert_mixing_record_row(conn, record_data) -> int` | sqlite3 connection, record dict | `lastrowid` | `mixing_records` 단일 INSERT |
| `_insert_mixing_detail_rows(conn, record_id, details) -> None` | conn, FK, detail list | — | `mixing_details` N건 INSERT |
| `_log_record_saved(record_data, record_id) -> None` | record dict, FK | — | `logger.log_mixing_operation` 호출 |

가시성: 모두 **`_` 접두 인스턴스 메서드** (외부 노출 안 함, 단 테스트에서는 접근 가능).

### 데이터 무결성

- `_insert_mixing_record_row`는 connection을 인자로 받아 **트랜잭션 경계는 호출자(메인)** 가 관리. commit/rollback 책임 분산 금지.
- 예외 발생 시 with 블록의 connection.close()와 sqlite3 rollback 동작은 기존과 동일하게 유지.

---

## 3. `record_view_dialog.save_changes` 분해

### 현재(64 LOC)

```
1. 확인 다이얼로그 (Yes/No)
2. try:
     form 수집 (product_lot, worker, amount, materials_updates from table)
     data_manager.update_record(...)
     if success:
         info dialog + logger.info
         편집모드 종료 (edit_mode=False, 버튼 텍스트, ReadOnly, 스타일)
         lot_data 새로고침
     else:
         warning dialog
   except ValueError: warning
   except Exception: error log + critical dialog
```

### After (메인 ≤ 20줄)

```python
def save_changes(self):
    """변경 사항 저장 (시그니처 동일)"""
    if not self._confirm_save_changes():
        return
    try:
        form = self._collect_edit_form()
        success = self.data_manager.update_record(
            product_lot=form['product_lot'],
            worker=form['worker'],
            total_amount=form['amount'],
            materials=form['materials'],
        )
        self._handle_update_result(success, form['product_lot'])
    except ValueError as e:
        QMessageBox.warning(self, "입력 오류", f"숫자 형식이 올바르지 않습니다.\n{e}")
    except Exception as e:
        logger.error(f"기록 수정 오류: {e}")
        QMessageBox.critical(self, "오류", f"기록 수정 중 오류가 발생했습니다.\n{e}")
```

### 신규 헬퍼

| 헬퍼 | 책임 | 외부 의존 | 단위 테스트 |
| --- | --- | --- | --- |
| `_confirm_save_changes() -> bool` | 확인 다이얼로그, Yes만 True | QMessageBox | 어려움 (UI) |
| `_collect_edit_form() -> Dict` | `{product_lot, worker, amount, materials}` 수집 | QTableWidget, QLineEdit | 어려움 (Qt) |
| `_collect_material_updates_from_rows(rows) -> List[Dict]` **(staticmethod)** | 행 raw 데이터(List[List[str]]) → materials dict 리스트 | 없음 | **가능** |
| `_handle_update_result(success, product_lot)` | 성공/실패 분기, 다이얼로그+UI 상태 복원+데이터 새로고침 | Qt | 어려움 |
| `_exit_edit_mode()` | edit_mode=False, 버튼 텍스트, ReadOnly, 스타일 복원 | Qt | 어려움 |
| `_refresh_lot_data(product_lot)` | `self.lot_data` 갱신 | data_manager | 어려움 |

`_collect_edit_form`은 내부에서 다음과 같이 staticmethod를 활용:

```python
def _collect_edit_form(self) -> Dict:
    rows = [
        [self.table.item(r, c).text() if self.table.item(r, c) else ""
         for c in range(self.table.columnCount())]
        for r in range(self.table.rowCount())
    ]
    return {
        'product_lot': self.lot_data.iloc[0]['product_lot'],
        'worker': self.worker_edit.text().strip(),
        'amount': float(self.amount_edit.text().strip()),
        'materials': self._collect_material_updates_from_rows(rows),
    }
```

→ 이 분리로 **`_collect_material_updates_from_rows`** 는 순수 함수가 되어 단위 테스트 가능.

---

## 4. 테스트 전략

### 4.1 회귀 (기존 테스트)

- `tests/unit/test_data_manager.py` — `save_record` 경로를 통해 `save_mixing_record` 간접 커버.
- `tests/integration/test_data_integration.py` — 종단 데이터 흐름 검증.
- `tests/test_normal_blend.py` — 정상 배합 시나리오.

### 4.2 신규 (Part C, save_changes 안전망)

`tests/unit/test_record_view_dialog_helpers.py` 신설:

- `test_collect_material_updates_basic`: 6개 컬럼 행 3개 → dict 3개, 타입(float) 변환 확인.
- `test_collect_material_updates_empty_strings`: ratio/theory/actual이 ""이면 0.0으로.
- `test_collect_material_updates_empty_rows`: 빈 리스트 → 빈 리스트.

→ Qt 의존 없이 staticmethod 만 import 해서 검증.

---

## 5. 구현 순서

1. **Part A**: `database.save_mixing_record` 분해 → 기존 테스트 통과 확인 → 커밋.
2. **Part B**: `record_view_dialog.save_changes` 분해 (헬퍼 추출만, 동작 보존) → 기존 테스트 통과 확인 → 커밋.
3. **Part C**: `_collect_material_updates_from_rows` 단위 테스트 신설 → 커밋.

각 Part는 독립 커밋(저위험 일괄 진행 정책 적용).

---

## 6. 검증 체크리스트

- [ ] `save_mixing_record` 메인 본문 ≤ 20줄 (코드 라인 기준).
- [ ] `save_changes` 메인 본문 ≤ 20줄.
- [ ] `python -m pytest v3/tests/unit/test_data_manager.py v3/tests/integration` 통과.
- [ ] 신규 `test_record_view_dialog_helpers.py` 통과.
- [ ] Public 시그니처/예외 동일 (diff로 확인).
