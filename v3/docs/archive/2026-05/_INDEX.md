# 2026-05 Archive Index

> 2026년 5월 아카이브 문서 목록

## PDCA #13 (Long Function Refactor)

| 문서 | 원래 위치 | 단계 |
| --- | --- | --- |
| [long_function_refactor.plan.md](./long_function_refactor/long_function_refactor.plan.md) | 01-plan/features/ | Plan |
| [long_function_refactor.design.md](./long_function_refactor/long_function_refactor.design.md) | 02-design/features/ | Design |
| [long_function_refactor.analysis.md](./long_function_refactor/long_function_refactor.analysis.md) | 03-analysis/features/ | Analysis (Match Rate 98%) |
| [long_function_refactor.report.md](./long_function_refactor/long_function_refactor.report.md) | 04-report/features/ | Report |

## PDCA #14 (Recipe Dialog Dead Code Removal — 경량)

| 문서 | 원래 위치 | 단계 |
| --- | --- | --- |
| [recipe_dialog_dead_code_removal.plan.md](./recipe_dialog_dead_code_removal/recipe_dialog_dead_code_removal.plan.md) | 01-plan/features/ | Plan |
| [recipe_dialog_dead_code_removal.report.md](./recipe_dialog_dead_code_removal/recipe_dialog_dead_code_removal.report.md) | 04-report/features/ | Report (Design/Analysis 생략, 데드 코드 삭제) |

## 핵심 성과

- **`_init_ui` 분해**: 패널/다이얼로그 5종, 합계 851 → 120 LOC (−86%)
- **빌더 메서드**: 30개 추출 (모두 ≤40줄), 순수 Extract Method
- **동작 변경**: 0 (테스트 65/65 통과, 위젯 smoke 41개 속성 검증)
- **데드 코드 제거** (#14): `dhr_recipe_manager_dialog.py` 삭제 (−441 LOC)
- **아카이브 날짜**: 2026-05-19
