# PDCA #31 Plan — inventory_reversal_audit

> 배합 기록 **수정/삭제 시 재고 원복 + 감사 로그(ADJUST)**
> 선행: #27(임계값 알림) · #29(저장 시 자동 차감 CONSUME) · #30(입고 INBOUND + 이력 추적)

## 1. 배경 / 문제

PDCA #29에서 배합 저장 시 자재 재고를 자동 차감(`CONSUME`, 부호 -)하고,
#30에서 입출고 이력(`material_stock_history`)을 도입했다. 그러나 현재:

- **배합 기록 삭제**(`DataManager.delete_record`) 시 차감됐던 재고가 **원복되지 않음**.
- **배합 기록 수정**(`DataManager.update_record`) 시 변경된 사용량이 재고에 **재반영되지 않음**.

→ 생산 기록을 지우거나 사용량을 줄여도 재고는 줄어든 채 고정되어,
**재고가 영구적으로 부족(과소 계상)** 되는 데이터 정합성 오류가 발생한다.

## 2. 목표 (요구사항)

1. **삭제 시 원복**: 삭제될 배합의 각 자재 `actual_amount`만큼 재고를 **가산(+)** 하고
   `material_stock_history`에 `MOVE_ADJUST`(부호 +) 1건씩 기록한다.
2. **수정 시 재정산**: 기존(저장 당시) 차감을 **원복(+)** 하고 새 사용량을 **차감(-)** 한다.
   자재당 **2건의 `MOVE_ADJUST` 이력**(원복 +, 재차감 -)을 남긴다.
3. 모든 원복/조정은 `material_stock_history`에 `MOVE_ADJUST`로 기록(`stock_after` 스냅샷 포함).
4. **기존 회귀 0**: 현행 테스트 스위트(≈232건) 전부 통과 유지.
5. `MOVE_ADJUST` 상수는 `material_stock_repository.py`에 이미 예약됨 — 이를 활성화한다.

## 3. 범위

### In scope
- `MaterialStockRepository`: 재고 가산/차감 + `MOVE_ADJUST` 이력 기록 저수준 메서드 신설.
- `database.py`(Facade) / `data_manager.py`(API) 위임 추가.
- `DataManager.delete_record` / `update_record`에 원복·재정산 오케스트레이션 삽입.
- 단위·통합 테스트 신설.

### Out of scope
- UI 변경 없음(삭제/수정은 기존 화면 흐름 그대로, 원복은 백그라운드 자동).
- `material_stock_history` 스키마 변경 없음(#30 정의 재사용, `change_type='ADJUST'`).
- 과거에 차감 없이 저장된 기록의 소급 보정(이번 범위 아님).

## 4. 핵심 설계 결정 (요지, 상세는 Design)

- **토글 일관성**: 원복/재정산은 저장 차감과 동일한 설정
  `inventory_alert.auto_deduct_on_save`로 게이트한다. 저장 시 차감하지 않았다면
  원복할 것도 없으므로 같은 스위치로 묶는 것이 정합적.
- **best-effort 보존**: 원복 실패가 생산 기록 삭제/수정을 **롤백시키지 않는다**
  (#29 철학: 생산 기록이 1순위 진실). 단 원복은 삭제/수정 트랜잭션과 **분리**된
  별도 트랜잭션으로 수행하고, 실패 시 경고 로그만 남긴다.
- **조회 시점**: 삭제는 레코드가 사라지기 **전에** 상세(`actual_amount`)를 스냅샷.
  수정은 **수정 전 old 상세**를 스냅샷한 뒤, 수정 후 new 사용량으로 재차감.

## 5. 성공 기준

- 삭제 후 해당 자재 재고가 차감 전 값으로 복귀(0 floor 영향 없는 정상 케이스).
- 수정(사용량 변경) 후 재고 = 초기 − new_amount(원복 +old, 재차감 −new 순효과).
- `get_stock_history`에 ADJUST 이력이 부호/스냅샷과 함께 기록됨.
- `apply_consumption`/`add_inbound`/임계값 알림 동작·반환계약 불변.
- 전체 테스트 회귀 0, 신규 테스트 통과.

## 6. 리스크

| 리스크 | 대응 |
|---|---|
| 원복으로 재고가 실제 입고분을 초과 가산(이중 원복) | 삭제는 1회성(레코드 제거 후 재호출 불가), 수정은 old 스냅샷 기반 1:1 상계 |
| material_code 정규화 불일치(저장 시 code-or-name 폴백) | 저장 차감과 **동일한 정규화 규칙** 재사용(`code or name`) |
| best-effort 원복 실패 은폐 | 경고 로그 + 이력 부재로 추적 가능, 트랜잭션 분리로 기록 일관성 유지 |
