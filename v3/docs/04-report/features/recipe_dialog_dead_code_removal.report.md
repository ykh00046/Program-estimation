# 레시피 다이얼로그 데드 코드 제거 보고서 (PDCA #14)

> **Feature**: recipe_dialog_dead_code_removal
> **Author**: AI Assistant
> **Created**: 2026-05-19
> **PDCA Cycle**: #14 (경량 — Plan + Report)
> **Status**: ✅ Completed

---

## 1. 요약

미사용 `DhrRecipeManagerDialog`(`ui/dhr_recipe_manager_dialog.py`, 475줄)를
삭제하여 `RecipeManagementInterface`와의 중복 코드를 제거. mixin 추출 없이
삭제만으로 중복 100% 소멸.

---

## 2. 배경 — mixin이 아닌 삭제인 이유

`improvement.plan.md` #10은 두 레시피 편집 클래스의 빌더/CRUD 중복 해소를
목표로 했고, 당초 `RecipeEditorMixin` 추출을 검토했다. 그러나 저장소 전체
조사에서 `DhrRecipeManagerDialog`가 **데드 코드**임이 드러났다:

- 참조: 클래스 정의 자신 + `recipe_management_interface.py` docstring 주석 1줄
- import / 인스턴스화 / 테스트 / 메뉴·사이드바 연결: **0건**
- 패널 버전 `RecipeManagementInterface`가 완전 대체, `ui/builders.py`에 연결

→ mixin 추출은 데드 코드를 살아있는 코드에 결합시키는 부채. 삭제가 정답.

---

## 3. 변경 내역

| 파일 | 변경 |
| --- | --- |
| `ui/dhr_recipe_manager_dialog.py` | **삭제** (475줄) |
| `ui/panels/recipe_management_interface.py` | docstring의 stale 클래스명 참조 정정 |

---

## 4. 검증

| 항목 | 결과 |
| --- | --- |
| `grep -r DhrRecipeManager v3` | ✅ 잔존 참조 0건 |
| `py_compile` (recipe_management_interface, builders) | ✅ |
| import 스모크 (`ui.builders`, `RecipeManagementInterface`) | ✅ |
| `python tests/run_tests.py` | ✅ 65/65 통과 |

---

## 5. 교훈

- **중복 제거 전 생사 확인 우선**: "중복 코드"로 보여도 한쪽이 데드 코드면
  해법은 공통화가 아니라 삭제다. 리팩토링 패턴을 정하기 전에 사용처 조사 필수.
- PDCA #13에서 이 파일의 `_init_ui`를 리팩토링했으나, 데드 코드 판정 시
  삭제가 우선. 사전 사용처 조사를 #13 범위 산정 때 했다면 5개가 아닌
  4개 파일로 좁힐 수 있었다 — 차기 Plan 단계 체크리스트에 반영.

---

## 6. 잔여 / 다음 사이클 후보

`improvement.plan.md` 기준 잔여:

- **#9 로직 함수 리팩토링** — `recipe_manager_dialog.save_to_excel`(94),
  `manual_input_interface._save_and_export`(82), `dhr_bulk_generator.generate`(82)
  등. 테스트 보강 선행 필요. → PDCA #15 후보.

이로써 `improvement.plan.md`는 #10까지 완료, #9만 잔여.

---

**작성일**: 2026-05-19
