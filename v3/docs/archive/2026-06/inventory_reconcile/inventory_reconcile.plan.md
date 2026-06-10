# 재고 정합성 검사·보정 (Inventory Reconcile) — Plan

> PDCA Feature: `inventory_reconcile` (PDCA #34)
> 작성일: 2026-06-10 · Level: Starter (Desktop / PySide6)

## 1. 배경 / 문제 정의

전체 검토(2026-06-10)의 High 이슈: 배합 기록 저장(트랜잭션)과 재고 차감(별도 트랜잭션,
best-effort)이 분리되어 있어 **"기록은 있는데 차감이 안 된"** 상태가 생길 수 있다
(저장 직후 강제 종료, 차감 예외 흡수, 토글 OFF 기간 등). 현재는 이를 발견·복구할 수단이 없다.

코드 분석으로 확인한 구조적 사실 (`material_stock_repository.py`):

| # | 사실 | 영향 |
|---|------|------|
| F1 | 수동 편집 `upsert_material_stock`은 **이력을 기록하지 않음** (#30 후속 후보로 예약만 됨) | 수동 편집 시 장부(history) 체인이 끊김 — 향후 드리프트의 주 원인 |
| F2 | CONSUME 이력 note는 고정 문자열 "배합 자동 차감" — **LOT 연결 없음** | 어떤 배합 기록이 차감됐는지 역추적 불가 → 미차감 검출 불가 |
| F3 | 차감/조정은 `MAX(0, ...)` clamp — 이력 quantity는 **요청량** 기록 | Σquantity 재생(replay)으로는 현재고 복원 불가 → 검사 기준은 **최근 `stock_after`** 가 옳음 |
| F4 | 시드는 0/0 생성(이력 없음), INBOUND/CONSUME/ADJUST는 모두 stock_after 스냅샷 보유 | "현재고 = 최근 stock_after" 불변식이 성립해야 정상 |

## 2. 목표 (Goals)

재고 장부의 일관성을 **검사**하고, 불일치를 **진단**하며, 사용자가 확인 후 **보정**할 수 있게 한다.
동시에 향후 드리프트의 두 근원(F1 수동 편집 무이력, F2 LOT 무연결)을 제거한다.

### 요구사항 매핑

| # | 요구사항 | 충족 방법 |
|---|----------|-----------|
| 1 | 수동 편집도 감사 추적 | `upsert_material_stock`이 변경 델타(≠0)를 ADJUST 이력으로 기록 (F1 해소) |
| 2 | 차감 이력에서 배합 기록 역추적 | CONSUME note에 LOT 포함 (`배합 자동 차감 (LOT {lot})`) (F2 해소) |
| 3 | 장부 체인 불일치 검출 | 검사 1: 자재별 `current_stock` vs 최근 `stock_after` (이력 없으면 vs 0) |
| 4 | 미차감 의심 배합 기록 검출 | 검사 2: 기간 내 `mixing_records` LOT 중 CONSUME 이력 note에 없는 LOT 목록 |
| 5 | 사용자 확인 후 보정 | (검사1) 장부 정렬 이력 기록 — 재고 불변 / (검사2) 선택 LOT 소급 차감 |
| 6 | UI 진입점 | 재고 설정 허브에 "정합성 검사" 버튼 → 결과 다이얼로그 |

## 3. 범위 (Scope)

### In Scope
- `MaterialStockRepository`:
  - `upsert_material_stock` 변경 델타 ADJUST 이력화 (요구 1)
  - `apply_consumption(consumption, note=...)` note 파라미터화 — 기본값 기존 문자열 유지 (요구 2)
  - `check_ledger_consistency() -> List[Dict]` — 검사 1 (요구 3)
  - `record_reconcile_entry(code, note)` — 재고 불변, 체인 정렬용 ADJUST(delta=드리프트) 이력 1건 (요구 5a)
- `DataManager`:
  - `_deduct_inventory`에 product_lot 전달 → CONSUME note에 LOT 포함
  - `find_undeducted_lots(start_date, end_date) -> List[Dict]` — 검사 2 (요구 4)
  - `retro_deduct_lots(lots) -> int` — 선택 LOT 소급 차감 (`apply_adjustment` 음수 델타, note에 LOT) (요구 5b)
- UI: `stock_settings_dialog` 허브에 "정합성 검사" 버튼 + 신규 `reconcile_dialog.py`
  (검사1 결과 표 + 장부 정렬 버튼 / 검사2 기간 선택(기본 최근 7일) + LOT 선택 소급 차감)
- 단위/통합 테스트 + 기존 295개 회귀 없음

### Out of Scope (후속)
- 과거 전 기간 자동 소급 보정 — 토글 OFF 기간/LOT 무연결 과거 이력은 의도 구분 불가,
  **기간 선택 + 사용자 판단** 방식만 제공 (자동화 안 함)
- 차감을 저장 트랜잭션에 포함하는 구조 변경 — best-effort 설계 의도 유지 (#29 결정 존중)
- 발주(PO)·입고 정합성 (이미 단일 트랜잭션 원자성 보장됨)
- 백업 견고화 (#35 후보)

## 4. 핵심 설계 결정 (요약 — 상세는 Design)

1. **검사 기준 = 최근 stock_after** (F3): quantity 합산 replay는 clamp 때문에 부정확.
   불변식 "current_stock == 최근 history.stock_after (이력 없으면 0)" 위반 자재만 보고.
2. **장부 보정은 재고 불변**: 현재고가 사용자가 보는 진실 → 이력 쪽을 현재고에 정렬
   (ADJUST 이력 1건, note="정합성 보정(장부 정렬)"). `apply_adjustment`는 재고를 바꾸므로
   별도 메서드 `record_reconcile_entry` 신설.
3. **소급 차감은 ADJUST로**: CONSUME은 저장 시 자동 차감 전용 의미 보존(#31 패턴).
   소급분은 `apply_adjustment(delta<0, note="소급 차감 (LOT ...)")`.
4. **미차감 검출은 note의 LOT 매칭**: 신규 저장부터 유효. 과거 기록은 기간 필터 +
   사용자 판단으로 처리 (기본 최근 7일 — false positive 최소화).
5. **기존 계약 보존**: `apply_consumption` note 기본값 = 기존 문자열("배합 자동 차감") —
   기존 테스트/동작 비트 보존. upsert 이력화는 delta=0이면 미기록(시드/무변경 저장 무影響).

## 5. 영향 범위 (변경 파일 예상)

| 파일 | 변경 |
|------|------|
| `v3/models/repositories/material_stock_repository.py` | upsert 이력화, note 파라미터, check_ledger_consistency, record_reconcile_entry |
| `v3/models/database.py` | Facade 위임 추가 |
| `v3/models/data_manager.py` | LOT note 전달, find_undeducted_lots, retro_deduct_lots |
| `v3/ui/dialogs/stock_settings_dialog.py` | "정합성 검사" 버튼 |
| `v3/ui/dialogs/reconcile_dialog.py` | **신규** 검사 결과 + 보정 다이얼로그 |
| `v3/tests/unit/test_inventory_reconcile.py` | **신규** |
| `v3/tests/integration/test_reconcile_dialog_smoke.py` | **신규** |

## 6. 리스크 / 완화

| 리스크 | 영향 | 완화 |
|--------|------|------|
| upsert 이력화로 기존 upsert 테스트 깨짐 | 중 | delta=0 미기록 + 반환값/시그니처 불변. 기존 테스트 회귀 가드로 활용 |
| note 의미 과적재(LOT 파싱 취약) | 중 | LOT 매칭은 `LIKE '%(LOT ' \|\| lot \|\| ')%'` 정확 포맷 고정, 포맷 상수화 |
| 과거 기록 대량 false positive | 중 | 기간 기본 7일 + 사용자 선택 적용(자동 보정 금지) |
| 소급 차감 중복 적용 | 높음 | 소급 차감 시 note에 LOT 기록 → 동일 LOT 재검출 제외 (CONSUME+ADJUST 양쪽 매칭) |
| Python 3.9 / 다이얼로그 모달(offscreen) | 중 | typing 준수, 스모크는 QMessageBox patch (#23 교훈) |

## 7. 완료 기준 (Definition of Done)

- [ ] 요구사항 1~6 구현
- [ ] gap-detector 일치율 ≥ 90%
- [ ] 신규 테스트 통과 + 기존 295개 회귀 없음
- [ ] 기존 UITheme 토큰만 사용
- [ ] 완료 보고서 작성

## 8. 다음 단계

→ `/pdca design inventory_reconcile`
