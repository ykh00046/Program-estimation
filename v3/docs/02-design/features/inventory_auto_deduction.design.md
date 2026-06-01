# PDCA #29 Design — 배합 저장 시 자동 재고 차감

> Plan: `docs/01-plan/features/inventory_auto_deduction.plan.md`

## 1. 데이터 흐름

```
controllers.save_record()
  └─ DataManager.save_record(...)
       ├─ build record_data / details_data
       ├─ db_manager.save_mixing_record(...)        # 1순위: 생산 기록(트랜잭션 A)
       ├─ _backup_to_google_sheets(...)             # best-effort
       └─ _deduct_inventory(details_data)           # ★신규 best-effort(트랜잭션 B)
            └─ db_manager.apply_consumption(consumption)
                 └─ MaterialStockRepository.apply_consumption(consumption)
```

생산 기록 저장(트랜잭션 A)과 재고 차감(트랜잭션 B)은 **분리**된다. R5: 차감 실패가 생산 기록을 롤백하지 않는다.

## 2. `MaterialStockRepository.apply_consumption`

```python
@handle_exceptions(user_message="자재 재고 차감 중 오류가 발생했습니다.", default_return=0)
def apply_consumption(self, consumption: List[Dict]) -> int:
    """배합 사용량만큼 기존 재고를 차감한다(현재고는 0 미만으로 내려가지 않음).

    Args:
        consumption: [{"material_code": str, "actual_amount": float}, ...]

    동작:
      - material_code 기준으로 사용량을 합산(R2)한다.
      - 비양수 사용량·빈 코드는 건너뛴다.
      - 단일 트랜잭션에서 기존 행만 current_stock = max(0, current_stock - amt) 로 UPDATE.
      - 마스터에 없는 자재는 생성하지 않는다(R4) → UPDATE rowcount 0.

    Returns:
        실제 차감(갱신)된 자재 수.
    """
    totals: Dict[str, float] = {}
    for item in consumption or []:
        code = str(item.get("material_code") or "").strip()
        try:
            amount = float(item.get("actual_amount") or 0.0)
        except (TypeError, ValueError):
            amount = 0.0
        if not code or amount <= 0:
            continue
        totals[code] = totals.get(code, 0.0) + amount
    if not totals:
        return 0
    updated = 0
    with self.get_connection() as conn:
        for code, amount in totals.items():
            cursor = conn.execute(
                "UPDATE material_stock "
                "SET current_stock = MAX(0, current_stock - ?), updated_at = CURRENT_TIMESTAMP "
                "WHERE material_code = ?",
                [amount, code],
            )
            updated += cursor.rowcount or 0
        conn.commit()
    logger.debug(f"재고 자동 차감: {updated}건 갱신 (요청 {len(totals)}종)")
    return updated
```

- `MAX(0, ...)`는 SQLite 스칼라 `max(a,b)` — 클램프(R3).
- 코드별 합산은 파이썬에서 수행(R2) → 같은 코드 중복 UPDATE 방지.

## 3. Facade 위임 (`MixingDatabaseManager`)

```python
# ── 자재 재고 (MaterialStockRepository) ── 섹션에 추가
def apply_consumption(self, consumption: List[Dict]) -> int:
    return self._stock.apply_consumption(consumption)
```

#28 패턴: 데코레이터 없는 순수 passthrough(예외처리는 Repo 메서드 1회).

## 4. 오케스트레이션 (`DataManager`)

`save_record`의 백업 호출 직후, return 직전에 1줄 추가:

```python
self._backup_to_google_sheets(record_data, details_data)
self._deduct_inventory(details_data)          # ★신규
logger.info(f"배합 저장: LOT {product_lot}")
```

```python
def _deduct_inventory(self, details: List[Dict]) -> None:
    """배합 저장 후 자재 재고를 자동 차감한다(설정 on일 때, best-effort)."""
    if not self.get_auto_deduct_on_save():
        return
    try:
        consumption = [
            {
                "material_code": (str(d.get("material_code") or "").strip()
                                  or str(d.get("material_name") or "").strip()),
                "actual_amount": d.get("actual_amount", 0.0),
            }
            for d in (details or [])
        ]
        updated = self.db_manager.apply_consumption(consumption)
        if updated:
            logger.info(f"재고 자동 차감 완료: {updated}건")
    except Exception as e:  # noqa: BLE001 — 차감 실패가 저장을 막지 않음(R5)
        logger.warning(f"재고 자동 차감 실패(저장은 정상): {e}")
```

> 코드 해석: 마스터 seed/upsert는 `code = TRIM(material_code) or material_name`. details의 `material_code`가
> 빈 문자열일 수 있으므로 동일하게 `material_name` 폴백(키 정합, 리스크 완화).

### 설정 토글

```python
def get_auto_deduct_on_save(self) -> bool:
    return bool(config.get("inventory_alert.auto_deduct_on_save", True))

def set_auto_deduct_on_save(self, enabled: bool) -> bool:
    return config.set_value("inventory_alert.auto_deduct_on_save", bool(enabled))
```

기본 True(키 미존재 시 활성). 기존 `inventory_alert.*` 네임스페이스 재사용.

## 5. UI (`StockSettingsDialog`)

전역 기본 임계값 행 아래에 체크박스 1개 추가:

```python
self.auto_deduct_check = QCheckBox("배합 저장 시 재고 자동 차감")
# _load_data: setChecked(self.data_manager.get_auto_deduct_on_save())
# _on_save:   self.data_manager.set_auto_deduct_on_save(self.auto_deduct_check.isChecked())
```

`get/set_auto_deduct_on_save`가 없는 fake data_manager(기존 테스트)도 깨지지 않도록 **getattr 가드** 사용:
`getattr(self.data_manager, "get_auto_deduct_on_save", lambda: True)()`.

## 6. 테스트 설계

### 단위 (`tests/unit/test_material_stock_db.py`)
- `test_apply_consumption_reduces_existing_stock`: 100→차감40→60
- `test_apply_consumption_clamps_at_zero`: 30 사용량50 → 0
- `test_apply_consumption_aggregates_duplicate_codes`: 같은 코드 30+20 → 50 차감
- `test_apply_consumption_skips_unknown_material`: 미존재 코드 → rowcount 0, 행 미생성
- `test_apply_consumption_skips_nonpositive_and_blank`: amount≤0·빈 코드 무시, 반환 0
- `test_apply_consumption_empty_returns_zero`

### 통합/오케스트레이션 (`tests/integration/test_inventory_auto_deduction.py`)
- `test_save_record_deducts_stock`: upsert로 재고 셋업 → DataManager.save_record → 재고 감소 확인
- `test_toggle_off_skips_deduction`: 토글 off → 재고 불변
- DataManager는 무거운 의존(GoogleSheets/Excel) 있으므로, `apply_consumption` 직접 경로 + `_deduct_inventory` 단위 검증으로 대체 가능(아래 Do에서 최종 결정)

### 스모크
- `StockSettingsDialog` 구동(offscreen, QMessageBox patch) + 체크박스 존재/토글 반영

## 7. 회귀 안전성

- 기존 `material_stock` CRUD·`save_mixing_record`·Facade 시그니처 **불변**(추가만).
- `apply_consumption`은 신규 메서드 → 기존 호출자 영향 0.
- 토글 기본 True → 신규 동작이지만 마스터 미설정 사용자는 차감 대상이 없어(R4) 무영향.
