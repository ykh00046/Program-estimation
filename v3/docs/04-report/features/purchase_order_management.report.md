# PDCA #32 Report — purchase_order_management (자재 발주(PO) 등록 + 입고 연동)

> 완료일: 2026-06-02 · Level: Starter (PySide6 데스크톱) · Match ≈ 99%

## 1. 개요

bkit 1순위 추천 "자재 입고/발주 관리" 중 **입고/이력**은 PDCA #30에서 이미 완료되어 있었다.
이번 #31은 남은 절반인 **발주(Purchase Order)** 를 구현하여 재고 라이프사이클
(발주 → 입고 → 차감 → 알림)을 닫았다. 발주 등록·부분/완료 입고·취소를 제공하며,
입고 처리는 #30 입고 엔진(`_apply_inbound`)을 **동일 트랜잭션**에서 재사용해 재고 누적 +
INBOUND 이력을 원자적으로 반영한다. 사용자 요청 명칭 `apply_replenishment`는 `add_inbound`의
공개 별칭으로 제공했다.

## 2. 변경 사항

| 유형 | 파일 | 내용 |
|---|---|---|
| DB | `models/database.py` | `purchase_orders` 테이블 DDL + 인덱스 3개 + `PurchaseOrderRepository` 주입 + 위임 5종(`apply_replenishment`/PO 4종) |
| Repo(확장) | `models/repositories/material_stock_repository.py` | 입고 코어 `_apply_inbound(conn,…)` 추출, `add_inbound`가 이를 호출하도록 리팩토링(동작 불변), `apply_replenishment` 별칭 |
| Repo(신규) | `models/repositories/purchase_order_repository.py` | `PO_PENDING/PARTIAL/RECEIVED/CANCELLED`, `create/get/receive/cancel_purchase_order`, `_next_po_number`/`_status_for` |
| Facade/DM | `models/repositories/__init__.py`, `models/data_manager.py` | export + passthrough 위임 |
| UI(신규) | `ui/dialogs/purchase_order_dialog.py` | `PurchaseOrderDialog`(목록·상태필터·입고·취소) + `_NewOrderDialog`(신규 발주 입력) |
| UI | `ui/dialogs/stock_settings_dialog.py` | "발주 관리" 버튼 + `_open_purchase_orders`(닫힘 시 재고 테이블 갱신) |
| 테스트 | `tests/unit/test_purchase_order_db.py` | 19건 |
| 테스트 | `tests/integration/test_purchase_order_dialog_smoke.py` | 12건 |

## 3. 검증 결과

- **단위/통합**: 278 passed (+31), 회귀 0, ~11s.
- **Gap 분석**: R1~R7 7/7, 불변식 INV1~INV4 4/4, 누락/불일치 0 → Match ≈ 99%.
- **런타임 E2E**: 7/7 PASS
  - QA1 발주 생성 + 당일 채번(PO-YYYYMMDD-001/002)
  - QA2 부분입고 → PARTIAL, 재고 +40, INBOUND 이력(발주번호 메모)
  - QA3 잔량 자동입고(received_qty=None) → RECEIVED, 재고 100
  - QA4 RECEIVED 재입고 거부(재고/이력 불변)
  - QA5 PENDING 취소 OK / RECEIVED 취소 거부 / 입고분 재고 원복 없음
  - QA6 `apply_replenishment` 별칭 = `add_inbound` 동작
  - QA7 구버전 DB(purchase_orders 없음) 재기동 시 테이블 자동 생성 + 기존 재고 보존

## 4. 교훈 (durable)

1. **요청 전 기존 자산 확인이 중복 구현을 막는다** — "입고/발주 관리" 요청이 들어왔으나 입고/이력은
   #30에서 이미 완료된 상태였다. 코드/커밋 선조사로 *실제 공백(발주)* 만 구현해 중복 작업을 회피.
   기능 요청은 "무엇이 이미 있는가"부터 확인한다.
2. **입고 코어를 conn-주입 헬퍼로 추출 → 두 진입점이 한 트랜잭션을 공유** — 단발 입고(`add_inbound`)와
   발주 입고(`receive_purchase_order`)가 `_apply_inbound(conn, …)`를 공유. 발주 Repo가 재고 Repo를
   생성자 주입받아 **같은 conn**에서 호출 → 재고 가산 + 이력 기록 + PO 갱신이 원자적. #30 교훈 3
   ("의미로 트랜잭션 경계를 정한다")의 cross-repository 확장.
3. **검증된 메서드는 동작 보존 추출만** — `add_inbound`의 외부 계약(검증·반환·로그·INBOUND 이력)을
   유지하고 내부 SQL만 `_apply_inbound`로 이동. #30 `StockInboundHistoryTests`가 회귀 가드 역할 →
   리팩토링 안전성을 테스트가 보증.
4. **상태는 저장하지 말고 파생하라** — PO `status`는 입고 시마다 `_status_for(ordered, received)`로
   재계산해 UPDATE. received_qty가 SSOT, status는 파생값이라 불일치 여지가 없다(INV2).
5. **새 테이블은 별 도메인일 때만** — 발주는 주문 라이프사이클(현재상태 ≠ 이동로그)이라 신규 테이블이
   타당. 입고 이력은 기존 `material_stock_history`(INBOUND) 재사용 → 발주 입고도 동일 이력에 통합 기록.
6. **PySide6 입고 수량 입력은 `QInputDialog.getDouble`로 충분** — 잔량을 기본값으로 주면 추가 모달
   클래스 없이 부분/전체 입고 UX 확보. 스모크는 `getDouble`을 patch해 hang 회피(#30 교훈 5 계열).

## 5. 후속 후보 (다음 PDCA)

1. 매입처(공급사) 마스터 + 단가/금액/통화 — 발주 메모의 자유텍스트를 구조화.
2. 발주 입고 취소/롤백(잘못 입고 정정) — `apply_adjustment`(ADJUST) 경로 연계.
3. 발주서 PDF/Excel 출력 (대시보드 export #25/#26 패턴 재사용).
4. 대시보드에 미결 발주(PENDING/PARTIAL) 요약 카드 + 저재고 알림 → 발주 바로가기.
5. 발주 1건 다(多)자재 라인(line item) 확장.

## 6. PDCA 상태

- Plan ✅ → Design ✅ → Do ✅ → Check ✅(≈99%) → (Iterate 불필요) → QA ✅ → Report ✅
- 다음 PDCA 번호: **#33**
- 커밋 대기. 메모리 `project_pdca_status` / `project_pdca_stock_alert` 갱신 대상.
