# 재고 정합성 검사·보정 (Inventory Reconcile) — Design

> PDCA Feature: `inventory_reconcile` (PDCA #34)
> 작성일: 2026-06-10 · Plan: `docs/01-plan/features/inventory_reconcile.plan.md`

## 1. 아키텍처 개요

```
StockSettingsDialog ──"정합성 검사"──▶ ReconcileDialog
                                        │
                                        ├─ 검사1: 장부 체인   ──▶ DataManager ──▶ Facade ──▶ MaterialStockRepository
                                        │   └─ [장부 정렬]            check_ledger_consistency / record_reconcile_entry
                                        │
                                        └─ 검사2: 미차감 LOT  ──▶ find_undeducted_lots (기간)
                                            └─ [선택 소급 차감] ──▶ retro_deduct_lots → apply_adjustment(-)
```

**불변식**: 정상 상태에서 `material_stock.current_stock == 최근 material_stock_history.stock_after`
(이력이 없으면 0). clamp(MAX 0) 때문에 Σquantity replay는 사용하지 않는다 (Plan F3).

**note 포맷 상수** (LOT 역추적의 단일 진실):
```python
# material_stock_repository.py 모듈 상수
LOT_NOTE_SUFFIX_FMT = "(LOT {lot})"      # note 끝에 부착되는 LOT 마커
CONSUME_NOTE_FMT = "배합 자동 차감 (LOT {lot})"
RETRO_NOTE_FMT = "소급 차감 (LOT {lot})"
RECONCILE_NOTE = "정합성 보정(장부 정렬)"
```
미차감 검출은 `note LIKE '%(LOT ' || product_lot || ')%'` 정확 포맷 매칭 —
CONSUME(자동 차감)·ADJUST(소급 차감) 어느 쪽이든 마커가 있으면 "차감됨"으로 간주
(소급 차감 중복 적용 방지, Plan 리스크 4).

## 2. 컴포넌트 설계

### 2.1 `MaterialStockRepository` (4개 변경/신규)

**(a) `upsert_material_stock` 수동 편집 이력화** — **opt-in 파라미터** `log_history: bool = False`:
```python
with self.get_connection() as conn:
    old = conn.execute("SELECT current_stock FROM material_stock WHERE material_code = ?", [code]).fetchone()
    old_stock = float(old["current_stock"]) if old else 0.0
    conn.execute(<기존 UPSERT SQL 그대로>)
    delta = current - old_stock
    if log_history and abs(delta) > LEDGER_TOLERANCE:  # 무변경 저장은 이력 미기록
        self._insert_history(conn, code, name, MOVE_ADJUST, delta, current, unit, MANUAL_EDIT_NOTE)
    conn.commit()
```
> 기본 False인 이유: 기존 테스트/시드가 upsert를 셋업으로 쓰며 이력 건수를 단언함 —
> 무조건 이력화는 광범위 회귀. 수동 편집의 유일한 진입점인
> **DataManager.upsert_material_stock 위임에서 `log_history=True` 고정**으로
> 다이얼로그 경로만 감사 추적된다 (Facade는 파라미터 passthrough).

**(b) `apply_consumption(consumption, note="배합 자동 차감")`** — note 파라미터 추가,
기본값이 기존 문자열이므로 기존 호출/테스트 비트 보존. `_insert_history(..., note)` 전달만 변경.

**(c) `check_ledger_consistency(tolerance=1e-6) -> List[Dict]`** (신규):
```sql
SELECT s.material_code, s.material_name, s.current_stock, s.unit,
       (SELECT h.stock_after FROM material_stock_history h
        WHERE h.material_code = s.material_code
        ORDER BY h.created_at DESC, h.id DESC LIMIT 1) AS ledger_stock
FROM material_stock s ORDER BY s.material_name
```
Python에서 `drift = current_stock - (ledger_stock if not None else 0.0)` 계산,
`abs(drift) > tolerance`인 자재만 반환: `{material_code, material_name, current_stock,
ledger_stock(None→0.0), drift, unit}`. `@handle_exceptions(default_return=[])`.

**(d) `record_reconcile_entry(material_code, note=RECONCILE_NOTE) -> bool`** (신규):
**재고는 절대 변경하지 않는다** — 현재고를 진실로 보고 장부 체인을 정렬.
drift 재계산(위 (c)와 동일 기준) 후 `abs(drift) <= tolerance`면 False,
아니면 `_insert_history(ADJUST, quantity=drift, stock_after=current_stock, note)` 1건 + commit → True.

**(e) `find_undeducted_lots(start_date, end_date) -> List[Dict]`** (신규):
mixing_records와 history가 **동일 DB 파일**이므로 단일 SQL:
```sql
SELECT r.product_lot, r.recipe_name, r.work_date, r.total_amount
FROM mixing_records r
WHERE r.work_date >= ? AND r.work_date <= ?
  AND NOT EXISTS (
      SELECT 1 FROM material_stock_history h
      WHERE h.note LIKE '%(LOT ' || r.product_lot || ')%')
ORDER BY r.work_date DESC, r.product_lot DESC
```
> 도메인 경계 주석: 재고 정합성 진단이 생산 기록을 *읽기만* 하는 cross-domain 조회 —
> docstring에 명시 (수정은 MixingRecordRepository 영역 침범 금지).

### 2.2 Facade (`database.py`) — 순수 위임 3건 추가
`check_ledger_consistency` / `record_reconcile_entry` / `find_undeducted_lots`
(#28 규약: 데코레이터 없는 passthrough, `@handle_exceptions`는 Repo에만).

### 2.3 `DataManager`

| 변경 | 내용 |
|------|------|
| `_deduct_inventory(details, product_lot)` | 파라미터 추가, `apply_consumption(consumption, note=CONSUME_NOTE_FMT.format(lot=product_lot))`. `save_record` 호출부에서 lot 전달 |
| `check_ledger_consistency()` / `record_reconcile_entry(code)` | Facade 위임 |
| `find_undeducted_lots(start_date, end_date)` | Facade 위임 |
| `retro_deduct_lots(lots: List[str]) -> int` (신규) | LOT마다: `get_mixing_record_by_lot` → `get_mixing_details(record['id'])` → `[{material_code: _norm_code(d), delta: -actual_amount}]` → `apply_adjustment(items, note=RETRO_NOTE_FMT.format(lot=lot))`. 갱신 자재 수>0인 LOT 수 반환. 기록 없으면 스킵+warning |

`_norm_code` 재사용(#31)으로 저장 차감과 동일한 code→name 폴백 보장.

### 2.4 UI

**`reconcile_dialog.py` (신규)** — `ReconcileDialog(QDialog)`:
- 섹션 1 "장부 일관성": 표(자재코드/자재명/현재고/장부재고/차이) — `check_ledger_consistency` 결과.
  비어있으면 "모든 자재의 장부가 일치합니다" 라벨. `[장부 정렬]` 버튼: 확인 QMessageBox →
  각 행 `record_reconcile_entry` → 재검사·표 갱신.
- 섹션 2 "미차감 의심 배합 기록": `QDateEdit` 시작(기본 7일 전)/종료(오늘) + `[검사]` 버튼 →
  체크박스 표(LOT/레시피/작업일/배합량) — `find_undeducted_lots`. `[선택 소급 차감]` 버튼:
  확인 QMessageBox → `retro_deduct_lots(선택 LOT)` → 재검사.
- 스타일: `UIStyles.get_dialog_style/get_table_style/버튼 스타일` 기존 토큰만. 신규 색 금지.
- 모든 보정 액션은 **사용자 확인 후** 실행 (자동 보정 금지 — Plan 결정 4).

**`stock_settings_dialog.py`**: `_build_button_row`에 `reconcile_btn`("정합성 검사") 추가 →
`_open_reconcile`: `ReconcileDialog(self.data_manager, self).exec()` 후 `_reload_after_change()`
(소급 차감으로 재고 변동 가능). 기존 버튼 패턴(지연 import) 동일.

## 3. 오류 처리 정책

| 경로 | 정책 |
|------|------|
| 검사/보정 Repo 메서드 | `@handle_exceptions` + default_return ([]/False/0) — 기존 재고 메서드와 동일 |
| 다이얼로그 로드/액션 | try/except + QMessageBox.warning (stock_settings 패턴) |
| retro_deduct 일부 LOT 실패 | 성공 건수만 반환, 실패 LOT은 warning 로그 — 재검사로 잔여 확인 가능 |

## 4. 테스트 계획

| 테스트 | 파일 | 검증 |
|--------|------|------|
| upsert 이력화 | `tests/unit/test_inventory_reconcile.py` (신규, 실제 tmp DB — `test_material_stock_db.py` 패턴) | 값 변경 시 ADJUST(delta) 기록 / 무변경 저장 무기록 / 신규 생성 delta=current |
| consumption note | 〃 | `apply_consumption(note=...)` → history note에 LOT 마커. 기본값 호출은 기존 문자열(회귀) |
| check_ledger_consistency | 〃 | 정상 흐름(입고→차감) 후 [] / SQL로 current 직접 변조 → drift 검출 / 이력 없는 자재 current>0 검출 |
| record_reconcile_entry | 〃 | 이력 1건 추가 + **current_stock 불변** + 직후 consistency [] / drift≈0이면 False·무기록 |
| find_undeducted_lots | 〃 | 차감 이력 有/無 LOT 구분, 기간 필터, 소급 차감(ADJUST 마커) 후 재검출 제외 |
| retro_deduct_lots | 〃 | 재고 감소 + ADJUST note에 LOT / 미존재 LOT 스킵 |
| 다이얼로그 스모크 | `tests/integration/test_reconcile_dialog_smoke.py` (신규, mock dm + QMessageBox patch) | 생성/표 로드/버튼→DM 위임/빈 결과 안전 |
| 허브 배선 | 〃 | stock_settings "정합성 검사" 버튼 → ReconcileDialog mock 호출 (#30 자식 다이얼로그 mock 패턴) |
| 회귀 | `run_tests.py` | 기존 295개 통과 (특히 `test_material_stock_db`/`test_inventory_auto_deduction`) |

## 5. 구현 순서

1. Repository: 상수 4종 + (a)~(e) + 단위 테스트
2. Facade 위임 3건
3. DataManager: LOT note 전달 + retro_deduct_lots + 위임 + 테스트
4. ReconcileDialog + stock_settings 버튼 + 스모크
5. 전체 회귀 + 보고

## 6. 호환성 체크리스트

- [ ] Python 3.9 typing (`Optional`/`List`/`Dict`, `|` 금지)
- [ ] 스키마 변경 0 (기존 테이블/컬럼 재사용 — 무중단)
- [ ] `apply_consumption`/`upsert` 기존 호출 비트 보존 (기본값·시그니처 호환)
- [ ] UITheme 토큰 외 신규 스타일 금지
- [ ] 함수 20줄 이내 / 타입 힌트

## 7. 다음 단계

→ `/pdca do inventory_reconcile`
