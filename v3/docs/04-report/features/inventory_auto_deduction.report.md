# PDCA #29 Report (Act) — 배합 저장 시 자동 재고 차감

> **사이클**: #29 (사용자 가치) · **날짜**: 2026-06-02 · **Match**: ~100% · **테스트**: 214 passed
> Plan/Design/Analysis: `docs/{01-plan,02-design,03-analysis}/features/inventory_auto_deduction.*`

## 1. 한 줄 요약

#27 재고 알림이 수동/seed 재고에만 의존하던 "반쪽" 상태를, **배합 저장 시 실제 사용량 자동 차감**으로
연결해 알림이 실시간으로 동작하게 만들었다.

## 2. 변경 산출물

| 파일 | 변경 |
|---|---|
| `models/repositories/material_stock_repository.py` | `apply_consumption(consumption) -> int` 신규 (합산/클램프/미존재 skip, 단일 트랜잭션) |
| `models/database.py` | Facade 무데코 위임 `apply_consumption` |
| `models/data_manager.py` | `save_record`에 차감 스텝 1줄 + `_deduct_inventory`(best-effort) + `get/set_auto_deduct_on_save` 토글 |
| `ui/dialogs/stock_settings_dialog.py` | "배합 저장 시 재고 자동 차감" 체크박스 + 로드/저장 (getattr 가드) |
| `tests/unit/test_material_stock_db.py` | `apply_consumption` 단위 6건 |
| `tests/integration/test_inventory_auto_deduction.py` | 오케스트레이션/토글 5건 (신규 파일) |
| `tests/integration/test_inventory_dialog_smoke.py` | 체크박스 스모크 2건 |

## 3. 핵심 동작

- **차감 규칙**: details의 `actual_amount`를 `material_code`(없으면 `material_name` 폴백) 기준 합산 →
  `current_stock = MAX(0, current_stock - amt)`. 마스터에 **있는 자재만** 갱신(미존재는 생성 안 함).
- **트랜잭션 분리**: 생산 기록 저장(트랜잭션 A)과 재고 차감(트랜잭션 B)을 분리. 차감 실패는
  `logger.warning`만 남기고 저장을 롤백하지 않는다 — 생산 기록(DHR)이 1순위 진실.
- **토글**: `config["inventory_alert.auto_deduct_on_save"]`(기본 True). 재고 설정 다이얼로그 체크박스로 on/off.

## 4. 결과

- 전체 스위트 **214 passed**(201 → +13: 단위 6 + 통합 5 + 스모크 2), 회귀 0.
- 요구사항 R1~R6 6/6 충족, 설계-구현 일치 100%.

## 5. 교훈 (durable)

1. **부수 효과는 best-effort 트랜잭션 분리** — 재고 차감처럼 "있으면 좋은" 파생 갱신은 1순위 영속화
   (생산 기록)와 트랜잭션을 분리하고 try/except로 감싸 실패가 본 저장을 막지 않게 한다.
   `_backup_to_google_sheets`와 동일 패턴 → `save_record`가 "저장 + 백업 + 차감" 오케스트레이터로 일관.
2. **오케스트레이션 seam 선택이 테스트 격리를 좌우** — 차감을 Facade `save_mixing_record`가 아닌
   애플리케이션 서비스(`data_manager.save_record`)에 두어, `db.save_mixing_record`를 직접 부르는
   기존 단위/DHR 테스트와 무관하게 유지(영향 0).
3. **차감 키는 마스터 적재 키와 동일 규칙으로 해석** — seed/upsert가 `TRIM(code) or name`으로 키를
   만들므로 차감도 동일 폴백을 써야 매칭된다. 규칙 불일치는 "조용한 미차감"(데드 매칭)을 낳는다 — #27의
   SQL↔순수함수 parity 교훈과 같은 계열.
4. **무거운 의존 객체는 `__new__`로 우회 후 협력자만 주입** — DataManager(GSheets/Excel/Excel 로드)를
   `__new__`로 만들고 `db_manager`만 임시 DB로 주입해 오케스트레이션 메서드를 격리 단위 검증.
5. **fake 협력자 호환은 getattr 가드** — 다이얼로그가 신규 dm 메서드(`get/set_auto_deduct_on_save`)에
   의존할 때 `getattr(dm, name, default)`로 감싸면 기존 fake/MagicMock dm 테스트가 깨지지 않는다.

## 6. 후속 후보

1. **배합 기록 수정/삭제 시 재고 원복** — 현재는 신규 저장 차감만. 삭제 시 `actual_amount` 환원, 수정 시 차분 조정.
2. **입고/발주 관리** — 재고 증가 경로(현재 수동 upsert만).
3. **차감 이력 로그/감사** — 언제 무엇이 얼마 차감됐는지 추적 테이블.
4. **저재고 즉시 토스트** — 저장 직후 차감 결과로 임계값 하회 시 즉시 알림(현재는 대시보드 새로고침 시).

## 7. 커밋

- `feat(inventory): 배합 저장 시 자재 재고 자동 차감 (PDCA #29)` — 구현 4파일
- `test(inventory): apply_consumption + 오케스트레이션/토글 테스트 (PDCA #29)` — 테스트 3파일
- `docs: PDCA #29 inventory_auto_deduction (plan/design/analysis/report)` — 문서 4파일
