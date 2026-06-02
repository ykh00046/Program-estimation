# PDCA #32 Analysis (Gap) — purchase_order_management

> 설계: `docs/02-design/features/purchase_order_management.design.md` · 분석일: 2026-06-02

## 1. 요구사항 충족 매트릭스 (Plan §2)

| # | 요구사항 | 구현 | 검증 | 상태 |
|---|---|---|---|---|
| R1 | 발주 등록(채번·PENDING) | `PurchaseOrderRepository.create_purchase_order` + `_next_po_number` | unit `test_create_returns_id_and_pending`, `test_po_number_increments_per_day`, E2E QA1 | ✅ |
| R2 | 발주 입고 처리(상태전이·재고·이력 원자적) | `receive_purchase_order` (단일 conn → `_status_for` + `_stock._apply_inbound`) | unit `test_receive_partial/remainder/default/consistency`, E2E QA2·QA3 | ✅ |
| R3 | `apply_replenishment` 별칭(Stock·Facade·DM) | `MaterialStockRepository.apply_replenishment` + Facade/DM 위임 | unit `test_apply_replenishment_alias_matches_add_inbound`, E2E QA6 | ✅ |
| R4 | 발주 목록/상태 조회(필터·remaining) | `get_purchase_orders` (status 필터, remaining_qty 계산) | unit `test_get_filters_by_status`, smoke `test_filter_*` | ✅ |
| R5 | 발주 취소(PENDING/PARTIAL만, 재고 원복 X) | `cancel_purchase_order` | unit `test_cancel_pending/partial/received_fails/does_not_revert`, E2E QA5 | ✅ |
| R6 | 발주 관리 UI | `PurchaseOrderDialog` + `_NewOrderDialog` + 재고허브 "발주 관리" 버튼 | smoke 12건(목록/필터/입고/취소/신규/배선) | ✅ |
| R7 | 무회귀 | `add_inbound` `_apply_inbound` 추출(동작 불변) | 전체 **278 passed** (회귀 0) | ✅ |

**충족: 7/7**

## 2. 설계 불변식 검증 (Design §6)

| 불변식 | 검증 | 결과 |
|---|---|---|
| INV1: received_qty 합 == INBOUND 이력 증가량 합 | E2E QA2/QA3, `test_receive_history_stock_after_consistency` | ✅ |
| INV2: status ↔ received/ordered 관계 일치 | `test_receive_partial/remainder`, `test_receive_overdelivery_caps` | ✅ |
| INV3: add_inbound 외부 계약 비트-동일 | #30 `StockInboundHistoryTests` 전건 통과 | ✅ |
| INV4: 발주/입고 단일 트랜잭션(원자성) | 단일 `get_connection()` conn 내 PO UPDATE + `_apply_inbound`, 말미 1회 commit | ✅ (코드 리뷰 + E2E) |

## 3. 산출물 점검

| 유형 | 파일 | 비고 |
|---|---|---|
| DB | `models/database.py` | `purchase_orders` DDL + 인덱스 3 + `_po` 주입 + 위임 5 |
| Repo(확장) | `models/repositories/material_stock_repository.py` | `_apply_inbound` 추출 + `add_inbound` 리팩토링 + `apply_replenishment` |
| Repo(신규) | `models/repositories/purchase_order_repository.py` | 상수 4 + create/get/receive/cancel + 채번/상태 헬퍼 |
| Facade/DM | `models/database.py`, `models/data_manager.py` | passthrough 위임 |
| UI(신규) | `ui/dialogs/purchase_order_dialog.py` | 허브 + 신규발주 모달 |
| UI | `ui/dialogs/stock_settings_dialog.py` | "발주 관리" 버튼 + `_open_purchase_orders` |
| 테스트 | `tests/unit/test_purchase_order_db.py` | 19건 |
| 테스트 | `tests/integration/test_purchase_order_dialog_smoke.py` | 12건 |

## 4. 검증 결과 요약

- 단위/통합: **278 passed** (이전 기준 대비 +31: PO unit 19 + PO smoke 12), 회귀 0, 약 11s.
- 런타임 E2E: **7/7 PASS** (생성·채번 / 부분입고 / 잔량자동입고 / RECEIVED 재입고거부 / 취소 / 별칭 / 구버전DB 마이그레이션).

## 5. 누락/불일치

- 없음. Plan 비범위(매입처 마스터·단가·발주취소시 재고원복·발주서 출력)는 의도적 제외이며 후속 후보로 명시.

## 6. Match Rate

**≈ 99%** (R1~R7 7/7, INV1~INV4 4/4, 누락/불일치 0). Iterate 불필요(≥90%).
