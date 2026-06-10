# 재고 정합성 검사·보정 — Gap 분석

> PDCA Feature: `inventory_reconcile` (PDCA #34)
> 분석일: 2026-06-10 · 도구: gap-detector Agent
> 설계: `docs/02-design/features/inventory_reconcile.design.md`

## 1. 분석 요약

| 구분 | 내용 |
|------|------|
| Match Rate | **~99.5%** (1차 통과, iterate 불필요) |
| 미구현 | 0건 |
| 테스트 | 321개 전부 통과 (기존 295 + 신규 26, 회귀 0) |

## 2. 항목별 검증 결과

| 설계 항목 | 점수 | 비고 |
|-----------|:---:|------|
| §1 불변식·note 포맷 상수 | 100% | 6종 상수 + LIKE 정확 매칭 일치 |
| §2.1 Repository 계약 (a)~(e) | 98% | 유일 ⚠️: record_reconcile_entry drift 산출이 _LEDGER_QUERY 공유 대신 단건 조회 — 기준(`created_at DESC, id DESC`) 동일, 결과 비트-동일 |
| §2.2 Facade 순수 위임 | 100% | 무데코레이터 passthrough (#28 규약) |
| §2.3 DataManager | 100% | LOT note 전달, _norm_code 재사용, retro_deduct_lots |
| §2.4 UI | 100% | 2섹션 구성, 기본 7일, 모든 보정 확인 게이트, UITheme 토큰만 |
| §3 오류 처리 | 100% | |
| §4 테스트 커버 | 100% | 설계 9 카테고리 전부 + 취소 경로 보강 |
| §6 호환성 | 100% | 스키마 변경 0, 기존 계약 비트 보존 |

## 3. 의도적 변경 (설계에 반영 완료)

1. **upsert 이력화 → `log_history` opt-in 파라미터**: Do 중 기존 테스트들이 upsert를
   셋업으로 쓰며 이력 건수를 단언하는 것을 발견 — 무조건 이력화는 광범위 회귀.
   수동 편집의 유일한 진입점인 DataManager 위임에서 `log_history=True` 고정으로
   다이얼로그 경로만 감사 추적. 설계 §2.1(a)에 근거와 함께 역반영됨.
2. 추가 상수화: `MANUAL_EDIT_NOTE`, `LEDGER_TOLERANCE` (+`__all__` export).
3. 버튼 라벨 서술 보강("장부 정렬 (재고 불변)" 등) — 설계 미고정, 의미 동일.

## 4. 선택적 개선 (차기 후보, 기능 영향 없음)

- `record_reconcile_entry`와 `check_ledger_consistency`의 "최근 stock_after" 산출을
  단일 헬퍼로 묶어 정렬 기준 SSOT 단일화 (현재 두 곳 모두 동일 기준이라 무해).

## 5. 결론

미구현 0건, 실질 갭 0건. **Match Rate ~99.5% (≥90%)** → `/pdca report inventory_reconcile` 진행.
