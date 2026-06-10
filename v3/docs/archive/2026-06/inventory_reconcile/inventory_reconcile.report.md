# 재고 정합성 검사·보정 (Inventory Reconcile) — 완료 보고서

> PDCA Feature: `inventory_reconcile` (**PDCA #34**)
> 기간: 2026-06-10 (1일) · 최종 Match Rate: **~99.5%** (1차 통과) · 테스트: **321/321**

## 1. 무엇을 해결했나

전체 검토(2026-06-10)의 High 이슈 — 배합 저장(트랜잭션)과 재고 차감(best-effort 분리)
사이의 부분 실패로 생기는 **"기록은 있는데 차감 안 됨" 상태를 발견·복구할 수단 부재** — 를
해소했다. 동시에 향후 드리프트의 두 근원을 제거했다:

| 근원 | Before | After |
|------|--------|-------|
| 수동 편집 무이력 (F1) | 재고 설정 다이얼로그 저장이 이력 없이 재고 변경 → 장부 체인 단절 | DataManager 경로 `log_history=True` — 변경분이 ADJUST "수동 편집" 이력으로 기록 |
| LOT 무연결 (F2) | CONSUME note 고정 문자열 → 어떤 기록이 차감됐는지 역추적 불가 | note에 `(LOT {lot})` 마커 — 미차감 검출·중복 방지의 근거 |

## 2. 구현 내역

### 검사 2종 + 보정 2종 (`ReconcileDialog`, 재고 설정 허브 "정합성 검사" 버튼)

| 기능 | 메커니즘 |
|------|----------|
| 검사 1: 장부 일관성 | 불변식 `current_stock == 최근 history.stock_after`(없으면 0) 위반 자재 검출. clamp(MAX 0) 때문에 Σquantity replay가 아닌 **stock_after 체인** 기준 (핵심 설계 결정) |
| 보정 1: 장부 정렬 | **재고 불변** — 현재고를 진실로 보고 ADJUST 이력 1건(drift)으로 체인 복구 (`record_reconcile_entry`) |
| 검사 2: 미차감 의심 LOT | 기간 내(기본 7일) `mixing_records` 중 이력 note에 LOT 마커 없는 기록 — 단일 SQL `NOT EXISTS ... LIKE '%(LOT ' \|\| lot \|\| ')%'` |
| 보정 2: 선택 소급 차감 | 체크한 LOT의 상세 사용량을 `apply_adjustment(-)`로 차감, note에 LOT 마커 → **재검출 자동 제외 (중복 적용 방지)** |

모든 보정은 사용자 확인(QMessageBox) 후에만 실행 — 자동 보정 금지.

### 계약 보존
- `apply_consumption(note=...)` / `upsert(log_history=...)` 기본값이 기존 동작 비트 보존
- 스키마 변경 0 (기존 `material_stock_history` ADJUST 재사용)
- Facade 무데코레이터 위임(#28), `_norm_code` 재사용(#31)으로 차감 키 일치 보장

## 3. PDCA 사이클 기록

| 단계 | 결과 |
|------|------|
| Plan | 코드 사실 4종(F1~F4) 기반 문제 재정의 — "reconcile"을 장부 체인 검사 + LOT 마커 검출로 구체화 |
| Design | note 포맷 상수 SSOT, 검사/보정 4기능, 회귀 보존 전략 |
| Do | Repository 5변경 + Facade/DM 위임 + ReconcileDialog 신규 + 테스트 26개 |
| Do 중 수정 | upsert 무조건 이력화 → 기존 테스트 회귀 발견 → **opt-in 파라미터로 전환** (설계 역반영) |
| Check | **~99.5% 1차 통과** — 미구현 0, iterate 불필요 |

## 4. 교훈 (Lessons Learned)

1. **이력 quantity replay는 함정**: clamp(MAX 0)가 있으면 요청량과 실제 변화량이 달라
   Σquantity로 현재고를 복원할 수 없다. append-only 로그에 **사후 스냅샷(stock_after)** 을
   남겨둔 #30의 설계 덕에 체인 비교가 가능했다 — 이동 로그에는 항상 사후 상태를 함께 기록할 것.
2. **공용 저수준 메서드의 동작 변경은 opt-in부터**: upsert는 시드·테스트 셋업·다이얼로그가
   공유하는 진입점 — 무조건 이력화는 "셋업이 이력을 오염"시키는 광범위 회귀였다.
   동작 추가는 파라미터 opt-in + 의미 있는 진입점(DataManager)에서만 켜는 패턴이 안전.
3. **note 필드의 구조화된 마커**: 스키마 변경 없이 LOT 역추적을 얻는 실용 절충.
   포맷을 상수(SSOT)로 고정하고 LIKE 매칭과 짝지어야 파싱 취약성이 통제된다.
   (차후 LOT 추적성 사이클에서 정식 컬럼으로 승격 후보)

## 5. 후속 과제

- **#35 백업 견고화**: Sheets 컬럼 매핑 고정 + 실패 재시도 큐 (전체 검토 High 잔여)
- stock_after 산출 헬퍼 단일화 (선택, gap-detector 권고)
- LOT 양방향 추적성 — note 마커를 정식 컬럼/조회 화면으로 승격 (혁신 1순위와 합류)
- StockHistoryDialog에 "수동 편집"/"소급 차감" 라벨 노출 검토

## 6. 산출물

- 코드: `material_stock_repository.py`(+검사/보정 3메서드, 상수 6종), `database.py`,
  `data_manager.py`(retro_deduct_lots 등), `reconcile_dialog.py`(신규), `stock_settings_dialog.py`
- 테스트: `test_inventory_reconcile.py`(19) + `test_reconcile_dialog_smoke.py`(7) — 총 321 통과
- 문서: plan / design / analysis / report
