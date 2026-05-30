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

## PDCA #16 (Database Save Refactor — improvement.plan #9 종결)

| 문서 | 원래 위치 | 단계 |
| --- | --- | --- |
| [database_save_refactor.plan.md](./database_save_refactor/database_save_refactor.plan.md) | 01-plan/features/ | Plan |
| [database_save_refactor.design.md](./database_save_refactor/database_save_refactor.design.md) | 02-design/features/ | Design |
| [database_save_refactor.analysis.md](./database_save_refactor/database_save_refactor.analysis.md) | 03-analysis/features/ | Analysis (Match Rate **100%**) |
| [database_save_refactor.report.md](./database_save_refactor/database_save_refactor.report.md) | 04-report/features/ | Report |

## PDCA #19 (UI Architecture Refactor — 빌더 refs + 패널 검증 순수함수)

| 문서 | 원래 위치 | 단계 |
| --- | --- | --- |
| [ui_architecture_refactor.plan.md](./ui_architecture_refactor/ui_architecture_refactor.plan.md) | 01-plan/features/ | Plan |
| [ui_architecture_refactor.design.md](./ui_architecture_refactor/ui_architecture_refactor.design.md) | 02-design/features/ | Design (design-validator 78점→C-1/M-2/M-3 반영) |
| [ui_architecture_refactor.analysis.md](./ui_architecture_refactor/ui_architecture_refactor.analysis.md) | 03-analysis/features/ | Analysis (Match Rate **99%**) |
| [ui_architecture_refactor.report.md](./ui_architecture_refactor/ui_architecture_refactor.report.md) | 04-report/features/ | Report |

## PDCA #20 (Test Hang + Statusbar Cleanup — 경량)

| 문서 | 원래 위치 | 단계 |
| --- | --- | --- |
| [test_hang_and_statusbar_cleanup.plan.md](./test_hang_and_statusbar_cleanup/test_hang_and_statusbar_cleanup.plan.md) | 01-plan/features/ | Plan |
| [test_hang_and_statusbar_cleanup.report.md](./test_hang_and_statusbar_cleanup/test_hang_and_statusbar_cleanup.report.md) | 04-report/features/ | Report (Design/Analysis 생략, 경량) |

## PDCA #21 (Log Rotation Concurrency)

| 문서 | 원래 위치 | 단계 |
| --- | --- | --- |
| [log_rotation_concurrency.plan.md](./log_rotation_concurrency/log_rotation_concurrency.plan.md) | 01-plan/features/ | Plan |
| [log_rotation_concurrency.design.md](./log_rotation_concurrency/log_rotation_concurrency.design.md) | 02-design/features/ | Design |
| [log_rotation_concurrency.analysis.md](./log_rotation_concurrency/log_rotation_concurrency.analysis.md) | 03-analysis/features/ | Analysis (Match Rate **100%**) |
| [log_rotation_concurrency.report.md](./log_rotation_concurrency/log_rotation_concurrency.report.md) | 04-report/features/ | Report |

## 핵심 성과

- **`_init_ui` 분해**: 패널/다이얼로그 5종, 합계 851 → 120 LOC (−86%)
- **빌더 메서드**: 30개 추출 (모두 ≤40줄), 순수 Extract Method
- **동작 변경**: 0 (테스트 65/65 통과, 위젯 smoke 41개 속성 검증)
- **데드 코드 제거** (#14): `dhr_recipe_manager_dialog.py` 삭제 (−441 LOC)
- **save 함수 책임 분리 (#16)**: `save_mixing_record` 57→6 LOC, `save_changes` 64→12 LOC, 단위 테스트 +5건 (총 79/79 통과), `improvement.plan.md` #9 종결
- **UI 구조 리팩터 (#19)**: 빌더 `window.*` 직접 변형 제거(`SidebarRefs`/`StatusbarRefs` 반환), DHR 패널 검증을 `dhr_validation.py` 순수함수로 추출, 무동작변경 위반 0 (Match 99%), 신규 테스트 +18케이스(builders 3 + dhr_validation 10 + lot_utils 5)
- **테스트 hang 근절 + statusbar 단일소스 (#20)**: `error_handler` 헤드리스 모달 가드 + `generate_product_lot` except 타입 교정(DatabaseError 죽은코드 수정) + `SidebarRefs.mixing_status_bar` 단일소스화. 전체 스위트 120 passed, hang 0 (13.85s, 이전 영구정지)
- **로그 로테이션 동시성 (#21)**: `SafeTimedRotatingFileHandler`(rename 실패 silent tolerate) + `MIXING_LOG_DIR` 테스트 로그 격리. stderr 로테이션 노이즈 0, 123 passed (4.75s, Match 100%)
- **아카이브 날짜**: 2026-05-19 (#13/#14), 2026-05-23 (#16), 2026-05-30 (#19), 2026-05-31 (#20/#21)
