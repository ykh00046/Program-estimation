# PDCA #31 Gap 분석 — inventory_reversal_audit

> 대상: Design(`inventory_reversal_audit.design.md`) ↔ 구현
> 방법: 설계 항목별 구현 위치/동작 대조 + 테스트 통과로 동작 검증

## 1. 설계 항목 ↔ 구현 매핑

| # | 설계 항목 | 구현 위치 | 상태 |
|---|---|---|---|
| 2.1 | `apply_adjustment(items, note)` 저수준 메서드(부호 델타 + ADJUST 이력) | `material_stock_repository.py:146-205` | ✅ |
| 2.1 | `MAX(0, current+delta)` floor + rowcount>0 시만 이력 | 동 메서드 UPDATE/`_insert_history` | ✅ |
| 2.1 | delta==0/빈코드 스킵, 코드별 합산 | 동 메서드 totals 루프 | ✅ |
| 2.1 | `apply_consumption` 무변경(CONSUME 전용) | 미수정 확인 | ✅ |
| 3 | Facade 위임 `database.apply_adjustment` | `database.py:303-304` | ✅ |
| 4.1 | DataManager 위임 `apply_adjustment` | `data_manager.py` (apply_adjustment) | ✅ |
| 4.1 | `_norm_code` (code→name 폴백, 저장 차감과 동일) | `data_manager.py` | ✅ |
| 4.1 | `_reverse_inventory(details, note)` 원복(+), best-effort, 토글 게이트 | `data_manager.py` | ✅ |
| 4.1 | `_readjust_inventory(old, new)` 원복+재차감 2건 분리 기록 | `data_manager.py` | ✅ |
| 4.2 | `delete_record`: 삭제 전 상세 스냅샷 → 성공 시 원복 | `data_manager.py delete_record` | ✅ |
| 4.3 | `update_record`: 수정 전 old 스냅샷 → 성공 시 재정산 | `data_manager.py update_record` | ✅ |
| 1 | 스키마 변경 0(`material_stock_history` 재사용, ADJUST) | 신규 DDL 없음 | ✅ |

## 2. 요구사항 충족 (Plan §2)

| 요구사항 | 충족 근거 |
|---|---|
| 1. 삭제 시 원복(+) + ADJUST 이력 | `test_delete_restores_stock_with_adjust_history` (재고 100 복귀, ADJUST +30 1건) |
| 2. 수정 시 원복+재차감 = 자재당 2건 ADJUST | `test_update_increase_readjusts_with_two_adjust_entries` (quantities [-50,+30]) |
| 3. 모든 조정 MOVE_ADJUST + stock_after 스냅샷 | `apply_adjustment` `_insert_history(... MOVE_ADJUST, delta, stock_after ...)` |
| 4. 기존 회귀 0 | 전체 **247 passed** (기존 234 + 신규 13) |
| 5. MOVE_ADJUST 상수 활성화 | `material_stock_repository.py:16` 상수 → `apply_adjustment`에서 사용 |

## 3. 테스트 결과

- 신규 단위 `test_stock_adjustment.py`: 8 케이스(가산/차감/floor/합산/스킵/unknown/empty/consume 무회귀)
- 신규 통합 `test_inventory_reversal.py`: 5 케이스(삭제원복/수정증가2건/수정감소/토글off/best-effort)
- 신규 합계 13 passed, 전체 **247 passed / 0 failed**.

## 4. 엣지/리스크 검증

| 항목 | 결과 |
|---|---|
| 이중 원복 방지 | 삭제 1회성(레코드 제거 후 재호출 시 record None → False), 수정 old 스냅샷 1:1 상계 | 
| material_code 정규화 불일치 | `_norm_code`가 저장 차감과 동일 규칙(code→name) 재사용 |
| best-effort 실패 은폐 | `test_reversal_failure_does_not_block_delete`: apply_adjustment 예외에도 delete True + 레코드 삭제 확인 |
| 토글 off 무동작 | `test_toggle_off_skips_reversal_on_delete`: 재고 불변 + ADJUST 이력 0 |
| 0 floor | `test_negative_delta_clamps_at_zero` |

## 5. 결론

**Match Rate ≈ 100%.** 설계 12개 항목 전부 구현·검증됨. 미구현/이탈 항목 없음.
공개 API 시그니처 변경 0, 스키마 변경 0, 전체 회귀 0 → Act(개선 반복) 불필요, Report로 진행.
