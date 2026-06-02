# PDCA #31 완료 보고서 — inventory_reversal_audit

> 배합 기록 **수정/삭제 시 재고 원복 + 감사 로그(ADJUST)**
> 사이클: Plan → Design → Do → Check(Gap≈100%) → Report
> 일자: 2026-06-02

## 1. 요약

배합 기록을 삭제하거나 수정해도 #29에서 차감(`CONSUME`)된 자재 재고가 원복되지 않아
**재고가 영구 과소 계상**되던 정합성 오류를 해결했다. 삭제 시 차감분을 원복(+)하고,
수정 시 기존 차감을 원복(+)한 뒤 새 사용량을 재차감(-)하여, 모든 조정을
`material_stock_history`에 `MOVE_ADJUST`(부호 있는 델타 + `stock_after` 스냅샷)로 감사 기록한다.

## 2. 변경 내역

| 레이어 | 파일 | 변경 |
|---|---|---|
| Repository | `models/repositories/material_stock_repository.py` | `apply_adjustment(items, note)` 신규 — 부호 델타 적용 + MOVE_ADJUST 이력 |
| Facade | `models/database.py` | `apply_adjustment` 위임 추가 |
| API | `models/data_manager.py` | `apply_adjustment` 위임 + `_norm_code`/`_reverse_inventory`/`_readjust_inventory` 헬퍼; `delete_record`·`update_record`에 원복·재정산 오케스트레이션 삽입 |
| Test | `tests/unit/test_stock_adjustment.py` (신규) | apply_adjustment 8 케이스 |
| Test | `tests/integration/test_inventory_reversal.py` (신규) | 삭제/수정 오케스트레이션 5 케이스 |
| Docs | `docs/01-plan`·`02-design`·`03-analysis`·`04-report` | PDCA 문서 |

## 3. 핵심 설계 결정

1. **단일 저수준 메서드(`apply_adjustment`)로 ±델타 통합** — 원복(+)·재차감(-)을 한 메서드로
   처리. `apply_consumption`(CONSUME 전용)은 무변경하여 #29 회귀 0.
2. **수정은 순효과(net)가 아닌 원복+재차감 2건으로 분리 기록** — 감사 추적상
   "되돌린 양"과 "새로 반영한 양"이 명확. delta==0 자재는 Repository에서 자동 스킵.
3. **저장 차감과 동일 토글(`auto_deduct_on_save`)로 게이트** — 차감하지 않았으면 원복도 없음(정합).
4. **best-effort + 분리 트랜잭션** — 원복 실패가 삭제/수정을 롤백시키지 않음(생산 기록 1순위).
5. **삭제 전/수정 전 상세 스냅샷** — 삭제 후엔 mixing_details가 사라지므로 사전 조회 필수.

## 4. 검증 결과

- 전체 테스트: **247 passed / 0 failed** (기존 234 + 신규 13, 회귀 0).
- Gap 분석: 설계 12개 항목 100% 구현, Match ≈ 100%.
- 동작 시나리오(재고 100, 30 사용):
  - 삭제 → 100 복귀 (ADJUST +30 1건)
  - 수정 30→50 → 50 (ADJUST +30, -50 2건)
  - 토글 off → 불변, best-effort 실패 → 삭제 정상.

## 5. 무회귀 보증

- `apply_consumption`/`add_inbound`/`get_stock_history`/임계값 알림 동작·반환계약 불변.
- `delete_record`/`update_record` 시그니처·반환(bool) 불변(내부 보강만).
- 스키마 변경 0(`material_stock_history` 재사용).

## 6. 교훈 / 후속 후보

- **교훈**: 자동 차감 도입 시 "역연산(원복)"을 같은 사이클에서 설계하지 않으면 데이터가
  단방향으로 누적 편향된다. CONSUME/INBOUND/ADJUST가 이제 모든 재고 변동을 커버한다.
- **후속 후보**:
  1. ADJUST 이력의 UI 노출(이미 `StockHistoryDialog`에 "조정" 라벨 예약됨 — #30) 확인/스모크.
  2. 과거에 차감 없이 저장된 기록의 소급 정합 보정(opt-in 일괄 재계산) — 별도 PDCA.
  3. 동일 자재 LOT 단위 추적(현재 코드 단위) — 장기 과제.

## 7. 상태

✅ **완료** — Act(개선 반복) 불필요(Gap≥90%). 다음 PDCA는 #32부터.
