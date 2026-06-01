# PDCA #30 Design — inventory_inbound_history

> 선행 Plan: `docs/01-plan/features/inventory_inbound_history.plan.md`
> 무동작 보존 대상: PDCA #27(임계값 알림), #29(자동 차감) 공개 API·동작

## 1. 데이터 모델

### 1.1 신규 테이블 `material_stock_history` (append-only 이동 로그)

```sql
CREATE TABLE IF NOT EXISTS material_stock_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    material_code TEXT NOT NULL,
    material_name TEXT NOT NULL DEFAULT '',
    change_type  TEXT NOT NULL,            -- 'INBOUND' | 'CONSUME' | 'ADJUST'(예약)
    quantity     REAL NOT NULL,            -- 부호 있는 델타: 입고 +, 차감 -
    stock_after  REAL NOT NULL DEFAULT 0,  -- 이동 직후 current_stock 스냅샷
    unit         TEXT NOT NULL DEFAULT 'g',
    note         TEXT NOT NULL DEFAULT '',
    created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_stock_history_code ON material_stock_history(material_code);
CREATE INDEX IF NOT EXISTS idx_stock_history_created ON material_stock_history(created_at);
```

- `database.py::_create_tables`의 `material_stock` 생성 블록 **직후**에 추가(같은 트랜잭션). `CREATE TABLE IF NOT EXISTS`라 기존 DB도 다음 기동 시 자동 마이그레이션.
- 마스터(`material_stock`)=현재 상태 SSOT, 이력=불변 로그. 외래키는 두지 않음(자재 삭제 기능 없음 + 이력은 코드 사라져도 보존).

### 1.2 이동 유형 상수 (`material_stock_repository.py` 모듈 상수)

```python
MOVE_INBOUND = "INBOUND"   # 입고/매입 (+)
MOVE_CONSUME = "CONSUME"   # 배합 차감 (-)
MOVE_ADJUST  = "ADJUST"    # 수동 조정 (예약, 이번 미사용)
```

## 2. Repository (`MaterialStockRepository`) 변경

### 2.1 신규 `add_inbound`

```python
@handle_exceptions(user_message="입고 등록 중 오류가 발생했습니다.", default_return=False)
def add_inbound(self, material_code, material_name, quantity,
                unit="g", note="") -> bool:
    """입고(매입): 기존 재고에 수량을 더한다. 마스터에 없으면 신규 생성.
    이동 이력(INBOUND, +quantity, stock_after)을 동일 트랜잭션에 기록."""
```

동작:
- `code = (material_code or material_name or "").strip()` — 비면 False(경고 로그).
- `qty = float(quantity or 0)`; `qty <= 0`이면 False(입고는 양수만).
- 단일 트랜잭션:
  1. `INSERT ... ON CONFLICT(material_code) DO UPDATE SET current_stock = current_stock + excluded.current_stock, material_name=excluded..., unit=excluded..., updated_at=CURRENT_TIMESTAMP`
     (신규 시 `current_stock=qty, min_stock_threshold=0`; 기존 시 누적 가산)
  2. `SELECT current_stock FROM material_stock WHERE material_code=?` → `stock_after`
  3. `_insert_history(conn, code, name, MOVE_INBOUND, +qty, stock_after, unit, note)`
  4. `conn.commit()`
- 반환 True.

> 주의: ON CONFLICT의 `current_stock = current_stock + excluded.current_stock`는 누적 가산이라 #27 `upsert_material_stock`(절대값 설정)과 **의도적으로 다른** 별도 메서드다. upsert는 변경하지 않는다.

### 2.2 신규 `get_stock_history`

```python
@handle_exceptions(..., default_return=[])
def get_stock_history(self, material_code=None, limit=200) -> List[Dict]:
    """이동 이력 최신순. material_code 지정 시 해당 자재만."""
```
- `SELECT material_code, material_name, change_type, quantity, stock_after, unit, note, created_at FROM material_stock_history [WHERE material_code=?] ORDER BY created_at DESC, id DESC LIMIT ?`
- dict 리스트 반환.

### 2.3 신규 private `_insert_history`

```python
@staticmethod
def _insert_history(conn, code, name, change_type, quantity, stock_after, unit, note) -> None:
    conn.execute(
        "INSERT INTO material_stock_history "
        "(material_code, material_name, change_type, quantity, stock_after, unit, note) "
        "VALUES (?,?,?,?,?,?,?)",
        [code, name or code, change_type, float(quantity), float(stock_after), unit or "g", note or ""],
    )
```
- 커밋은 호출자(메인 메서드) 책임 — PDCA 교훈(트랜잭션 경계는 호출자 잔존).

### 2.4 `apply_consumption` 확장 (#29 무회귀 가산)

기존 로직(코드별 합산 → `UPDATE ... MAX(0, current-amt)` → `updated += rowcount`)을 **그대로 유지**하고, 각 자재 UPDATE 직후 **rowcount > 0일 때만** CONSUME 이력을 추가한다:

```python
for code, amount in totals.items():
    cursor = conn.execute("UPDATE material_stock SET current_stock = MAX(0, current_stock - ?), "
                          "updated_at=CURRENT_TIMESTAMP WHERE material_code = ?", [amount, code])
    if cursor.rowcount:
        updated += cursor.rowcount
        after_row = conn.execute("SELECT current_stock, material_name, unit FROM material_stock "
                                 "WHERE material_code=?", [code]).fetchone()
        stock_after = float(after_row["current_stock"]) if after_row else 0.0
        name = after_row["material_name"] if after_row else code
        unit = after_row["unit"] if after_row else "g"
        self._insert_history(conn, code, name, MOVE_CONSUME, -amount, stock_after, unit, "배합 자동 차감")
conn.commit()
```

- **반환값(`updated`) 불변** → #29 단위/통합 테스트 회귀 0.
- 이력 기록은 차감과 동일 트랜잭션 → 원자성 보장(차감 커밋 ⇔ 이력 커밋).

## 3. Facade (`database.py`) 위임 추가

```python
def add_inbound(self, material_code, material_name, quantity, unit="g", note=""):
    return self._stock.add_inbound(material_code, material_name, quantity, unit, note)

def get_stock_history(self, material_code=None, limit=200):
    return self._stock.get_stock_history(material_code, limit)
```
(무데코 passthrough — PDCA #28 패턴)

## 4. DataManager (`data_manager.py`) 위임 추가

자재 재고 섹션(line 485~)에 추가:

```python
def add_inbound(self, material_code, material_name, quantity, unit="g", note="") -> bool:
    return self.db_manager.add_inbound(material_code, material_name, quantity, unit, note)

def get_stock_history(self, material_code=None, limit=200) -> List[Dict]:
    return self.db_manager.get_stock_history(material_code, limit)
```

## 5. UI

### 5.1 `StockSettingsDialog` 버튼 추가

`_build_button_row`의 `reseed_btn` 옆(좌측 그룹)에 2개 추가:
- `inbound_btn = QPushButton("입고 등록")` → `_open_inbound` (secondary 스타일)
- `history_btn = QPushButton("입출고 이력")` → `_open_history` (secondary 스타일)

핸들러:
```python
def _open_inbound(self):
    from ui.dialogs.inbound_dialog import InboundDialog
    if InboundDialog(self.data_manager, self).exec():
        self._reload_after_change()   # seed 없이 재고 재조회 → 테이블 갱신

def _open_history(self):
    from ui.dialogs.stock_history_dialog import StockHistoryDialog
    StockHistoryDialog(self.data_manager, self).exec()
```
- `_reload_after_change`: `rows = get_all_material_stock(); self._fill_table(rows)` (seed 재호출 회피 — 입고로 생성된 신규 자재 포함됨).

### 5.2 `InboundDialog` (신규, `ui/dialogs/inbound_dialog.py`)

- 입력: **자재 선택 콤보**(`get_all_material_stock` 자재명/코드, editable 콤보로 신규 코드 직접 입력 허용) + 자재명 입력 + 수량(`QLineEdit`+`QDoubleValidator(0, 1e12, 3)`) + 단위(기본 'g') + 메모(`QLineEdit`).
- "등록" 클릭 → 수량 ≤ 0 또는 코드 공백이면 `QMessageBox.warning` 후 return.
  성공 시 `data_manager.add_inbound(...)` → True면 `QMessageBox.information("등록 완료")` 후 `accept()`, False면 warning.
- 콤보 선택 시 코드/단위 자동 채움(기존 자재). 표현/입력만, 영속화는 DataManager 위임.
- 스타일: `UIStyles.get_dialog_style/get_input_field_style/get_primary_button_style` 재사용(try/except 가드).

### 5.3 `StockHistoryDialog` (신규, `ui/dialogs/stock_history_dialog.py`)

- 상단: 자재 필터 콤보("전체" + 자재 목록) + 새로고침 버튼.
- 테이블 6열: 일시 / 자재명 / 유형 / 증감 / 이동후 재고 / 메모.
  - 유형 표기: INBOUND→"입고", CONSUME→"차감", ADJUST→"조정".
  - 증감: `+`/`-` 부호 + 색(입고=primary/green 계열 `UITheme`, 차감=warning/red). `UITheme` 기존 토큰만 사용(민트/틸 금지).
- 데이터: `data_manager.get_stock_history(code_or_None, limit=200)`.
- 읽기 전용(QMessageBox 등 모달 없음 → 스모크 단순).

## 6. 테스트 설계

| 파일 | 케이스 |
|---|---|
| `tests/unit/test_stock_inbound_history.py` (신규) | ① add_inbound 신규 생성(+stock, 이력 1건 INBOUND, stock_after 일치) ② add_inbound 기존 누적 가산 ③ 0/음수·빈코드 거부(False, 이력 0) ④ get_stock_history 최신순/자재필터 ⑤ apply_consumption 후 CONSUME 이력 + 부호(-) + stock_after, 반환 updated 불변 ⑥ 마스터에 없는 자재 차감 시 이력 미기록 |
| `tests/unit/test_data_manager_inbound.py` (또는 기존 확장) | DataManager.add_inbound/get_stock_history가 db_manager로 위임(실 tmp DB) |
| `tests/integration` 또는 스모크 | InboundDialog/StockHistoryDialog offscreen 구동 + QMessageBox patch, 등록 1건이 이력에 반영 |

- DB 단위 테스트는 `LEGACY_DB_PATH` 패치 + `MixingDatabaseManager(tmp)` (PDCA 교훈).
- 모달 스모크는 offscreen 가드 + `QMessageBox` patch (PDCA #20/#23).

## 7. 무회귀 보증 포인트

1. `material_stock`·`upsert_material_stock`·`get_low_stock_materials`·`evaluate_inventory_alerts` **불변**.
2. `apply_consumption` 반환 계약(updated count) **불변** — 이력은 순수 가산.
3. `_create_tables`는 신규 `CREATE TABLE/INDEX IF NOT EXISTS`만 추가 — 기존 테이블 정의 무변경.
4. 신규 공개 메서드만 추가(시그니처 변경 0).
