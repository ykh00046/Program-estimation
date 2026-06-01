# PDCA #30 Analysis — inventory_inbound_history (Gap 분석)

> 분석일: 2026-06-02 · gap-detector 독립 검증 · 전체 232 테스트 그린 전제

## 종합

| 항목 | 결과 |
|---|---|
| 설계 일치도 (R1~R6) | 6/6 충족 (100%) |
| 무회귀 보증 (§7) | 4/4 충족 |
| 누락(Missing) / 불일치(Changed) | 0 / 0 |
| **종합 Match Rate** | **≈ 99% (실질 100%)** |
| Iterate 필요 | ❌ (≥ 90%) |

## 요구사항 판정

| # | 요구 | 구현 위치 | 판정 |
|---|---|---|:---:|
| R1 | 입고 누적 가산 + 신규 생성 | `material_stock_repository.add_inbound` (`ON CONFLICT ... current_stock + excluded.current_stock`) | ✅ |
| R2 | 이력 영속화(8컬럼) | `database._create_tables` material_stock_history + `_insert_history` | ✅ |
| R3 | 자동 차감 CONSUME 이력 + 반환값 불변 | `apply_consumption` (rowcount>0 블록 내 순수 가산, 동일 트랜잭션) | ✅ |
| R4 | 입고 등록 UI | `ui/dialogs/inbound_dialog.py` + StockSettings "입고 등록" 버튼 | ✅ |
| R5 | 이력 조회 UI(6열+필터) | `ui/dialogs/stock_history_dialog.py` + "입출고 이력" 버튼 | ✅ |
| R6 | 무회귀 | 232 passed(214→+18), 회귀 0 | ✅ |

## 핵심 검증 포인트

1. **`apply_consumption` 반환 계약 보존** — `updated` 누산 경로 무수정, 이력 INSERT는 `if cursor.rowcount:` 내부 순수 가산. `test_consumption_records_negative_history`가 `updated==1` + `quantity==-40.0` + `stock_after==60.0` 가드.
2. **키 해석 일관성** — `add_inbound`/`upsert`(`(code or name).strip()`), `seed`(`COALESCE(NULLIF(TRIM(code),''),name)`), `consume`(code-only) 모두 동일 키를 생성/매칭 → 데드 매칭 위험 없음.
3. **§7 무회귀 4항목** — material_stock 관련 기존 API·DDL 불변, `_create_tables`는 `IF NOT EXISTS` 추가만(기존 DB 자동 마이그레이션), 신규 공개 메서드만 추가(시그니처 변경 0).

## 사소 관찰 (갭 아님, 설계 허용 범위)

- 테스트는 신규 파일 대신 기존 `test_material_stock_db.py`(StockInboundHistoryTests) + `test_inventory_dialog_smoke.py`에 통합 — 설계 §6이 "또는 기존 확장" 허용. 케이스 ①~⑥ 모두 커버.
- `_type_color`에 `qty>0/<0` 보조 폴백 추가(강건성), UITheme `SUCCESS_COLOR`/`ERROR_COLOR`만 사용(민트/틸 금지 준수).

## 결론

DoD(Match ≥ 90%) 충족. `[Check]` 통과 → Report 진행.
