# 긴 함수 리팩토링 설계서 (PDCA #13)

> **Feature**: long_function_refactor
> **Plan**: [../01-plan/features/long_function_refactor.plan.md](../../01-plan/features/long_function_refactor.plan.md)
> **Author**: AI Assistant
> **Created**: 2026-05-19
> **Status**: 🔄 Design
> **PDCA Cycle**: #13

---

## 1. 설계 원칙

순수 **Extract Method** 리팩토링. 동작·위젯 트리·시그널 연결 결과 불변.

1. 각 `_init_ui`를 **얇은 오케스트레이터**로 전환 — 빌더 호출 + 최상위 조립만.
2. 빌더 메서드는 **하나의 시각적 섹션**을 만들어 위젯/레이아웃을 반환.
3. 외부(다른 메서드)에서 참조하는 위젯은 빌더 내부에서 **`self.` 속성으로 그대로 할당**.
4. 빌더 호출 순서 = 원본 위젯 생성 순서 (시그널 연결 순서 보존).
5. 타입 힌트는 `typing`/Qt 타입 사용 (Python 3.9 호환, CLAUDE.md 규칙).

### 명명 규칙

- 위젯 반환 빌더: `_build_<섹션>(self) -> QWidget`
- 레이아웃 반환 빌더: `_build_<섹션>(self) -> QLayout`
- 반복 위젯 팩토리: `_make_<항목>(self, ...) -> QWidget`

---

## 2. 파일별 분해 설계

### 2.1 `ui/dhr_recipe_manager_dialog.py` — `_init_ui` 221줄

원본 33–253행. 우측 패널이 거대(정보 그룹 + 자재 그룹).
중첩 지역함수 `create_small_btn`은 메서드로 승격.

| 신규 메서드 | 반환 | 원본 행 범위 | 책임 |
| --- | --- | --- | --- |
| `_init_ui` (오케스트레이터) | None | 33–44, 234–253 | 스타일·레이아웃·splitter·조립·닫기버튼·`center_window` |
| `_build_recipe_list_panel` | `QWidget` | 46–87 | 좌측 레시피 목록 테이블 + 목록 버튼 |
| `_make_category_btn` | `StyledButton` | 101–105 | 분류 +/- 버튼 팩토리 (지역함수 승격) |
| `_build_info_group` | `QGroupBox` | 96–187 | 레시피 정보 (레시피명/거래처/제품종류/약품/착용기간) |
| `_build_material_group` | `QGroupBox` | 189–220 | 자재 목록 테이블 + 행 버튼 |

`self.` 노출 위젯: `recipe_table`, `name_edit`, `company_combo`, `product_type_combo`,
`drug_edit`, `wear_period_combo`, `mat_table` — 각 빌더 내부에서 그대로 할당.

### 2.2 `ui/panels/recipe_management_interface.py` — `_init_ui` 206줄

원본 33–238행. 2.1과 **구조 동일**(다이얼로그 → 패널 전환본). 동일 분해 적용.

| 신규 메서드 | 반환 | 원본 행 범위 | 책임 |
| --- | --- | --- | --- |
| `_init_ui` (오케스트레이터) | None | 33–49, 223–238 | 타이틀·splitter·조립 |
| `_build_recipe_list_panel` | `QWidget` | 51–90 | 좌측 레시피 목록 |
| `_make_category_btn` | `StyledButton` | 104–108 | 분류 버튼 팩토리 |
| `_build_info_group` | `QGroupBox` | 99–190 | 레시피 정보 |
| `_build_material_group` | `QGroupBox` | 192–221 | 자재 목록 |

`self.` 노출 위젯: 2.1과 동일.

### 2.3 `ui/panels/manual_input_interface.py` — `_init_ui` 164줄

원본 48–211행. `QScrollArea` 기반 — `content_widget`/`setWidget`은 오케스트레이터 유지.

| 신규 메서드 | 반환 | 원본 행 범위 | 책임 |
| --- | --- | --- | --- |
| `_init_ui` (오케스트레이터) | None | 49–56, 조립 | content_widget·root·빌더 조립 |
| `_build_toolbar` | `QHBoxLayout` | 58–70 | 타이틀 + 레시피 불러오기 버튼 |
| `_build_work_group` | `CardWidget` | 76–103 | 작업 정보 (작업일자/시간/시간표시) |
| `_build_product_group` | `CardWidget` | 105–133 | 제품 정보 (제품명/LOT/배합량) |
| `_build_settings_tabs` | `QTabWidget` | 137–154 | PDF 스캔 효과 + 서명 옵션 탭 |
| `_build_table_group` | `CardWidget` | 156–194 | 자재 테이블 + 행 버튼 |
| `_build_bottom_bar` | `QHBoxLayout` | 196–211 | 기록 조회 / 저장 및 출력 버튼 |

`self.` 노출 위젯: `content_widget`, `date_edit`, `time_edit`, `chk_include_time`,
`product_name_edit`, `product_lot_edit`, `amount_spin`, `scan_effects_panel`,
`signature_panel`, `table`, `save_btn`.
주의: `_build_table_group` 내부의 `self._add_row()` 초기 호출 순서 유지.

### 2.4 `ui/panels/bulk_creation_interface.py` — `_init_ui` 137줄

원본 43–179행. `QScrollArea` 기반.

| 신규 메서드 | 반환 | 원본 행 범위 | 책임 |
| --- | --- | --- | --- |
| `_init_ui` (오케스트레이터) | None | 43–55, 조립 | content_widget·root·타이틀·빌더 조립 |
| `_build_common_info_group` | `CardWidget` | 57–74 | 제품명 + 시간 옵션 |
| `_build_bulk_data_group` | `CardWidget` | 76–109 | 날짜/배합량 입력 테이블 + 행 버튼 |
| `_build_material_group` | `CardWidget` | 111–146 | 자재 정보 테이블 + 행/레시피 버튼 |
| `_build_settings_tabs` | `QTabWidget` | 148–161 | PDF/서명 설정 탭 |
| `_build_action_bar` | `QHBoxLayout` | 163–179 | 기록 조회 / 일괄 생성 버튼 |

`self.` 노출 위젯: `content_widget`, `product_name_edit`, `chk_include_time`,
`bulk_table`, `mat_table`, `scan_effects_panel`, `signature_panel`.
주의: `_build_material_group` 내부 `self._add_mat_row(0)` 초기 호출 유지.

### 2.5 `ui/panels/admin_signature_panel.py` — `_init_ui` 123줄

원본 76–198행. `QSplitter` 좌(설정)/우(미리보기) 구조.

| 신규 메서드 | 반환 | 원본 행 범위 | 책임 |
| --- | --- | --- | --- |
| `_init_ui` (오케스트레이터) | None | 77–84, 174–198 | splitter·left_panel·우 패널 조립 |
| `_build_position_group` | `QGroupBox` | 86–112 | 서명 위치 (charge/review/approve X·Y) |
| `_build_quality_group` | `QGroupBox` | 114–150 | 품질 파라미터 + Randomization |
| `_build_test_group` | `QGroupBox` | 152–172 | 작업자 선택 + 생성/저장 버튼 |
| `_build_preview_panel` | `QWidget` | 176–193 | 우측 미리보기 그리드 + 진행바 |

`self.` 노출 위젯: `pos_controls`, `param_controls`, `worker_combo`, `generate_btn`,
`save_config_btn`, `scroll_area`, `image_container`, `image_grid`, `progress_bar`.
기존 `_add_double_param`/`_add_int_param` 헬퍼는 유지(이미 분리됨).

---

## 3. 구현 순서

테스트 보유 파일 → 미보유 파일 순으로 진행 (조기 회귀 감지).

1. `manual_input_interface.py` — 단위 테스트 보유 ✅
2. `bulk_creation_interface.py`
3. `admin_signature_panel.py`
4. `recipe_management_interface.py`
5. `dhr_recipe_manager_dialog.py`

각 파일 완료 후: `py_compile` → `python tests/run_tests.py` 실행.

---

## 4. 검증 (DoD)

- [ ] 5개 `_init_ui` 각각 ≤40줄
- [ ] 추출 빌더 메서드 각각 ≤40줄 (불가 시 사유 기록)
- [ ] `python tests/run_tests.py` 65/65 통과
- [ ] 앱 스모크 실행 — 5개 화면 렌더링·상호작용 정상
- [ ] `git diff` — 위젯/시그널/스타일 변경 없음 확인

---

## 5. 리스크 대응 (Plan 5장 보강)

| 리스크 | 대응 |
| --- | --- |
| `self.` 할당 누락 | 2장 "노출 위젯" 목록을 체크리스트로 사용, 파일별 `grep "self\."` 대조 |
| 지역함수 `create_small_btn` 승격 시 클로저 변수 | 인자(`text`, `callback`)만 사용 — 클로저 의존 없음, 안전 |
| `QScrollArea` content_widget 조립 누락 | `setWidget` 호출은 오케스트레이터에 유지 |
| 초기 행 추가 호출 순서 | `_add_row`/`_add_mat_row`는 해당 빌더 내부 원위치 유지 |

---

**작성일**: 2026-05-19
**버전**: 1.0
