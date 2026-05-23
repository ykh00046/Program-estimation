# 로직 함수 리팩토링 Gap 분석 (PDCA #15)

> **Feature**: logic_function_refactor
> **Design**: [../../02-design/features/logic_function_refactor.design.md](../../02-design/features/logic_function_refactor.design.md)
> **Author**: AI Assistant
> **Created**: 2026-05-23
> **PDCA Cycle**: #15
> **Match Rate**: **100%**

---

## 1. 개요

Plan에서 정의한 Part A(데드 파일 삭제) + Part B(라이브 UI/로직 분해) +
Part C(테스트 보강 후 dhr_bulk_generator 분해)를 모두 Design 명세대로 구현.

---

## 2. 설계 대비 구현 대조

| Part | 설계 산출물 | 구현 결과 | 일치 |
| --- | --- | --- | --- |
| A | `recipe_manager_dialog.py` 삭제 | 삭제 + stale 주석 정정 없음(주석은 #14 처리 대상 아님) | ✅ |
| B-1 | RecordDetailDialog 빌더 3종 (info/detail/button) | 정확히 3종 추출, `init_ui` 89→8 LOC | ✅ |
| B-2 | RecordViewDialog 빌더 4종 (filter/table/agg/button) | 정확히 4종 추출, `init_ui` 89→8 LOC | ✅ |
| B-3 | `_save_and_export` 헬퍼 4종 | `_build_details_for_export`/`_persist_dhr_record`/`_run_export_pipeline`/`_notify_save_result` 추출, 82→25 LOC | ✅ |
| C-0 | T1~T9 단위 테스트 9건 | 9건 작성, 모두 통과 | ✅ |
| C-1 | `generate` 헬퍼 4종 | `_collect_unique_dates`/`_build_lot_map_by_date`/`_resolve_work_time`/`_build_record_and_details` 추출, 82→37 LOC | ✅ |
| C-2 | `_export_record` 헬퍼 4종 | `_prepare_signed_image`/`_build_bulk_export_data`/`_run_bulk_export`/`_cleanup_signed_image` 추출, 70→30 LOC | ✅ |

---

## 3. Gap 항목

### 설계 누락 — 없음
모든 헬퍼/빌더/테스트가 Design 명세 그대로 구현됨.

### 추가 발견 (Plan 단계 이연 항목)
- `record_view_dialog.save_changes` (64), `database.save_mixing_record` (57)는 Plan에서 이연 확정. PDCA #16 후보.

### 프로세스 관찰 (Lessons)
- **동일 이름 메서드 splice 함정**: `record_view_dialog.py`에 두 클래스의 `init_ui` 메서드가 동시 존재할 때, `src.index("def init_ui(self):")` 1회만 사용하면 항상 첫 occurrence만 잡히고 두 번째 splice가 같은 위치를 재교체함. 두 번째 occurrence를 `src.index(defline, first + 1)`로 명시 탐색 필요. PDCA #15에서 1회 픽스 splice 추가로 해결.
- **Plan-단계 사용처 사전 검증의 가치**: `recipe_manager_dialog.py`가 데드 코드임을 사전 grep으로 확인했기에 mixin 추출 같은 헛수고 없이 즉시 삭제로 처리. `#14`에서 학습한 패턴이 `#15`에서 재현됨.

---

## 4. 검증

| 항목 | 결과 |
| --- | --- |
| 5개 대상 메서드 ≤40 LOC | ✅ (8/8/25/37/30) |
| 전 빌더/헬퍼 ≤40 LOC | ✅ (0건 초과) |
| `python tests/run_tests.py` | ✅ 74/74 통과 |
| 신규 dhr_bulk_generator 테스트 | ✅ 9/9 통과 |
| 기존 `_save_and_export` 회귀 테스트 | ✅ D1·D2·D3 전 경로 통과 |
| 위젯 스모크 (RecordViewDialog) | ✅ 노출 속성 6종 확인 |
| `grep -r RecipeManagerDialog v3` | ✅ 0건 (Part A) |

---

## 5. 종합 판정

**Match Rate 100%** — Design의 모든 항목 구현 완료, Gap 없음. 90% 기준 충족,
**iterate 불필요, report 단계로 진행**.

---

**작성일**: 2026-05-23
