# 배합 레시피 SSOT 일원화 + 편집 화면 — Plan

> PDCA Feature: `recipe_ssot_unification` (PDCA #37)
> 작성일: 2026-06-10 · Level: Starter (Desktop / PySide6)

## 1. 배경 / 문제 정의 (코드 사실 기반 재정의)

전체 검토(2026-06-10)는 "레시피 SSOT 이원화(Excel+DB 병존)"를 Medium으로 지적했다.
코드 조사로 확인한 실체는 더 구체적이다:

| # | 사실 | 의미 |
|---|------|------|
| F1 | 배합(Mixing) 화면 레시피는 `DataManager._load_recipes_from_excel`(레시피.xlsx)만 읽음 | **배합 레시피의 진실 = Excel 파일** — 프로그램에서 편집 불가, 파일 직접 수정 필요 |
| F2 | mixing DB `recipes` 테이블 + `RecipeRepository`(save/get) + Facade 위임 완비 | **프로덕션 호출자 0** — 수동 테스트 도구(dhr_bulk_dryrun/selftest)만 사용하는 죽은 자산 |
| F3 | "레시피 관리" 화면(`recipe_management_interface`)은 **DHR 레시피 전용** (dhr_db 주입, 타이틀 "DHR 관리 (레시피)") | 배합 레시피용 편집 화면은 **존재하지 않음** — 사용자 요구("편집/추가 화면")의 빈자리 |
| F4 | `material_table_panel.load_items`는 '순서' 키로 정렬(기본 0, 안정 정렬) | DB 조회 결과에 '순서' 키를 포함하면 형식 호환 |

→ **문제 재정의**: "이원화 해소"는 단순 정리가 아니라, 죽어 있던 DB 경로(F2)를 살려
배합 레시피의 SSOT로 만들고, 그 위에 사용자가 원한 **배합 레시피 편집 화면**을 얹는 것.

## 2. 목표 (Goals)

배합 레시피의 진실을 DB(`recipes` 테이블)로 일원화하고, 프로그램 안에서 레시피를
추가/수정/삭제할 수 있게 한다. Excel은 최초 1회 시드(마이그레이션) 소스로 강등된다.

### 요구사항 매핑

| # | 요구사항 | 충족 방법 |
|---|----------|-----------|
| 1 | 배합 레시피 SSOT = DB | `DataManager.load_recipes()`를 `db.get_recipes()` 기반으로 전환 |
| 2 | 기존 Excel 데이터 무손실 이전 | 시작 시 recipes 테이블이 비어 있으면 Excel 자동 시드 (1회 마이그레이션) |
| 3 | 레시피 추가/수정 화면 | 신규 `RecipeEditDialog` — 목록 + 레시피명 + 자재(코드/명/비율) 테이블 + 저장 |
| 4 | 레시피 삭제 | `is_active=0` 비활성화 (이력 보존 — 기존 배합 기록의 recipe_name 참조 유지) |
| 5 | 편집 진입점 | 배합 탭 레시피 패널에 "레시피 편집" 버튼 → 다이얼로그 → 닫힌 후 콤보 갱신 |
| 6 | Excel 재가져오기 | 다이얼로그에 "Excel에서 가져오기" 버튼 (명시적 재임포트 — 이름 기준 덮어쓰기) |
| 7 | 기존 UI 형식 호환 | `get_recipes` 반환에 '순서' 키 추가 (F4 — load_items 정렬 호환) |

## 3. 범위 (Scope)

### In Scope
- `RecipeRepository`: `get_recipes`에 '순서' 키 추가, `deactivate_recipe(name)` 신규
- `DataManager`: `load_recipes()` DB 전환 + 빈 테이블 Excel 자동 시드(`seed_recipes_from_excel`),
  `save_recipe`/`deactivate_recipe` 위임 추가. `_load_recipes_from_excel`은 시드 소스로 유지
- Facade: `deactivate_recipe` 위임
- 신규 `ui/dialogs/recipe_edit_dialog.py` + `RecipePanel`에 편집 버튼 + `MainWindow` 배선
- 비율 합 100% 검증: 합≠100이면 **경고 후 사용자 확인** (저장 차단 아님 — 기존 Excel 데이터에
  관용)
- 단위/스모크 테스트 + 기존 346개 회귀 없음 (test_data_manager의 Excel 가정 테스트는
  DB+시드 가정으로 갱신)

### Out of Scope (후속)
- DHR 레시피 화면(`recipe_management_interface`)과의 통합 — 별도 도메인(DHR DB), 현행 유지
- 레시피 버전 관리/승인 이력 — is_active 스키마로 후일 확장 가능
- 레시피.xlsx 파일 제거 — 시드 소스로 존치 (운영 안정 확인 후 별도 결정)
- recipes 테이블 스키마 변경 (기존 UNIQUE(recipe_name, material_code) 그대로)

## 4. 핵심 설계 결정 (요약 — 상세는 Design)

1. **죽은 자산 재활용**: recipes 테이블/Repository/Facade가 이미 완비 — 신규 스키마 0,
   살리는 데 필요한 건 deactivate 1개와 호출 경로뿐.
2. **시드는 "비어 있을 때만" 자동**: 매 시작 시 Excel 동기화는 이원화의 재생산 —
   자동은 최초 1회, 이후엔 다이얼로그의 명시적 "Excel에서 가져오기"만.
3. **삭제 = 비활성화**: 배합 기록이 recipe_name을 참조하므로 물리 삭제 금지.
   `get_recipes`는 is_active=1만 조회(기존 동작)라 콤보에서 자연 제거.
4. **save_recipe의 기존 동작 보존 주의**: 기존 구현은 "전체 비활성화 후 INSERT OR REPLACE" —
   자재 축소 시 잔존 행 처리 검증 필요 (Design에서 확정).

## 5. 영향 범위 (변경 파일 예상)

| 파일 | 변경 |
|------|------|
| `v3/models/repositories/recipe_repository.py` | '순서' 키, deactivate_recipe |
| `v3/models/database.py` | deactivate_recipe 위임 |
| `v3/models/data_manager.py` | load_recipes DB 전환 + 시드 + 위임 2종 |
| `v3/ui/dialogs/recipe_edit_dialog.py` | **신규** |
| `v3/ui/panels/recipe_panel.py` | 편집 버튼 추가 |
| `v3/ui/main_window.py` | 버튼 배선 + 닫힘 후 콤보 갱신 |
| `v3/tests/unit/test_recipe_ssot.py` | **신규** (repository/시드/위임) |
| `v3/tests/integration/test_recipe_edit_dialog_smoke.py` | **신규** |
| `v3/tests/unit/test_data_manager.py` | Excel 가정 → DB+시드 가정으로 갱신 |

## 6. 리스크 / 완화

| 리스크 | 영향 | 완화 |
|--------|------|------|
| save_recipe의 "비활성화→INSERT OR REPLACE"가 자재 축소 시 옛 행을 is_active=0으로 남기지만 INSERT OR REPLACE가 같은 (name,code) 행을 되살림 | **높음** — 편집 후 유령 자재 가능 | Design에서 동작 검증 후 필요 시 save_recipe 보강(같은 이름 비활성 행 정리). 단위 테스트로 자재 축소 시나리오 고정 |
| 기존 test_data_manager가 Excel 로드 가정 | 중 | DB+시드 가정으로 갱신 (get_recipes mock 반환 설정) |
| 운영 DB 첫 실행 마이그레이션 | 중 | 빈 테이블 시드는 INSERT만 — 무손실. 시드 결과 로그 |
| 사용자 워크플로 변화 (Excel 직접 편집 → 화면) | 중 | Excel 재가져오기 버튼으로 과도기 지원 |
| Python 3.9 / offscreen 모달 | 중 | typing 준수, 스모크 QMessageBox patch |

## 7. 완료 기준 (Definition of Done)

- [ ] 요구사항 1~7 구현
- [ ] 자재 축소 편집 시 유령 자재 없음 (리스크 1 테스트 고정)
- [ ] gap-detector 일치율 ≥ 90%
- [ ] 신규/갱신 테스트 통과 + 기존 346개 회귀 없음
- [ ] 완료 보고서 작성

## 8. 다음 단계

→ `/pdca design recipe_ssot_unification`
