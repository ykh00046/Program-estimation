# PDCA #30 Report — inventory_inbound_history (재고 입고/매입 등록 + 입출고 이력 추적)

> 완료일: 2026-06-02 · Match ≈ 99%(실질 100%) · 전체 232 테스트 그린(214→+18, 회귀 0)
> 선행: #27(임계값 알림) · #29(자동 차감) | 후속 라인: 입고/발주·감사 로그 후보 해소

## 1. 요약

PDCA #27(알림)·#29(자동 차감)으로 재고가 *줄어드는* 경로와 알림은 갖췄으나,
재고를 *늘리는*(입고/매입) 경로와 변동 **이력(감사 로그)** 이 없던 공백을 해소했다.

- **입고(매입) 등록**: 기존 재고에 **누적 가산**(절대값 덮어쓰기인 #27 `upsert`와 구분). 마스터에 없으면 신규 생성.
- **입출고 이력**: 모든 이동(INBOUND/CONSUME)을 append-only `material_stock_history`에 부호 있는 델타·이동 후 재고 스냅샷·메모·시각과 함께 기록.
- **자동 차감 연동**: #29 `apply_consumption`이 차감과 **동일 트랜잭션**에서 CONSUME 이력을 남긴다(반환 계약 불변).
- **UI**: `재고 설정` 다이얼로그를 재고 허브로 확장 — "입고 등록"·"입출고 이력" 버튼 + 신규 모달 2종.

## 2. 변경 산출물

| 영역 | 파일 | 변경 |
|---|---|---|
| Repository | `models/repositories/material_stock_repository.py` | `add_inbound`/`get_stock_history`/`_insert_history` 신규, `apply_consumption`에 CONSUME 이력 가산, `MOVE_*` 상수 |
| 인프라 | `models/database.py` | `material_stock_history` 테이블+인덱스 2개(`IF NOT EXISTS`), `add_inbound`/`get_stock_history` 위임 |
| DataManager | `models/data_manager.py` | `add_inbound`/`get_stock_history` 위임 |
| UI(신규) | `ui/dialogs/inbound_dialog.py` | 입고 등록 다이얼로그(editable 콤보·수량·메모) |
| UI(신규) | `ui/dialogs/stock_history_dialog.py` | 입출고 이력 뷰(6열·자재 필터·부호 색상) |
| UI | `ui/dialogs/stock_settings_dialog.py` | 입고/이력 버튼 + `_open_inbound`/`_open_history`/`_reload_after_change` |
| 테스트 | `tests/unit/test_material_stock_db.py` | `StockInboundHistoryTests` 9건 |
| 테스트 | `tests/integration/test_inventory_dialog_smoke.py` | Inbound 4 + History 3 + Hub 2 = 9건 |

## 3. 검증 결과

- **단위/통합**: 232 passed (214→+18), 회귀 0, 5.86s.
- **Gap 분석**: R1~R6 6/6, §7 무회귀 4/4, 누락/불일치 0 → Match ≈ 99%.
- **런타임 QA(스크립트 E2E)**: 6/6 PASS
  - QA1 **기존 DB 자동 마이그레이션**: 이력 테이블 없는 구버전 DB 재기동 시 테이블 자동 생성 + 기존 재고 보존 ✅
  - QA2 입고 누적(M1 100→150)·신규 생성(M2 30) ✅
  - QA3 자동 차감 `updated=1`, M1 110 ✅
  - QA4 이력 최신순 `[(CONSUME,-40,110),(INBOUND,+50,150)]` ✅
  - QA5 0/음수/빈코드 거부 ✅
  - QA6 전체/자재 필터 ✅

## 4. 교훈 (durable)

1. **append-only 로그는 마스터와 분리** — 현재 상태(SSOT=`material_stock`)와 불변 이동 로그(`material_stock_history`)를 별 테이블로 분리. 외래키 없이(자재 삭제 기능 부재·이력은 코드 사라져도 보존) 단순 유지. PDCA #18 "기존 자산 재사용 + 중복 테이블 회피"의 연장.
2. **검증된 메서드 확장은 순수 가산으로** — #29 `apply_consumption`의 반환 계약(`updated` count)을 건드리지 않고 이력 INSERT를 `if cursor.rowcount:` **내부**에 가산. 차감과 동일 트랜잭션이라 원자성 확보. 반환값 단언 테스트가 회귀 가드.
3. **부수효과 트랜잭션 경계는 의미에 따라** — #29의 "저장↔차감"은 **분리**(차감 실패가 저장을 막으면 안 됨), 그러나 "차감↔차감이력"은 **동일 트랜잭션**(이력은 차감의 일부, 함께 커밋되어야 정합). 같은 "best-effort"가 아니라 의미로 경계를 정한다.
4. **누적 가산 vs 절대값 설정은 별 메서드로** — 입고(`current_stock + excluded`)와 수동 편집(`upsert` 절대값)을 한 메서드로 합치지 않음. 검증된 #27 `upsert` 경로를 보존하면서 의도를 코드로 구분.
5. **offscreen에서 중첩 다이얼로그 실제 생성은 access violation 유발** — 부모-자식 다이얼로그를 헤드리스로 실제 띄우면 Qt teardown 중 segfault. 진입점(버튼→다이얼로그) 배선 테스트는 **자식 다이얼로그 클래스를 mock으로 대체**해 배선만 검증(PDCA #20/#23 모달 가드 계열 교훈 확장).
6. **DDL은 `IF NOT EXISTS` 추가만으로 무중단 마이그레이션** — 기존 운영 DB도 다음 기동 시 `_create_tables`가 신규 테이블/인덱스만 추가. QA1로 런타임 확인.

## 5. 후속 후보 (다음 PDCA)

1. 배합 기록 **수정/삭제 시 재고 원복**(+ 원복 이력 ADJUST). `MOVE_ADJUST` 상수 이미 예약됨.
2. 수동 편집(`upsert`)의 ADJUST 이력화 — 편집 전후 델타 계산 필요.
3. 발주(PO)·매입처 마스터·단가/금액.
4. 입출고 이력 Excel/PDF 내보내기(대시보드 export #25/#26 패턴 재사용).
5. 대시보드에 최근 입출고 요약 카드.

## 6. PDCA 상태

- Plan ✅ → Design ✅ → Do ✅ → Check ✅(99%) → (Iterate 불필요) → QA ✅ → Report ✅
- 다음 PDCA 번호: **#31**
- 커밋 대기. 메모리 `project_pdca_status`/`project_pdca_stock_alert` 갱신 대상.
