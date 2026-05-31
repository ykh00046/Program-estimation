# 자재 재고 임계값 알림 (PDCA #27)

> feature: `inventory_threshold_alert`
> 작성일: 2026-06-01 · 갱신: 2026-06-01(재고 모델로 재정렬) · Level: Starter
> 선행: PDCA #17(대시보드)/#25(export)/#26(차트)

## 1. 배경

PDCA #17 대시보드가 자재 사용량 집계(`get_top_materials`)를 제공하나, 자재 재고가
부족해도 사용자가 능동적으로 인지할 수단이 없다. 사용자가 자재별 **최소 재고 임계값**을
설정하고, 현재 재고가 그 이하로 떨어지면 대시보드에 **알림 카드**로 능동 경고한다.

## 2. 핵심 결정 — 경량 수동 재고 모델 (Plan 재정렬, 2026-06-01)

- 사용자 요구사항(1~4)은 명확한 **재고(stock) 의미론**이다: `min_stock_threshold`,
  "현재 재고가 임계값 이하로 떨어지면", "부족분(shortfall) 표시".
- 단, 현 시스템에는 입고/재고 데이터가 없다(`actual_amount`=사용량만 존재).
- **결정**: 입고/발주 플로우 없이, 자재별 **현재 재고(`current_stock`)** 와
  **최소 임계값(`min_stock_threshold`)** 을 설정 다이얼로그에서 **수동 입력**하는
  경량 재고 모델을 도입한다. 5개 요구사항을 문자 그대로 충족하면서 스코프 폭발을 막는다.
- 알림 조건: `current_stock <= min_stock_threshold`(임계값 > 0인 자재만).
  부족분 `shortfall = max(0, threshold - current_stock)`.
- 레벨: `OUT_OF_STOCK`(현재고 ≤ 0) / `LOW_STOCK`(0 < 현재고 ≤ 임계값) / `OK`(제외).

## 3. 범위 (In Scope)

### Part A — 데이터 모델 (`models/database.py` + `models/data_manager.py`)
- 신규 테이블 `material_inventory`(mixing DB): `material_code`(PK), `material_name`,
  `current_stock`(REAL), `min_stock_threshold`(REAL), `updated_at`.
  `SqliteManagerBase` 패턴 준수(PDCA #18).
- DB 메서드: `get_material_inventory()`, `set_material_inventory(code, name, stock, threshold)`,
  `delete_material_inventory(code)`. `data_manager` 위임 래퍼 동반.

### Part B — 평가 순수 로직 (`models/inventory_alert.py` 신설)
- `evaluate_inventory_alerts(inventory_rows)` → `List[MaterialAlert]`.
  - 입력: 재고 행(`get_material_inventory` 결과 형태).
  - 출력: `MaterialAlert(material_code, material_name, current_stock, threshold, shortfall, level)`.
  - 임계값 ≤ 0(미설정) 자재 제외, `OK` 제외. 부족분 큰 순 정렬.
- **Qt·DB 무의존 → 단독 단위 테스트** (메모리 교훈: 순수 변환부 분리).

### Part C — UI 연동 (`ui/panels/dashboard_panel.py` + `ui/dialogs/`)
- 대시보드 상단에 **알림 카드 배너**(부족/품절 자재). 경고 0건 시 숨김.
- 각 카드: 자재명, 현재 재고, 임계값, 부족분 표시(요구사항 4). 단위 g.
- "재고 설정" 버튼 → `MaterialInventoryDialog`: 기존 사용 자재 자동 목록 + 현재고/임계값
  입력·저장·삭제. 저장 후 대시보드 `refresh()` 재평가(요구사항 3).
- 알림은 기간 비의존(현재 재고 기준) → `refresh()` 시 항상 재평가.

### Part D — 테스트
- 단위: `evaluate_inventory_alerts` 경계값(OUT/LOW/OK, 미설정 제외, 빈 입력, 정렬).
- 단위: DB CRUD(임시 DB, `LEGACY_DB_PATH` 패치) round-trip.
- 스모크: 패널 알림 배너 표시/숨김, 다이얼로그 생성(offscreen, QMessageBox patch).

## 4. 비-범위 (Out of Scope)
- 입고/발주/재고 자동 차감(사용량 연동) 관리.
- 임계값 초과 시 이메일/푸시 등 외부 알림.
- 자재 마스터(단가/규격) 관리.
- 임계값/재고 변경 이력·감사 로그.

## 5. 성공 기준
1. 현재고·임계값 설정→저장→재시작 후 유지(DB 영속).
2. 현재고가 임계값 이하일 때 대시보드 알림 카드에 정확히 분류·부족분 표시.
3. 임계값 미설정/경고 0건 시 배너 비표시(잡음 0).
4. 전체 테스트 스위트 회귀 0건, 신규 테스트 통과.
5. gap-detector Match ≥ 90%.

## 6. 위험 & 완화
| 위험 | 완화 |
|---|---|
| "재고" 용어로 입고관리 기대 | 수동 입력 경량 모델로 한정, 입고/발주는 비-범위 명시 |
| 단위 혼동(g) | 다이얼로그·카드에 단위 g 명시, 기존 KPI(총 배합량 g)와 일치 |
| 신규 테이블 마이그레이션 | `CREATE TABLE IF NOT EXISTS`, 기존 DB 무영향 |
| 옵셔널 의존 | 신규 의존 없음(Qt 기존 범위) |
| 모달 다이얼로그 스모크 hang | offscreen 가드(#20/#21) + QMessageBox patch(#23) |
| 기존 패널 테스트 회귀 | mock DM에 `get_material_inventory` 추가, 알림 refresh는 안전 가드 |

## 7. 커밋 계획
1. `feat(models): material_inventory 테이블 + CRUD` (Part A)
2. `feat(models): evaluate_inventory_alerts 순수 평가 로직` (Part B)
3. `feat(ui): 대시보드 재고 알림 배너 + 설정 다이얼로그` (Part C)
4. `test: 평가 로직/CRUD/패널·다이얼로그 스모크` (Part D)
5. `docs: PDCA #27 analysis + report`

## 8. 다음 단계
→ `/pdca design inventory_threshold_alert`
