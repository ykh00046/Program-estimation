# 배합 레시피 SSOT 일원화 + 편집 화면 — Gap 분석

> PDCA Feature: `recipe_ssot_unification` (PDCA #37)
> 분석일: 2026-06-10 · 도구: gap-detector Agent
> 설계: `docs/02-design/features/recipe_ssot_unification.design.md`

## 1. 분석 요약

| 구분 | 내용 |
|------|------|
| Match Rate | **100%** (1차 통과, iterate 불필요) |
| 미구현/스펙 위반 | 0건 |
| 테스트 | 364개 전부 통과 (기존 346 + 신규 18, 회귀 0) |

## 2. 항목별 검증 결과

| 설계 항목 | 결과 | 비고 |
|-----------|:---:|------|
| §2.1 Repository ('순서' additive, deactivate is_active=1 조건·rowcount 반환) | ✅ 100% | 설계 스니펫과 글자 단위 일치 |
| §2.2 Facade 순수 위임 | ✅ 100% | |
| §2.3 DataManager 표 6행 (init 전환/시드 분기/seed 무조건 임포트/위임 2종) | ✅ 100% | "비어 있을 때만" 책임 분리 정확 |
| §2.4 UI (패널 버튼 위치·배선·다이얼로그 전체 구성·비율 경고 비차단·토큰) | ✅ 100% | |
| §3 마이그레이션 (빈 테이블 자동 시드 / 이후 DB만 / Excel 존치) | ✅ 100% | |
| §4 테스트 계획 — **자재 축소 유령 테스트(Plan 리스크 1) 포함** | ✅ 100% | 신규 18개 전부 매핑 |
| §6 호환성 (스키마 0, 기존 키 보존, DHR 화면 무접촉, Py3.9) | ✅ 100% | |

## 3. 사전 검증으로 해소된 리스크

- **Plan 리스크 1 (자재 축소 유령)**: Design 단계 코드 검증으로 현행 `save_recipe`의
  "전체 비활성화 → INSERT OR REPLACE(is_active DEFAULT 1)" 패턴이 이미 올바름을 확인 —
  변경 없이 테스트(`test_material_shrink_leaves_no_ghosts`)로 동작 고정.

## 4. 차이점 (모두 무해 — 방어 로직/로깅 추가 3건)

deactivate 성공 로그, 다이얼로그 로드 try/except 방어, ratio≤0 검증 구체화 —
계약/반환형/동작 불변, 설계의 안정성 정신에 부합.

## 5. 결론

**Match Rate 100% (≥90%)** → `/pdca report recipe_ssot_unification` 진행.
배합 레시피의 진실이 Excel 파일에서 DB로 일원화되고, 처음으로 프로그램 안에서
배합 레시피를 편집할 수 있게 됨.
