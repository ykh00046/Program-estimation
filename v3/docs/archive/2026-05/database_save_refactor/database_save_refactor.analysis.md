# database_save_refactor — Gap Analysis (PDCA #16)

> **Author**: gap-detector agent (검증 후 메인 에이전트 기록)
> **Created**: 2026-05-23
> **Match Rate**: **100%**
> **Plan**: [`../../01-plan/features/database_save_refactor.plan.md`](../../01-plan/features/database_save_refactor.plan.md)
> **Design**: [`../../02-design/features/database_save_refactor.design.md`](../../02-design/features/database_save_refactor.design.md)

---

## 1. 분석 대상

| 항목 | 위치 |
| --- | --- |
| Impl #1 | `v3/models/database.py` (lines 131–194) |
| Impl #2 | `v3/ui/record_view_dialog.py` (lines 266–349) |
| Impl #3 (테스트) | `v3/tests/unit/test_record_view_dialog_helpers.py` (신규) |

---

## 2. 체크포인트별 검증

### CP1. 헬퍼 추출 일치

| Design 명세 헬퍼 | 위치 | 결과 |
| --- | --- | --- |
| `_insert_mixing_record_row(conn, record_data) -> int` | `database.py:150-165` | ✅ |
| `_insert_mixing_detail_rows(conn, record_id, details) -> None` | `database.py:167-184` | ✅ |
| `_log_record_saved(record_data, record_id) -> None` | `database.py:186-194` | ✅ |
| `_confirm_save_changes() -> bool` | `record_view_dialog.py:285-293` | ✅ |
| `_collect_edit_form() -> dict` | `record_view_dialog.py:295-309` | ✅ |
| `_collect_material_updates_from_rows(rows)` **@staticmethod** | `record_view_dialog.py:311-323` | ✅ |
| `_handle_update_result(success, product_lot)` | `record_view_dialog.py:325-333` | ✅ |
| `_exit_edit_mode()` | `record_view_dialog.py:335-344` | ✅ |
| `_refresh_lot_data(product_lot)` | `record_view_dialog.py:346-349` | ✅ |

**판정: 9/9 (100%)**

### CP2. 메인 본문 LOC

| 메서드 | 본문 LOC | 임계 | 결과 |
| --- | --- | --- | --- |
| `save_mixing_record` | ~6줄 (with + 4 호출 + return) | ≤ 20 | ✅ |
| `save_changes` | ~13줄 (if/try/except 포함) | ≤ 20 | ✅ |

### CP3. 시그니처/예외 보존
`save_mixing_record(self, record_data: Dict, details: List[Dict]) -> int`, `@handle_exceptions` 데코레이터, `save_changes(self)` 및 `ValueError` / `Exception` 분기 모두 보존. **✅**

### CP4. 트랜잭션 경계
`conn.commit()`은 `save_mixing_record` 메인 메서드 안(`database.py:146`)에 잔존. 두 INSERT 헬퍼는 `conn`만 받고 commit/rollback을 호출하지 않음. Design §2 원칙과 정확히 일치. **✅**

### CP5. 테스트 커버리지

| Design §4.2 케이스 | 구현 테스트 | 결과 |
| --- | --- | --- |
| basic 변환 / float 타입 | `test_basic_conversion` | ✅ |
| 빈 문자열 → 0.0 | `test_empty_strings_become_zero` | ✅ |
| 빈 입력 → [] | `test_empty_rows_returns_empty_list` | ✅ |
| (추가) name 무시·code/lot 패스스루 | `test_material_code_and_lot_passthrough` | ✅ 보너스 |
| (추가) 잘못된 숫자 → ValueError 전파 | `test_invalid_number_raises_value_error` | ✅ 보너스 |

### CP6. 회귀 테스트
`python -m pytest tests/unit tests/integration` → **79/79 통과** (기존 74 + 신규 5). **✅**

---

## 3. 종합 점수

| 항목 | 점수 |
| --- | :-: |
| 헬퍼 추출 일치 | 100% |
| LOC 임계 충족 | 100% |
| 시그니처/예외 보존 | 100% |
| 트랜잭션 경계 | 100% |
| 테스트 커버리지 | 100% (+추가 2건) |
| 회귀 통과 | 100% |
| **Overall Match Rate** | **100%** |

---

## 4. Gap 목록

### Missing (Design O · Impl X)
없음.

### Added (Design X · Impl O)
- `test_material_code_and_lot_passthrough`, `test_invalid_number_raises_value_error`: 추가 안전망 (긍정적).
- `_ensure_ui_dependencies()` 환경 가드 (CI 견고성, 긍정적).

### Changed (Design ≠ Impl) — 의도된 차이로 기록
- `_collect_edit_form`의 반환 타입 표기: Design은 `Dict`(typing), 구현은 `dict`(built-in). Python 3.9+ PEP 585 호환, 동작 동일.
- `save_mixing_record` 본문이 Design 목표(≤15줄)보다 더 엄격(≈6줄)하게 축소됨.

---

## 5. 권고
- Match Rate ≥ 90% 충족 → Report 단계 진입.
- `improvement.plan.md` 진행 현황 표 #9 = ✅ 완료 갱신은 Report 단계에서 일괄 처리.
- Design 문서 미세 표기 정합성(D)은 Cosmetic 수준 — 후속 사이클에서 처리해도 무방.
