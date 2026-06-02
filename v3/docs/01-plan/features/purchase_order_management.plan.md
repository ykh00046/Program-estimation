# PDCA #32 Plan — purchase_order_management (자재 발주(PO) 등록 + 입고 연동)

> 작성일: 2026-06-02 · Level: Starter (PySide6 데스크톱) · 선행: #27(임계값 알림) · #29(자동 차감) · #30(입고/이력)

## 1. 배경 / 문제 정의

bkit 분석 1순위 추천 기능은 **"자재 입고/발주 관리"** 였다. 이 중 **입고(매입 등록) + 입출고 이력**
절반은 PDCA #30(`inventory_inbound_history`)에서 이미 완료되었다(`add_inbound`, `material_stock_history`,
`InboundDialog`, `StockHistoryDialog`, 232 테스트). 그러나 나머지 절반인 **발주(Purchase Order)** 는
여전히 공백이며, #30이 명시적으로 비범위(후속 후보 #3)로 남긴 부분이다.

현재의 한계:

1. **발주(주문) 추적 부재** — "○○자재 100kg를 △△매입처에 주문했다"는 사실을 기록할 곳이 없다.
   입고(`add_inbound`)는 이미 *물건이 도착한 뒤* 재고를 늘리는 경로일 뿐, *주문~도착 사이의 미결 상태*
   (대기/부분입고)를 관리할 수 없다.
2. **발주↔입고 단절** — 입고가 어떤 발주에 대한 것인지 연결되지 않아, "주문한 것 중 아직 안 온 양"을
   알 수 없다. 제조 현장의 자재 조달은 **발주 잔량(미입고분) 가시성**이 핵심이다.
3. **저재고 알림(#27)의 다음 액션 부재** — 알림을 봐도 "발주 → 입고"로 이어지는 워크플로가 없어
   알림이 행동으로 연결되지 않는다.

→ 메모리 `project_pdca_stock_alert`의 남은 후속 후보 **"입고/발주 관리"** 중 발주 절반을 완성하여
재고 라이프사이클(발주 → 입고 → 차감 → 알림)을 닫는다.

## 2. 목표 (이번 사이클 범위)

| # | 요구사항 | 수용 기준 |
|---|---|---|
| R1 | 발주 등록 | 자재코드·발주량·(선택)매입처·단위·메모로 발주 생성. 발주번호 `PO-YYYYMMDD-NNN` 자동 채번. 상태 `PENDING`. |
| R2 | 발주 입고 처리 | 발주에 입고 수량(기본=잔량) 적용 → `received_qty += 수량`, 상태 자동 전이(PENDING→PARTIAL→RECEIVED). **동일 트랜잭션**에서 `material_stock` 누적 가산 + `material_stock_history` INBOUND 이력 기록(메모에 발주번호 포함). |
| R3 | apply_replenishment | 사용자 요청 명칭. `MaterialStockRepository.add_inbound`의 공개 별칭으로 제공(재고 보충 단발 경로). Facade/DM까지 위임. |
| R4 | 발주 목록/상태 조회 | 발주 목록을 최신순 조회(발주번호/자재/매입처/발주량/입고량/잔량/상태/일시). 상태 필터(전체/대기/부분/완료/취소). |
| R5 | 발주 취소 | PENDING/PARTIAL 발주를 CANCELLED 처리(이미 입고된 재고는 원복하지 않음 — 비범위). RECEIVED/CANCELLED는 취소 불가. |
| R6 | 발주 관리 UI | `재고 설정` 다이얼로그에 "발주 관리" 버튼 → `PurchaseOrderDialog`(목록·필터·신규발주·입고처리·취소). 신규 발주 입력은 소형 모달. |
| R7 | 무회귀 | 기존 232 테스트 통과 유지. #27/#29/#30 공개 동작·시그니처 불변(특히 `add_inbound` 동작 비트-동일). |

## 3. 비범위 (이번 사이클 제외)

- 매입처(공급사) 마스터 테이블·단가/금액/통화 — 매입처·메모는 자유 텍스트 컬럼으로만.
- 발주 입고 취소/롤백, 부분입고 분할 라인(line item) — 발주 1건 = 자재 1종(단일 라인) 단순 모델.
- 발주 취소 시 이미 입고된 재고 원복(ADJUST) — `MOVE_ADJUST` 상수는 #30에서 이미 예약, 별도 후속.
- 발주 PDF/Excel 내보내기·발주서 출력 — 별도 후속.
- 수동 편집(`upsert_material_stock`)의 ADJUST 이력화 — #30 비범위 유지.

## 4. 접근 방식 (기존 자산 재사용)

- **신규 테이블 `purchase_orders`** — 발주는 `material_stock`(현재 상태)·`material_stock_history`(이동 로그)와
  다른 도메인(주문 라이프사이클)이므로 별 테이블. DDL은 `_create_tables`에 `IF NOT EXISTS`로 추가 →
  기존 운영 DB는 다음 기동 시 무중단 마이그레이션(#30 교훈 6).
- **신규 `PurchaseOrderRepository(SqliteManagerBase)`** — #28 Repository 분해 패턴 계승. 단발 트랜잭션
  `get_connection()` 사용. 입고 연동을 위해 **`MaterialStockRepository`를 생성자 주입** 받아,
  같은 conn에서 재고 가산 + 이력 기록을 수행(원자성).
- **`MaterialStockRepository` 최소 확장** — 입고 반영 로직(UPSERT + `_insert_history`)을 conn을 인자로 받는
  내부 헬퍼 `_apply_inbound(conn, ...)`로 추출하고, 기존 `add_inbound`는 그 헬퍼를 호출하도록 리팩토링
  (동작·반환 비트-동일, #30 테스트가 회귀 가드). `apply_replenishment`는 `add_inbound`의 얇은 별칭.
- **Facade(`database.py`) / `DataManager` 위임** — #28/#30 무데코 passthrough 패턴 그대로.
- **UI는 `StockSettingsDialog`(재고 허브) 확장** — 버튼 1개("발주 관리") 추가. 신규 모달
  `PurchaseOrderDialog`(목록 허브) + 내부 신규발주/입고처리 입력. 기존 패널/대시보드 무변경
  (입고 처리 시 재고 증가로 알림 카드 자동 반영).
- **상태 상수** — `PO_PENDING`/`PO_PARTIAL`/`PO_RECEIVED`/`PO_CANCELLED`. 입고 시 잔량 기준 자동 전이.

## 5. 리스크 / 완화

| 리스크 | 완화 |
|---|---|
| `add_inbound` 리팩토링이 #30 회귀 유발 | 입고 로직을 `_apply_inbound`로 *추출*만, SQL·반환·로그 불변. #30의 `StockInboundHistoryTests` 9건이 가드. |
| 발주 입고와 재고 가산이 별 트랜잭션이면 정합 깨짐 | 두 Repo가 같은 DB파일·같은 conn 1개에서 PO갱신+재고가산+이력INSERT를 한 트랜잭션으로 커밋(#30 교훈 3 적용). |
| 발주번호 채번 동시성 | 데스크톱 단일 인스턴스(Mutex). 같은 트랜잭션 내 당일 COUNT+1로 충분. |
| 헤드리스 테스트 모달 hang/segfault | 신규 다이얼로그 스모크는 offscreen + QMessageBox patch, 자식 다이얼로그는 mock 대체(#30 교훈 5). |
| 음수/0/빈코드 발주·입고 | Repo 레벨에서 거부(반환 False/None), 단위 테스트로 명시 검증. |

## 6. 산출물

- 코드: `models/database.py`(DDL+위임), `models/repositories/material_stock_repository.py`(헬퍼+별칭),
  `models/repositories/purchase_order_repository.py`(신규), `models/data_manager.py`(위임),
  `ui/dialogs/purchase_order_dialog.py`(신규), `ui/dialogs/stock_settings_dialog.py`(버튼).
- 테스트: `tests/unit/test_purchase_order_db.py`, `tests/integration/test_purchase_order_dialog_smoke.py`.
- 문서: 본 plan, design, analysis, report.

## 7. 완료 정의 (DoD)

- R1~R7 전부 충족, 전체 테스트 통과(232 → +N, 회귀 0).
- 런타임 E2E(발주 → 부분입고 → 완료입고 → 재고/이력 연동 → 취소) PASS.
- Gap Match ≥ 90%, Report 작성.
