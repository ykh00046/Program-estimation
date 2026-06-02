# PDCA #31 Design — inventory_reversal_audit

> 선행 Plan: `docs/01-plan/features/inventory_reversal_audit.plan.md`
> 무동작 보존 대상: #27(임계값 알림) · #29(`apply_consumption`) · #30(`add_inbound`/`get_stock_history`) 공개 API·반환계약

## 1. 데이터 모델

**스키마 변경 없음.** #30의 `material_stock_history`를 그대로 사용하고
`change_type='ADJUST'`(부호 있는 `quantity`)로 기록한다.

```python
MOVE_INBOUND = "INBOUND"   # 입고/매입 (+)
MOVE_CONSUME = "CONSUME"   # 배합 자동 차감 (-)
MOVE_ADJUST  = "ADJUST"    # 수정/삭제 원복·재정산 (±)  ← #31에서 활성화
```

- `quantity` 부호 규약: 원복=+(재고 증가), 재차감=−(재고 감소).
- `stock_after`: 각 조정 직후 `current_stock` 스냅샷(이력 무결성, #30과 동일).

## 2. Repository (`MaterialStockRepository`) 변경

### 2.1 신규 저수준 메서드 `apply_adjustment`

`apply_consumption`(차감 전용, CONSUME 고정)과 별개로, **부호 있는 델타**를 적용하고
`MOVE_ADJUST` 이력을 남기는 단일 메서드를 신설한다. (원복 +, 재차감 − 모두 이 메서드 1개로 처리)

```python
@handle_exceptions(user_message="자재 재고 조정 중 오류가 발생했습니다.", default_return=0)
def apply_adjustment(self, items: List[Dict], note: str = "재고 조정") -> int:
    """부호 있는 델타(``delta``)를 기존 재고에 적용하고 MOVE_ADJUST 이력을 기록한다.

    Args:
        items: ``[{"material_code": str, "delta": float}, ...]``
               delta > 0 = 가산(원복), delta < 0 = 차감(재정산). 0/빈코드는 건너뜀.
        note:  이력 메모(예: "배합 기록 삭제 원복", "배합 수정 재정산").

    동작:
        - material_code 기준 델타를 합산한다(같은 코드 중복 시 누적).
        - 단일 트랜잭션에서 기존 행만
          ``current_stock = MAX(0, current_stock + delta)`` 로 UPDATE.
          마스터에 없는 자재는 생성하지 않는다(rowcount 0 → 이력 미기록).
        - UPDATE 성공(rowcount>0)한 자재마다 ``_insert_history(... MOVE_ADJUST, delta, stock_after ...)``.

    Returns:
        실제 조정(갱신)된 자재 수.
    """
```

구현 골자(`apply_consumption`의 거울 — 같은 트랜잭션/이력 패턴 재사용):

```python
totals: Dict[str, float] = {}
for item in items or []:
    code = str(item.get("material_code") or "").strip()
    try:
        delta = float(item.get("delta") or 0.0)
    except (TypeError, ValueError):
        delta = 0.0
    if not code or delta == 0:
        continue
    totals[code] = totals.get(code, 0.0) + delta
if not totals:
    return 0
updated = 0
with self.get_connection() as conn:
    for code, delta in totals.items():
        cursor = conn.execute(
            "UPDATE material_stock "
            "SET current_stock = MAX(0, current_stock + ?), updated_at = CURRENT_TIMESTAMP "
            "WHERE material_code = ?",
            [delta, code],
        )
        if cursor.rowcount:
            updated += cursor.rowcount
            after = conn.execute(
                "SELECT current_stock, material_name, unit FROM material_stock WHERE material_code = ?",
                [code],
            ).fetchone()
            stock_after = float(after["current_stock"]) if after else 0.0
            name = after["material_name"] if after else code
            unit = after["unit"] if after else "g"
            self._insert_history(conn, code, name, MOVE_ADJUST, delta, stock_after, unit, note)
    conn.commit()
logger.debug(f"재고 조정: {updated}건 갱신 (요청 {len(totals)}종, note={note})")
return updated
```

- `apply_consumption`은 **무변경**(차감 -amount 전용, MOVE_CONSUME). 회귀 0.
- `MAX(0, ...)` floor 유지 → 음수 재고 불가(저장 차감과 동일 가드).
- `delta == 0` 스킵 → 수정 시 사용량이 동일한 자재는 불필요한 이력 생성 안 함.
- `__all__`에 변경 없음(`MOVE_ADJUST` 이미 export됨).

## 3. Facade (`database.py`) 위임 추가

`apply_consumption`/`add_inbound` 위임 블록 옆에 무데코 passthrough(PDCA #28 패턴):

```python
def apply_adjustment(self, items: List[Dict], note: str = "재고 조정") -> int:
    return self._stock.apply_adjustment(items, note)
```

## 4. DataManager (`data_manager.py`) 오케스트레이션

### 4.1 위임 + 공통 헬퍼

```python
def apply_adjustment(self, items: List[Dict], note: str = "재고 조정") -> int:
    return self.db_manager.apply_adjustment(items, note)

@staticmethod
def _norm_code(d: Dict) -> str:
    """저장 차감과 동일한 정규화: material_code 우선, 없으면 material_name."""
    return (str(d.get("material_code") or "").strip()
            or str(d.get("material_name") or "").strip())

def _reverse_inventory(self, details: List[Dict], note: str) -> None:
    """details의 actual_amount만큼 재고를 원복(+)한다(설정 on, best-effort)."""
    if not self.get_auto_deduct_on_save():
        return
    try:
        items = [{"material_code": self._norm_code(d),
                  "delta": float(d.get("actual_amount") or 0.0)}
                 for d in (details or [])]
        items = [it for it in items if it["material_code"] and it["delta"] > 0]
        if not items:
            return
        updated = self.db_manager.apply_adjustment(items, note)
        if updated:
            logger.info(f"재고 원복 완료: {updated}건 ({note})")
    except Exception as e:  # noqa: BLE001 — 원복 실패가 삭제/수정을 막지 않음
        logger.warning(f"재고 원복 실패(작업은 정상): {e}")

def _readjust_inventory(self, old_details: List[Dict],
                        new_materials: List[Dict]) -> None:
    """수정 시: old 사용량 원복(+) 1건 + new 사용량 재차감(-) 1건을
    자재당 2건의 MOVE_ADJUST로 기록한다(설정 on, best-effort)."""
    if not self.get_auto_deduct_on_save():
        return
    try:
        plus = [{"material_code": self._norm_code(d),
                 "delta": float(d.get("actual_amount") or 0.0)}
                for d in (old_details or [])]
        plus = [it for it in plus if it["material_code"] and it["delta"] > 0]
        if plus:
            self.db_manager.apply_adjustment(plus, "배합 수정 원복")
        minus = [{"material_code": self._norm_code(d),
                  "delta": -float(d.get("actual_amount") or 0.0)}
                 for d in (new_materials or [])]
        minus = [it for it in minus if it["material_code"] and it["delta"] < 0]
        if minus:
            self.db_manager.apply_adjustment(minus, "배합 수정 재차감")
        logger.info("재고 재정산 완료(수정)")
    except Exception as e:  # noqa: BLE001
        logger.warning(f"재고 재정산 실패(수정은 정상): {e}")
```

> 설계 의도: 수정은 **순효과(net)** 가 아니라 **원복+재차감 2건**으로 분리 기록한다
> (요구사항 2 "2건 ADJUST 이력"). 감사 추적상 "무엇을 되돌리고 무엇을 새로 반영했는지"가
> 명확해진다. delta==0(동일 사용량) 자재는 Repository 단에서 자동 스킵.

### 4.2 `delete_record` 수정 (원복 삽입)

기존: 레코드 조회 → `delete_mixing_record(id)`.
변경: **삭제 전** 상세를 스냅샷 → 삭제 성공 시 원복.

```python
def delete_record(self, product_lot: str) -> bool:
    try:
        record = self.db_manager.get_mixing_record_by_lot(product_lot)
        if not record:
            logger.warning(f"삭제할 기록을 찾을 수 없습니다: LOT {product_lot}")
            return False
        # 삭제 전에 차감분 스냅샷(삭제 후엔 mixing_details가 사라짐)
        old_details = self.db_manager.get_mixing_details(record['id'])
        success = self.db_manager.delete_mixing_record(record['id'])
        if success:
            self._reverse_inventory(old_details, "배합 기록 삭제 원복")
            logger.info(f"배합 기록 삭제 완료: LOT {product_lot}")
        return success
    except (sqlite3.Error, ValueError) as e:
        logger.error(f"배합 기록 삭제 오류: {e}", exc_info=True)
        return False
```

### 4.3 `update_record` 수정 (재정산 삽입)

기존: 레코드 조회 → `update_mixing_record_with_details(...)`.
변경: **수정 전** old 상세 스냅샷 → 수정 성공 시 재정산.

```python
def update_record(self, product_lot, worker, total_amount, materials) -> bool:
    try:
        record = self.db_manager.get_mixing_record_by_lot(product_lot)
        if not record:
            logger.warning(f"수정할 기록을 찾을 수 없습니다: LOT {product_lot}")
            return False
        record_id = record['id']
        old_details = self.db_manager.get_mixing_details(record_id)  # 수정 전 스냅샷
        success = self.db_manager.update_mixing_record_with_details(
            record_id=record_id, worker=worker,
            total_amount=total_amount, materials=materials,
        )
        if not success:
            return False
        self._readjust_inventory(old_details, materials)
        logger.info(f"배합 기록 수정 완료: LOT {product_lot}")
        return True
    except (sqlite3.Error, ValueError) as e:
        logger.error(f"배합 기록 수정 오류: {e}", exc_info=True)
        return False
```

> `get_mixing_details` 반환 dict는 `material_code`/`material_name`/`actual_amount` 키를 포함
> (SELECT *). `materials`(UI 입력)도 동일 키를 갖는다 → `_norm_code`/`actual_amount` 추출 일치.

## 5. 동작 시나리오 (검증용)

초기 재고 A=100 가정, 배합이 A를 30 사용.

| 단계 | 호출 | A 재고 | 이력 추가 |
|---|---|---|---|
| 저장(#29) | apply_consumption(-30) | 70 | CONSUME −30 (after 70) |
| **삭제(#31)** | apply_adjustment(+30) | 100 | ADJUST +30 (after 100) |
| (수정: 30→50) 원복 | apply_adjustment(+30) | 100 | ADJUST +30 (after 100) |
| (수정: 30→50) 재차감 | apply_adjustment(−50) | 50 | ADJUST −50 (after 50) |

순효과: 수정 후 재고 70→50(−20 = 추가 사용분), 이력 2건으로 추적 가능. ✅

## 6. 테스트 설계

| 파일 | 케이스 |
|---|---|
| `tests/unit/test_stock_adjustment.py` (신규) | ① apply_adjustment(+delta) 가산 + ADJUST 이력 부호+/stock_after ② (−delta) 차감 + MAX(0) floor ③ 같은 코드 델타 합산 ④ delta==0/빈코드 스킵(반환 0, 이력 0) ⑤ 마스터에 없는 코드 스킵(이력 0) ⑥ apply_consumption 무회귀(CONSUME 그대로) |
| `tests/integration/test_inventory_reversal.py` (신규) | ① 저장→삭제 후 재고 원복 + ADJUST 이력 1건/자재 ② 저장→수정(사용량 증가) 후 재고 재정산 + ADJUST 2건/자재 ③ 수정(사용량 감소) 재정산 ④ auto_deduct=off 시 원복/재정산 미수행 ⑤ best-effort: 원복 실패해도 delete/update 반환 True |
| 회귀 | `test_inventory_auto_deduction.py` 등 기존 38건 + 전체 스위트 |

- DB 단위 테스트: `LEGACY_DB_PATH` 패치 + `MixingDatabaseManager(tmp)` (PDCA 교훈 재사용).
- DataManager 통합: tmp DB + 설정 토글 patch.

## 7. 무회귀 보증 포인트

1. `apply_consumption`·`add_inbound`·`get_stock_history`·`upsert_material_stock`·
   `get_low_stock_materials`·`evaluate_inventory_alerts` **불변**.
2. 신규는 **추가 메서드 + 기존 2개 public 메서드(delete/update) 내부 보강**뿐 —
   두 메서드의 시그니처·반환계약(bool) 불변.
3. 스키마 변경 0(`material_stock_history` 재사용).
4. 원복/재정산은 `auto_deduct_on_save` off 시 완전 무동작 → 토글 off 기존 테스트 영향 0.
5. best-effort 분리 트랜잭션 → 원복 예외가 삭제/수정 결과를 바꾸지 않음.
