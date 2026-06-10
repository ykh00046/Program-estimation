# 배합 레시피 SSOT 일원화 + 편집 화면 — Design

> PDCA Feature: `recipe_ssot_unification` (PDCA #37)
> 작성일: 2026-06-10 · Plan: `docs/01-plan/features/recipe_ssot_unification.plan.md`

## 1. 아키텍처 개요

```
[시작/콤보 갱신]                         [편집]
RecipeController.load_recipes            RecipePanel "레시피 편집" 버튼
  → DataManager.load_recipes               → MainWindow._open_recipe_editor
      → db.get_recipes()  (SSOT)               → RecipeEditDialog(dm).exec()
      → 비어 있으면 seed_recipes_from_excel        (저장/삭제/Excel 가져오기 → dm 위임)
        (1회 마이그레이션) 후 재조회             → 닫힌 후 recipe_controller.load_recipes()
  → recipe_panel.set_recipes(names)              (콤보 갱신)
```

**Plan 리스크 1 해소 (코드 검증 완료)**: `save_recipe`의 "전체 `is_active=0` → INSERT OR
REPLACE" 패턴은 자재 축소 시에도 올바름 — REPLACE된 새 행은 `is_active` 컬럼이 INSERT
목록에 없어 **DEFAULT 1**을 받고, 빠진 자재 행은 is_active=0으로 남아 `get_recipes`
(is_active=1 필터)에서 자연 제외된다. **save_recipe 변경 불필요**, 단위 테스트로 동작 고정만.

## 2. 컴포넌트 설계

### 2.1 `RecipeRepository` (2건)

**(a) `get_recipes` '순서' 키 추가** — `material_table_panel.load_items`의 '순서' 정렬(F4) 호환:
```python
recipes[recipe_name].append({
    '품목코드': row['material_code'],
    '품목명': row['material_name'],
    '배합비율': row['ratio'],
    '순서': row['sequence_order'],     # 추가 (additive — 기존 소비자에 무해)
})
```

**(b) `deactivate_recipe(recipe_name) -> bool`** (신규):
```python
@handle_exceptions(user_message="레시피 삭제 중 오류가 발생했습니다.", default_return=False)
def deactivate_recipe(self, recipe_name: str) -> bool:
    """레시피를 비활성화한다 (물리 삭제 금지 — 배합 기록의 recipe_name 참조 보존)."""
    with self.get_connection() as conn:
        cursor = conn.execute(
            "UPDATE recipes SET is_active = 0, updated_at = CURRENT_TIMESTAMP "
            "WHERE recipe_name = ? AND is_active = 1", (recipe_name,))
        conn.commit()
        return cursor.rowcount > 0
```

### 2.2 Facade (`database.py`) — `deactivate_recipe` 순수 위임 1건.

### 2.3 `DataManager`

| 변경 | 내용 |
|------|------|
| `__init__` | `self.recipes = self._load_recipes_from_excel()` → `self.recipes: Dict = {}` + `self.load_recipes()` |
| `load_recipes()` | DB 조회 → **비어 있으면** `seed_recipes_from_excel()` 후 재조회 → `self.recipes` 갱신 |
| `seed_recipes_from_excel() -> int` (신규 공개) | `_load_recipes_from_excel()` → 레시피별 `db.save_recipe(name, materials)` → 종수 반환. **무조건 임포트(이름 기준 덮어쓰기)** — "비어 있을 때만" 조건은 load_recipes 쪽 책임 (다이얼로그의 명시적 재가져오기가 이 메서드를 직접 호출) |
| `save_recipe(name, materials)` / `deactivate_recipe(name)` | Facade 위임 (신규) |
| `_load_recipes_from_excel` | 유지 — 시드 소스로 강등 (docstring 갱신) |
| `get_recipe_names`/`get_recipe_items` | 무변경 (`self.recipes` 기반 — 원천만 교체됨) |

### 2.4 UI

**`RecipePanel`** — HBox 레이아웃의 콤보 직후에 보조 버튼:
```python
self.edit_recipes_btn = QPushButton("레시피 편집")
self.edit_recipes_btn.setStyleSheet(UIStyles.get_secondary_button_style())
layout.addWidget(self.edit_recipes_btn)   # recipe_combo 다음, addSpacing(20) 앞
```
패널은 시그널만 노출(클릭 처리 없음) — 배선은 MainWindow 책임 (기존 패턴).

**`MainWindow`**:
```python
# _connect_panel_signals 또는 _create_panels 말미
self.recipe_panel.edit_recipes_btn.clicked.connect(self._open_recipe_editor)

def _open_recipe_editor(self):
    """배합 레시피 편집 다이얼로그 (PDCA #37). 닫힌 후 콤보 갱신."""
    from ui.dialogs.recipe_edit_dialog import RecipeEditDialog
    RecipeEditDialog(self.data_manager, self).exec()
    self.recipe_controller.load_recipes()
```

**`ui/dialogs/recipe_edit_dialog.py` (신규)** — `RecipeEditDialog(QDialog)`:
- 좌: `QListWidget` 레시피 목록 + `[새 레시피]` 버튼 (우측 폼 초기화)
- 우: 레시피명 `QLineEdit` + 자재 테이블 3열(품목코드/품목명/배합비율(%)) +
  `[행 추가]`/`[행 삭제]` + 비율 합 라벨(실시간 갱신, 100±0.01 벗어나면 WARNING_COLOR)
- 하단: `[Excel에서 가져오기]` `[레시피 삭제]` | `[저장]` `[닫기]`
- 동작 (영속화는 전부 DataManager 위임):
  - 목록 선택 → `dm.get_recipe_items(name)` 폼 로드
  - 저장: 검증(이름 필수 / 자재 ≥1 / 코드·비율 유효) → 합≠100이면 `QMessageBox.question`
    확인 후 진행(차단 아님 — 기존 Excel 데이터 관용) → `dm.save_recipe` →
    `dm.load_recipes()` + 목록 갱신
  - 삭제: 확인 question → `dm.deactivate_recipe` → `dm.load_recipes()` + 목록 갱신 + 폼 초기화
  - Excel 가져오기: "이름 기준 덮어쓰기" 경고 question → `dm.seed_recipes_from_excel()` →
    `dm.load_recipes()` + 목록 갱신 + 가져온 종수 알림
- 스타일: `UIStyles.get_dialog_style/get_table_style/버튼 스타일` 토큰만 (신규 색 금지)
- 모든 작업이 빠른 SQLite 단건 — **워커 불필요** (COM/네트워크 없음)

## 3. 마이그레이션 / 운영 전환

| 시점 | 동작 |
|------|------|
| 갱신 후 첫 실행 | recipes 테이블 비어 있음 → Excel 자동 시드(INSERT만, 무손실) + 시드 종수 로그 |
| 이후 실행 | DB만 읽음 — Excel 변경은 무시 (명시적 가져오기 전까지) |
| 과도기 | 다이얼로그 "Excel에서 가져오기"로 기존 워크플로(파일 편집) 지원 |
| 레시피.xlsx | 존치 (제거는 운영 안정 확인 후 별도 결정 — Plan Out of Scope) |

## 4. 테스트 계획

| 테스트 | 파일 | 검증 |
|--------|------|------|
| get_recipes '순서' 키 + 정렬 | `tests/unit/test_recipe_ssot.py` (신규, tmp DB) | sequence_order가 '순서'로 노출, 순서 보존 |
| **자재 축소 시 유령 없음** (Plan 리스크 1 고정) | 〃 | 3자재 저장 → 2자재 재저장 → get_recipes 2건만 |
| 자재 재추가 부활 | 〃 | 축소 후 같은 코드 재저장 → 다시 포함 |
| deactivate | 〃 | 비활성화 후 get_recipes 미포함 / 미존재·중복 호출 False |
| load_recipes 시드 분기 | 〃 (DataManager.__new__ + 실제 tmp Facade, Excel 로더 monkeypatch) | 빈 테이블 → 시드 후 DB 재조회 / 이미 있으면 Excel 로더 미호출 |
| seed 명시 호출 = 덮어쓰기 | 〃 | DB에 기존 레시피 있어도 Excel 내용으로 갱신 |
| 다이얼로그 스모크 | `tests/integration/test_recipe_edit_dialog_smoke.py` (신규, mock dm + QMessageBox patch) | 목록 로드/선택→폼/저장 위임/합≠100 경고 분기/삭제 확인 위임/Excel 가져오기 위임/빈 목록 안전 |
| RecipePanel 버튼 + MainWindow 배선 | 스모크 또는 builders 테스트 보강 | edit_recipes_btn 존재 |
| 기존 갱신 | `tests/unit/test_data_manager.py` | setUp에 `get_recipes.return_value={}`, `test_load_recipes_success`를 "빈 DB → 시드 → 재조회" 흐름으로 재작성 |
| 회귀 | `run_tests.py` | 기존 346개 통과 |

## 5. 구현 순서

1. Repository ('순서'/deactivate) + Facade 위임 + tmp DB 단위 테스트
2. DataManager (load_recipes/seed/위임) + 시드 분기 테스트 + test_data_manager 갱신
3. RecipeEditDialog + RecipePanel 버튼 + MainWindow 배선 + 스모크
4. 전체 회귀 + 보고

## 6. 호환성 체크리스트

- [ ] recipes 테이블 스키마 변경 0
- [ ] `get_recipes` 기존 키 보존 ('순서'는 additive)
- [ ] `get_recipe_names`/`get_recipe_items` 시그니처·반환 형식 불변 (UI 무수정 호환)
- [ ] Python 3.9 typing / UITheme 토큰만 / 함수 20줄
- [ ] DHR 레시피 화면(`recipe_management_interface`) 무접촉

## 7. 다음 단계

→ `/pdca do recipe_ssot_unification`
