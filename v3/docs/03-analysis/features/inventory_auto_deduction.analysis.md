# PDCA #29 Analysis (Check) — 자동 재고 차감

> Plan/Design 대비 구현 Gap 분석. 방법: 설계 항목 ↔ 구현 직접 대조 + 전체 테스트.

## 1. 요구사항 충족 (Plan §2)

| # | 요구사항 | 구현 | 근거 | 상태 |
|---|---|---|---|---|
| R1 | 저장 시 actual_amount만큼 차감 | `DataManager.save_record` → `_deduct_inventory` → `apply_consumption` | data_manager.py:193, repository UPDATE | ✅ |
| R2 | 중복 자재 합산 1회 차감 | `totals` dict 합산 | material_stock_repository.py `apply_consumption` | ✅ (`test_apply_consumption_aggregates_duplicate_codes`) |
| R3 | 음수 → 0 클램프 | `MAX(0, current_stock - ?)` | SQL | ✅ (`test_apply_consumption_clamps_at_zero`) |
| R4 | 미존재 자재 미생성·skip | UPDATE only (INSERT 없음), rowcount 집계 | SQL | ✅ (`test_apply_consumption_skips_unknown_material`) |
| R5 | 차감 실패가 저장 롤백 금지 | 별도 트랜잭션 + `_deduct_inventory` try/except | data_manager.py | ✅ (`test_deduction_failure_is_swallowed`) |
| R6 | 설정 토글 + 다이얼로그 체크박스 | `get/set_auto_deduct_on_save` + `auto_deduct_check` | data_manager / stock_settings_dialog | ✅ (smoke 2건) |

**요구사항 6/6 충족.**

## 2. 설계 항목 대조 (Design)

| Design 항목 | 구현 여부 | 비고 |
|---|---|---|
| `apply_consumption(consumption) -> int` 시그니처·동작 | ✅ | 설계 의사코드와 비트-동일 |
| `@handle_exceptions(default_return=0)` | ✅ | Repo 1회 예외처리(#28 패턴) |
| Facade 무데코 위임 | ✅ | database.py `apply_consumption` |
| `save_record` 백업 직후 1줄 삽입 | ✅ | `_backup_to_google_sheets` 다음 줄 |
| `_deduct_inventory` 코드 폴백(`material_code or material_name`) | ✅ | seed/upsert 키 규칙 정합 (`test_blank_code_falls_back_to_material_name`) |
| 토글 기본 True | ✅ | `config.get(..., True)` |
| 다이얼로그 체크박스 + getattr 가드 | ✅ | fake dm 호환 |

**설계-구현 일치율 100%, 미구현/이탈 0.**

## 3. 비목표 준수 (Plan §3)

- 입고/발주 미구현 ✅ / 수정·삭제 원복 미구현(후속 후보) ✅ / 음수 재고 미허용 ✅ / GSheet 재고동기화 없음 ✅

## 4. 회귀 / 테스트

- 전체 스위트: **214 passed**(이전 201 → +13: 단위 6 + 통합 5 + 스모크 2), 회귀 0, 8s 내.
- 기존 `material_stock` CRUD/`save_mixing_record`/Facade 시그니처 불변(추가만) → 기존 테스트 영향 0.

## 5. 잔여 리스크 / 관찰

- **수정·삭제 시 재고 원복 부재**: 잘못 저장 후 기록을 삭제해도 재고는 복구되지 않음 → 후속 후보(R5 범위 명시 제외).
- **레시피 Excel 코드 vs DB 코드 정합**: 차감 키는 details의 `품목코드`(없으면 품목명) — seed/upsert와 동일 규칙이라 마스터와 정합. 다만 사용자가 수동 upsert로 다른 코드를 넣으면 매칭 실패(미존재 skip). 이는 R4 설계 동작(안전).
- **동시성**: 단일 인스턴스 데스크톱 앱이라 차감 UPDATE 경쟁 없음.

## 6. 판정

**Match Rate ≈ 100%** (요구 6/6 + 설계 일치 + 회귀 0). 임계값(90%) 초과 → iterate 불필요, report 단계로 진행.
