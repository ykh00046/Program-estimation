# 긴 함수 리팩토링 Gap 분석 (PDCA #13)

> **Feature**: long_function_refactor
> **Design**: [../../02-design/features/long_function_refactor.design.md](../../02-design/features/long_function_refactor.design.md)
> **Author**: AI Assistant
> **Created**: 2026-05-19
> **PDCA Cycle**: #13
> **Match Rate**: **98%**

---

## 1. 분석 개요

설계서(Design)의 빌더 메서드 분해안과 실제 구현을 대조한다.
대상: 5개 파일의 `_init_ui` 및 추출 빌더 메서드.

---

## 2. 설계 대비 구현 대조

| 파일 | 설계 빌더 수 | 구현 빌더 수 | `_init_ui` LOC | 일치 |
| --- | --- | --- | --- | --- |
| `manual_input_interface.py` | 6 | 6 | 20 | ✅ 완전 일치 |
| `bulk_creation_interface.py` | 5 | 5 | 18 | ✅ 완전 일치 |
| `admin_signature_panel.py` | 4 | 4 | 14 | ✅ 완전 일치 |
| `recipe_management_interface.py` | 4 (+`_make_category_btn`) | 7 | 33 | 🔶 보정 |
| `dhr_recipe_manager_dialog.py` | 4 (+`_make_category_btn`) | 8 | 35 | 🔶 보정 |

---

## 3. Gap 목록

### Gap-1 (보정 / Minor) — 정보 그룹 행 단위 추가 분해

- **대상**: `recipe_management_interface.py`, `dhr_recipe_manager_dialog.py`
- **설계**: `_build_info_group` 단일 메서드.
- **구현**: `_build_info_group`이 ≤40줄 기준(약 62줄 예상)을 초과하여
  `_build_name_row` / `_build_company_type_row` / `_build_drug_period_row`
  3개 행 빌더로 추가 분해. `_build_info_group`은 이를 조립만 수행.
- **판정**: 설계 원칙(빌더 ≤40줄, 순수 Extract Method) **준수를 위한 보정**.
  설계 의도를 위반하지 않고 강화함. 회귀 위험 없음.

### Gap-2 (보정 / Minor) — 닫기 버튼 빌더 분리

- **대상**: `dhr_recipe_manager_dialog.py`
- **설계**: 최하단 닫기 버튼을 `_init_ui` 오케스트레이터에 포함(행 234–253).
- **구현**: `_build_bottom_bar`로 분리하여 `_init_ui`를 ≤40줄로 유지(35줄).
- **판정**: ≤40줄 목표 달성을 위한 보정. 설계 원칙 부합.

### Gap 없음 항목

- 위젯 트리·시그널 연결·스타일: 변경 없음 (smoke 41개 속성 검증).
- `_init_ui` ≤40줄 목표: 5/5 달성.
- 동작 변경: 없음 (테스트 65/65 통과).

---

## 4. 검증 결과

| 검증 항목 | 결과 |
| --- | --- |
| `py_compile` (5개 파일) | ✅ 통과 |
| `python tests/run_tests.py` | ✅ 65/65 통과 |
| 위젯 생성 smoke (5개 클래스) | ✅ 통과 (노출 위젯 41개 확인) |
| `_init_ui` ≤40줄 | ✅ 5/5 (20·18·14·33·35) |
| 빌더 메서드 ≤40줄 | ✅ 40줄 초과 0건 |
| `git diff` 범위 | ✅ `_init_ui` 영역 한정 |

---

## 5. 종합 판정

**Match Rate 98%** — 설계 항목 전량 구현 완료. 2건의 Gap은 모두 설계 원칙
(빌더 ≤40줄)을 **준수하기 위한 추가 분해(보정)**이며 설계 의도 위반·회귀 위험
없음. 90% 기준을 충족하므로 **iterate 불필요, report 단계로 진행**.

---

**작성일**: 2026-05-19
