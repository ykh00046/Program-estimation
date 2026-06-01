# PDCA #29 — 배합 저장 시 자동 재고 차감 (inventory_auto_deduction)

> **사이클**: PDCA #29 (사용자 가치)
> **날짜**: 2026-06-02
> **선행**: #27 `inventory_threshold_alert`(재고 알림), #28 `database_repository_split`(Repository 분해)

## 1. 배경 / 문제

PDCA #27에서 **자재 재고 임계값 알림**(대시보드 부족 알림 카드 + 재고 설정 다이얼로그)을 도입했다.
그러나 현재 `material_stock.current_stock`은 **수동 입력 / `seed_material_stock_from_history`(0으로 시드)** 로만 관리된다.
즉 배합을 아무리 저장해도 현재고가 줄지 않아 **알림이 실시간으로 동작하지 않는** "반쪽" 상태다.

`material_stock` 테이블·CRUD·순수 판정 함수(`evaluate_inventory_alerts`)·`MaterialStockRepository`(#28에서 분리)는
이미 갖춰져 있어, **"배합 저장 시 사용량만큼 자동 차감"** 한 스텝만 추가하면 재고 알림이 비로소 살아난다.

## 2. 목표 (What)

배합 기록을 저장(`DataManager.save_record`)할 때, 각 자재의 **실제 배합량(`actual_amount`)** 만큼
`material_stock.current_stock`을 **자동 차감**한다. 결과적으로 재고가 임계값 이하로 떨어지면
대시보드 부족 알림이 자동으로 뜬다.

### 요구사항

| # | 요구사항 |
|---|---|
| R1 | 배합 저장 성공 시, 각 자재의 `actual_amount` 합계만큼 해당 자재 `current_stock` 차감 |
| R2 | 같은 자재가 상세에 여러 번 등장하면 **합산**하여 1회 차감 |
| R3 | 차감 결과가 음수면 **0으로 클램프**(현재고는 0 미만 불가 — 기존 `upsert` 클램프 컨벤션 준수) |
| R4 | 재고 마스터에 **없는 자재는 생성하지 않고 건너뜀**(기준 재고를 알 수 없으므로). 추후 `seed`/수동 입력으로 합류 |
| R5 | 차감은 **배합 저장(생산 기록)의 부수 효과** — 차감 실패가 생산 기록 저장을 롤백시키면 안 됨(생산 기록이 1순위 진실, DHR 법적 자료) |
| R6 | 설정 토글 `inventory_alert.auto_deduct_on_save`(기본 **True**)로 자동 차감 on/off. 재고 설정 다이얼로그에 체크박스 제공 |

## 3. 비목표 (Out of scope)

- 입고/발주/구매 관리 — 차감만 다룬다(증가는 수동 `upsert`).
- 배합 기록 **수정/삭제 시 재고 원복** — 본 사이클은 신규 저장 차감만. (후속 후보)
- 음수 재고 허용(과소비 추적) — 클램프 0 유지.
- Google Sheets 재고 동기화.

## 4. 접근 (How) — 개요

1. **Repository 핵심 로직**: `MaterialStockRepository.apply_consumption(consumption) -> int`
   - 입력: `[{"material_code", "actual_amount"}, ...]`
   - 코드별 합산 → 단일 트랜잭션 → 기존 행만 `current_stock = max(0, current_stock - amt)` UPDATE
   - 반환: 실제 갱신된(=마스터에 존재하는) 자재 수
2. **Facade 위임**: `MixingDatabaseManager.apply_consumption` (무동작 위임 래퍼, #28 패턴)
3. **오케스트레이션**: `DataManager.save_record` 성공 후 `_deduct_inventory(details_data)` 호출(비-치명, try/except)
4. **설정 토글**: `DataManager.get/set_auto_deduct_on_save` + `StockSettingsDialog` 체크박스

> **왜 data_manager 오케스트레이션인가**: 저장 경로의 애플리케이션 서비스 계층. `save_mixing_record`(Repository/Facade)에 직접
> 넣으면 `db.save_mixing_record`를 직접 호출하는 기존 테스트·DHR 경로까지 영향을 받는다.
> `_backup_to_google_sheets`와 동일하게 **best-effort 부수 효과**로 배치하는 것이 R5(생산 기록 우선)와 SRP에 부합.

## 5. 영향 파일

| 파일 | 변경 |
|---|---|
| `models/repositories/material_stock_repository.py` | `apply_consumption` 추가 |
| `models/database.py` | Facade 위임 `apply_consumption` 추가 |
| `models/data_manager.py` | `save_record`에 차감 스텝 + `_deduct_inventory` + 토글 getter/setter |
| `ui/dialogs/stock_settings_dialog.py` | "배합 저장 시 재고 자동 차감" 체크박스 |
| `tests/unit/test_material_stock_db.py` | `apply_consumption` 단위 테스트 |
| `tests/integration/` | 저장→차감 오케스트레이션 테스트 |

## 6. 리스크

| 리스크 | 완화 |
|---|---|
| 차감 실패가 저장을 롤백 | 별도 트랜잭션 + best-effort(R5) |
| 자재코드 키 불일치(마스터 seed 규칙과) | data_manager에서 `code = (material_code or '').strip() or material_name` 동일 해석 후 전달 + repo 방어적 skip |
| UI 추가로 offscreen 모달 hang | 다이얼로그 스모크에서 QMessageBox/exec patch(#23/#24 교훈) |
| 음수/0 차감 오삽입 | 비양수 금액·빈 코드 skip |

## 7. 완료 기준 (DoD)

- [ ] `apply_consumption`: 합산/클램프/미존재 skip/비양수 skip 단위 테스트 통과
- [ ] 저장→차감 오케스트레이션 테스트(토글 on/off) 통과
- [ ] 전체 스위트 회귀 0 (기존 201 passed 유지 + 신규)
- [ ] 재고 설정 다이얼로그 스모크 통과
- [ ] gap-detector Match ≥ 90%
