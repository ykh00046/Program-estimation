# PDCA #32 Design — purchase_order_management

> 선행 Plan: `docs/01-plan/features/purchase_order_management.plan.md` · 2026-06-02

## 1. 데이터 모델

### 신규 테이블 `purchase_orders` (발주 헤더, 단일 자재 라인)

```sql
CREATE TABLE IF NOT EXISTS purchase_orders (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    po_number       TEXT    NOT NULL,                 -- PO-YYYYMMDD-NNN (당일 순번)
    material_code   TEXT    NOT NULL,
    material_name   TEXT    NOT NULL DEFAULT '',
    supplier        TEXT    NOT NULL DEFAULT '',       -- 매입처(자유 텍스트)
    ordered_qty     REAL    NOT NULL,                  -- 발주량 (> 0)
    received_qty    REAL    NOT NULL DEFAULT 0,        -- 누적 입고량
    unit            TEXT    NOT NULL DEFAULT 'g',
    status          TEXT    NOT NULL DEFAULT 'PENDING',-- PENDING/PARTIAL/RECEIVED/CANCELLED
    note            TEXT    NOT NULL DEFAULT '',
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_po_status  ON purchase_orders(status);
CREATE INDEX IF NOT EXISTS idx_po_created ON purchase_orders(created_at);
CREATE INDEX IF NOT EXISTS idx_po_code    ON purchase_orders(material_code);
```

- **외래키 없음** — `material_stock`과 느슨한 결합(자재 마스터 없이도 발주 가능, 입고 시 자동 생성).
  #30의 "이력은 코드 사라져도 보존" 원칙 계승.
- `material_stock_history`는 그대로 사용(발주 입고도 INBOUND 이력으로 기록, note에 발주번호 포함).

### 상태 전이

```
            create                    receive(부분)              receive(잔량 0)
   (없음) ───────────▶ PENDING ──────────────▶ PARTIAL ──────────────▶ RECEIVED
                          │                       │
                          └──────── cancel ───────┴─────────▶ CANCELLED
   (RECEIVED / CANCELLED 에서는 receive·cancel 불가)
```

전이 규칙(잔량 = ordered_qty − received_qty, 입고 후 재계산):
- `received_qty <= 0`            → PENDING
- `0 < received_qty < ordered`   → PARTIAL
- `received_qty >= ordered`      → RECEIVED (초과입고 허용, 상태는 RECEIVED 고정)

## 2. Repository 설계

### 2.1 `MaterialStockRepository` 확장 (material_stock_repository.py)

```python
def _apply_inbound(self, conn, material_code, material_name, quantity, unit, note) -> float:
    """주어진 conn(트랜잭션)에서 재고 누적 가산 + INBOUND 이력 기록. 커밋은 호출자 책임.
    반환: 이동 후 재고(stock_after). 사전조건: code 비어있지 않음, quantity > 0 (호출자 검증)."""
    # 기존 add_inbound 내부의 UPSERT + _insert_history 로직을 그대로 이동

def add_inbound(self, material_code, material_name, quantity, unit='g', note='') -> bool:
    # 검증(코드/수량) 동일 → with get_connection() as conn: self._apply_inbound(...) ; conn.commit()
    # 반환·로그 #30과 비트-동일

def apply_replenishment(self, material_code, material_name, quantity, unit='g', note='') -> bool:
    """add_inbound의 공개 별칭(재고 보충). 사용자 요청 명칭(PDCA #32 R3)."""
    return self.add_inbound(material_code, material_name, quantity, unit, note)
```

리팩토링 안전성: `add_inbound`의 외부 계약(검증·반환 True/False·로그·INBOUND 이력)을 유지하고
내부 SQL만 `_apply_inbound`로 추출. #30 `StockInboundHistoryTests`가 회귀 가드.

### 2.2 신규 `PurchaseOrderRepository(SqliteManagerBase)` (purchase_order_repository.py)

생성자에 `MaterialStockRepository` 주입(입고 연동 시 `_apply_inbound` 재사용):

```python
PO_PENDING, PO_PARTIAL, PO_RECEIVED, PO_CANCELLED = "PENDING","PARTIAL","RECEIVED","CANCELLED"

class PurchaseOrderRepository(SqliteManagerBase):
    def __init__(self, db_path, stock_repo):
        super().__init__(db_path, log_prefix="데이터베이스")
        self._stock = stock_repo

    def create_purchase_order(self, material_code, material_name, supplier,
                              ordered_qty, unit='g', note='') -> Optional[int]:
        """발주 생성. 코드 공백/발주량<=0 이면 None. 성공 시 PO id. po_number 자동 채번."""

    def get_purchase_orders(self, status=None, limit=200) -> List[Dict]:
        """최신순 발주 목록. status 지정 시 해당 상태만. 각 dict에 remaining_qty 포함."""

    def receive_purchase_order(self, po_id, received_qty=None, note='') -> bool:
        """발주 입고 처리. received_qty=None이면 잔량 전체.
        단일 conn 트랜잭션: PO행 SELECT(검증) → received_qty 갱신·status 재계산 UPDATE
        → self._stock._apply_inbound(conn, ...) (재고 가산 + INBOUND 이력) → commit.
        RECEIVED/CANCELLED 또는 입고량<=0 이면 False."""

    def cancel_purchase_order(self, po_id) -> bool:
        """PENDING/PARTIAL → CANCELLED. RECEIVED/CANCELLED이면 False. 재고 원복 없음."""
```

#### 채번 (`_next_po_number`, 같은 conn 내)
```
오늘 날짜 D = datetime.now().strftime('%Y%m%d')   # 런타임 코드라 datetime 사용 가능
seq = SELECT COUNT(*) FROM purchase_orders WHERE po_number LIKE 'PO-D-%'  + 1
po_number = f"PO-{D}-{seq:03d}"
```

#### receive 트랜잭션 경계 (Plan R2 / #30 교훈 3)
"발주 입고 처리 ↔ 재고 가산 ↔ INBOUND 이력" = **동일 트랜잭션**(입고는 발주 입고의 일부, 함께 커밋).
입고 메모 = `note or f"발주 {po_number} 입고"`. `_apply_inbound`는 커밋하지 않으므로 PO UPDATE와
같은 conn에서 호출 후 마지막에 한 번 commit → 원자성 확보.

### 2.3 Facade(database.py) / DataManager 위임

`database.py.__init__`: `self._po = PurchaseOrderRepository(self.db_path, self._stock)` (self._stock 이후).
`_create_tables`에 `purchase_orders` DDL + 인덱스 3개 추가.

Facade 위임 메서드(자재 재고 섹션 아래):
`apply_replenishment`, `create_purchase_order`, `get_purchase_orders`,
`receive_purchase_order`, `cancel_purchase_order`.

`DataManager`도 동일 시그니처로 `self.db_manager.*` 위임(입고 섹션 근처 #30 패턴).

## 3. UI 설계

### 3.1 `PurchaseOrderDialog` (신규, ui/dialogs/purchase_order_dialog.py) — 발주 관리 허브
- 제목 + 상태 필터 콤보(전체/대기/부분입고/입고완료/취소) + "새로고침".
- 발주 목록 테이블 7열: 발주번호 / 자재 / 매입처 / 발주량 / 입고량 / 잔량 / 상태. 읽기 전용.
  상태별 색상: PENDING=TEXT_SECONDARY, PARTIAL=WARNING_COLOR(앰버), RECEIVED=SUCCESS_COLOR, CANCELLED=ERROR_COLOR.
- 버튼 행: "신규 발주"(→ `_NewOrderDialog`), "입고 처리"(선택 행), "발주 취소"(선택 행), 우측 "닫기".
- 입력/표시만 담당, 영속화는 `data_manager`에 위임(#30 다이얼로그 패턴 준수).

### 3.2 `_NewOrderDialog` (같은 파일 내 보조 모달) — 신규 발주 입력
- 자재 콤보(editable, 기존 재고 목록 + 빈 항목, 선택 시 자재명/단위 자동 채움 — InboundDialog 패턴 재사용),
  자재명, 매입처, 발주량(QDoubleValidator), 단위, 메모. "등록/취소".
- 검증: 코드 공백·발주량<=0 → QMessageBox.warning 후 유지.

### 3.3 입고 처리 흐름
- 목록에서 행 선택 → "입고 처리" → 잔량을 기본값으로 한 수량 입력(QInputDialog.getDouble 또는 소형 모달).
  RECEIVED/CANCELLED 행이면 안내 후 무시. 성공 시 목록 새로고침.
- 단순성을 위해 입고 수량 입력은 `QInputDialog.getDouble(기본=잔량, 0~잔량+초과허용)` 사용.

### 3.4 `StockSettingsDialog` 버튼 추가
`_build_button_row`에 "발주 관리" 버튼(secondary) 추가(입고/이력 버튼 옆), `_open_purchase_orders`:
```python
def _open_purchase_orders(self):
    from ui.dialogs.purchase_order_dialog import PurchaseOrderDialog
    if PurchaseOrderDialog(self.data_manager, self).exec():
        self._reload_after_change()   # 입고로 재고 변동 가능 → 재고 테이블 갱신
```

## 4. 테스트 설계

### 4.1 단위 `tests/unit/test_purchase_order_db.py` (임시 DB + LEGACY 패치, #27/#30 패턴)
- `test_create_returns_id_and_pending` — 생성 시 id 반환·status PENDING·po_number 형식.
- `test_create_rejects_blank_code_and_nonpositive_qty` — None 반환, 행 미생성.
- `test_po_number_increments_per_day` — 같은 날 2건 → -001, -002.
- `test_get_filters_by_status` + `remaining_qty` 계산.
- `test_receive_partial_sets_partial_and_updates_stock` — 부분입고 → PARTIAL, 재고 += 입고량, INBOUND 이력 1건(부호 +, note에 PO번호).
- `test_receive_remainder_sets_received` — 잔량 입고 → RECEIVED, 재고 누적.
- `test_receive_default_qty_is_remaining` — received_qty=None → 잔량 전체.
- `test_receive_on_received_or_cancelled_fails` — False, 재고/이력 불변.
- `test_receive_nonpositive_fails`.
- `test_cancel_pending_and_partial` / `test_cancel_received_fails` / `test_cancel_does_not_revert_stock`.
- `test_apply_replenishment_alias_matches_add_inbound` — 별칭이 재고 가산 + INBOUND 이력 동일 동작.
- `test_receive_atomic_history_and_stock` — 입고 후 재고와 이력 stock_after 정합.

### 4.2 통합 스모크 `tests/integration/test_purchase_order_dialog_smoke.py` (offscreen + QMessageBox patch)
- PurchaseOrderDialog: 목록 로드/빈목록 무크래시/상태필터 콤보 존재.
- 신규발주 위임(`create_purchase_order` 호출), 입고처리 위임(`receive_purchase_order`), 취소 위임.
- StockSettings "발주 관리" 버튼 → 자식 다이얼로그 **mock**으로 배선만 검증(#30 교훈 5, segfault 회피).

### 4.3 무회귀
기존 전체 테스트(232) 통과 유지 — 특히 `StockInboundHistoryTests`(add_inbound 리팩토링 가드).

## 5. 구현 순서

1. `database.py`: `purchase_orders` DDL + 인덱스 (`_create_tables`).
2. `material_stock_repository.py`: `_apply_inbound` 추출 + `add_inbound` 리팩토링 + `apply_replenishment` 별칭 + `__all__`.
3. `purchase_order_repository.py`: 신규 Repo(상수·CRUD·채번·receive 트랜잭션).
4. `database.py`: `self._po` 주입 + 위임 메서드.
5. `data_manager.py`: 위임 메서드.
6. `purchase_order_dialog.py`: 허브 + 신규발주 + 입고처리.
7. `stock_settings_dialog.py`: "발주 관리" 버튼.
8. 테스트 2종 작성 → 전체 실행 → 런타임 E2E.

## 6. 설계 불변식 (검증 대상)

- INV1: 발주 입고 후 `received_qty` 합 == 해당 PO의 INBOUND 이력 증가량 합.
- INV2: `status`는 항상 `received_qty`/`ordered_qty` 관계와 일치(또는 CANCELLED).
- INV3: `add_inbound` 외부 계약(반환·이력·로그) 리팩토링 전후 비트-동일.
- INV4: 발주/입고는 단일 conn 트랜잭션 — 중간 실패 시 PO·재고·이력 모두 롤백.
