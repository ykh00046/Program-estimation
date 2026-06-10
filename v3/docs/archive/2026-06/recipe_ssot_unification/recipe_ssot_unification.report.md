# 배합 레시피 SSOT 일원화 + 편집 화면 — 완료 보고서

> PDCA Feature: `recipe_ssot_unification` (**PDCA #37**)
> 기간: 2026-06-10 (1일) · 최종 Match Rate: **100%** (1차 통과) · 테스트: **364/364**

## 1. 무엇을 해결했나

전체 검토(2026-06-10)의 Medium "레시피 SSOT 이원화"를 코드 조사로 재정의해 해소했다:

| | Before | After |
|---|--------|-------|
| 배합 레시피의 진실 | **레시피.xlsx 파일** — 프로그램에서 편집 불가, 파일 직접 수정 | **DB recipes 테이블** — 화면에서 추가/수정/삭제 |
| DB recipes 테이블 | 프로덕션 호출자 0인 죽은 자산 (#28에서 Repository까지 완비된 채 방치) | 배합 레시피의 SSOT로 부활 |
| 편집 화면 | DHR 레시피용만 존재 (배합 레시피용 **없음**) | 신규 `RecipeEditDialog` — 배합 탭 "레시피 편집" 버튼 |

> 문제 재정의가 핵심이었다: "이원화 해소"의 실체는 정리가 아니라 **죽은 DB 경로를 살려
> SSOT로 만들고, 사용자가 원한 편집 화면을 그 위에 얹는 것** (#18 "단어 트랩" 교훈 재적용).

## 2. 구현 내역

- **Repository**: `get_recipes`에 '순서' 키(additive — UI 정렬 호환), `deactivate_recipe`
  (물리 삭제 금지 — 배합 기록의 recipe_name 참조 보존, 콤보에서만 제거)
- **DataManager**: `load_recipes()` DB 전환 + **빈 테이블이면 Excel 1회 자동 시드**(무손실
  마이그레이션) / `seed_recipes_from_excel()`은 무조건 임포트(이름 덮어쓰기) — "비어 있을
  때만" 조건은 호출자 책임으로 분리 (명시적 "Excel에서 가져오기" 버튼이 직접 호출)
- **RecipeEditDialog**: 목록+새 레시피 / 레시피명+자재 3열 테이블+행 추가·삭제 /
  비율 합 실시간 표시(100±0.01 벗어나면 경고색) / 저장(합≠100은 확인 후 진행 — 차단 아님) /
  삭제 확인 / Excel 재가져오기. 영속화 전부 DataManager 위임, 워커 불필요(동기 SQLite)
- **진입점**: RecipePanel 콤보 옆 "레시피 편집" 버튼 → MainWindow 배선 → 닫힌 후 콤보 갱신
- **호환**: 스키마 변경 0, `get_recipe_names/items` 시그니처 불변(소비 UI 무수정),
  DHR 레시피 화면 무접촉

## 3. PDCA 사이클 기록

| 단계 | 결과 |
|------|------|
| Plan | 코드 사실 4종(F1~F4)으로 문제 재정의 — "배합 레시피 편집 화면 부재"가 진짜 빈자리 |
| Design | save_recipe 자재 축소 동작을 코드 검증으로 사전 해소(변경 불필요 확정) |
| Do | Repository 2건 + DataManager 전환 + 다이얼로그 신규 + 테스트 18개 |
| Check | **100% 1차 통과** — 미구현/스펙 위반 0 |

## 4. 교훈 (Lessons Learned)

1. **죽은 자산 점검이 설계의 지름길**: recipes 테이블·Repository·Facade가 이미 완비 —
   "신규 구축"처럼 보였던 작업의 실비용은 deactivate 1개 + 호출 경로 전환뿐이었다.
   기능 요청 전 기존 자산 확인(#32 교훈)의 재확인.
2. **INSERT OR REPLACE + 컬럼 생략 = DEFAULT 복원**: is_active를 INSERT 목록에서 빼면
   REPLACE된 행이 DEFAULT 1을 받는다 — "전체 비활성화 후 재삽입" 패턴이 자재 축소를
   공짜로 처리하는 이유. 리스크로 가정하지 말고 **Design 단계에서 코드로 검증**하면
   불필요한 보강을 막는다.
3. **마이그레이션 조건과 임포트 행위의 책임 분리**: "비어 있을 때만"은 load 쪽,
   seed 자체는 무조건 — 같은 메서드가 자동 마이그레이션과 명시적 재가져오기 양쪽에
   재사용된다.

## 5. 후속 과제

- 레시피.xlsx 제거 — 운영 안정 확인 후 별도 결정 (현재는 시드 소스로 존치)
- 잔여 내실 후보: DataManager InventoryService 분리, 대형 UI 파일 분해,
  image_processor 타입 힌트, 백업 재시도 버튼, 일괄 생성 진행률(#36 후속)

## 6. 산출물

- 코드: `recipe_repository.py`, `database.py`, `data_manager.py`,
  `recipe_edit_dialog.py`(신규), `recipe_panel.py`, `main_window.py`
- 테스트: `test_recipe_ssot.py`(9) + `test_recipe_edit_dialog_smoke.py`(8) +
  `test_data_manager.py` 갱신 — 총 364 통과
- 문서: plan / design / analysis / report
