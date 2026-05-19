# 레시피 다이얼로그 데드 코드 제거 계획서 (PDCA #14)

> **Feature**: recipe_dialog_dead_code_removal
> **Summary**: 미사용 `DhrRecipeManagerDialog` 삭제로 중복 코드 제거
> **Author**: AI Assistant
> **Created**: 2026-05-19
> **Status**: ✅ Plan 승인됨
> **PDCA Cycle**: #14 (경량 — Plan + Report)

---

## 1. 배경

`improvement.plan.md` #10(중복 코드 제거)의 후속. `recipe_management_interface.py`와
`dhr_recipe_manager_dialog.py`는 빌더·CRUD 메서드가 거의 동일하다.

당초 mixin 추출을 검토했으나, 전체 저장소 조사 결과
**`DhrRecipeManagerDialog`는 데드 코드**임이 확인되었다.

### 데드 코드 근거

`DhrRecipeManagerDialog` 참조 위치 (저장소 전체, dist 제외):

| 위치 | 종류 |
| --- | --- |
| `ui/dhr_recipe_manager_dialog.py:20` | 클래스 정의 자신 |
| `ui/panels/recipe_management_interface.py:3` | 모듈 docstring 주석 |

import·인스턴스화·테스트·메뉴/사이드바 연결 **0건**. 패널 버전
`RecipeManagementInterface`가 완전히 대체했고 `ui/builders.py`에 연결되어 있다.

---

## 2. 범위

### 작업

1. `ui/dhr_recipe_manager_dialog.py` 파일 삭제 (475줄).
2. `ui/panels/recipe_management_interface.py:3`의 stale 주석 정정
   (삭제될 클래스명 참조 제거).

### 제외

- mixin/공통 베이스 추출 — 한쪽이 데드 코드이므로 불필요(중복이 삭제로 소멸).
- `recipe_management_interface.py`의 빌더/CRMethod 로직 변경 없음.

---

## 3. 기대 효과

- 중복 코드 100% 제거 (mixin 부채 없이).
- 코드베이스 -475줄.
- 회귀 위험 0 (미참조 코드 삭제).

---

## 4. 검증 기준 (DoD)

- [ ] `grep -r DhrRecipeManager` — 잔존 참조 0건
- [ ] `python tests/run_tests.py` 65/65 통과
- [ ] 앱 import 스모크 — `ui.builders` 등 정상 import

---

## 5. 다음 단계

경량 사이클이므로 Design/Analysis 생략. 삭제 → 검증 → Report.

---

**작성일**: 2026-05-19
