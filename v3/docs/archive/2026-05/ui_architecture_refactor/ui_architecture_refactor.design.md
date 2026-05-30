# UI 구조 리팩터 설계서 (PDCA #19)

> **Feature**: ui_architecture_refactor
> **Plan**: [../../01-plan/features/ui_architecture_refactor.plan.md](../../01-plan/features/ui_architecture_refactor.plan.md)
> **Author**: AI Assistant
> **Created**: 2026-05-29
> **Status**: ✅ Design (design-validator 반영 완료, §8)
> **PDCA Cycle**: #19

---

## 1. 설계 원칙

- **무동작변경 우선(Part A)**: 공개 속성명(`self.manual_interface` 등)·위젯 생성 순서·런타임 동작을 **비트 단위로 보존**. 내부 전달 방식만 `window.* 직접 set` → `refs 반환 + 호출부 명시 할당`으로 교체.
- **순수 함수 분리(Part B)**: DHR 패널 3종에는 전용 controller가 없다(`SaveController`/`RecipeController`는 메인 배합 페이지용). 새 controller 클래스를 만드는 대신, 검증을 **Qt 비의존 순수 함수**로 추출 → `(bool, message)` 튜플 반환. 기존 `DataManager.validate_record_inputs` 패턴과 일치.
- **뷰의 책임 축소**: 패널은 입력 수집 + 결과 메시지 표시만. 검증 규칙은 순수 함수가 보유.
- **Python 3.9**: `typing.Optional/List/Dict/Tuple` 사용, `|` 유니온 금지.
- **빌더는 Qt API 호출은 유지**: `window.addSubInterface(...)`는 FluentWindow 등록이므로 빌더에 잔존(이건 "window 속성 변형" 스멜이 아님). 제거 대상은 `window.manual_interface = ...` 같은 **커스텀 속성 set**뿐.

---

## 2. Part A — 빌더 refs 반환 (무동작변경)

### 2.1 refs 데이터클래스 (builders.py 상단)

```python
from dataclasses import dataclass
from typing import Optional

@dataclass
class SidebarRefs:
    """register_sidebar_interfaces가 생성해 main_window가 소유할 참조 묶음."""
    mixing_page_refs: object          # build_mixing_page 반환 refs
    mixing_status_bar: object         # mixing_page_refs.status_bar
    manual_interface: object          # ManualInputInterface
    bulk_interface: object            # BulkCreationInterface
    recipe_interface: object          # RecipeManagementInterface

@dataclass
class StatusbarRefs:
    """setup_statusbar가 생성해 main_window가 소유할 참조 묶음."""
    google_sheets_status_label: object
    status_controller: object         # StatusController
```

> 필드 타입을 `object`로 두는 이유: 순환 import 회피 + 무동작변경 단계에서 타입 강결합 최소화. Design 검토에서 구체 타입 힌트로 좁히는 것은 선택.

### 2.2 시그니처 변경

| 함수 | Before | After |
|---|---|---|
| `register_sidebar_interfaces(window) -> None` | `window.manual_interface = ...` 등 직접 set | `-> SidebarRefs` 반환, 커스텀 속성 set 제거 |
| `setup_statusbar(window) -> None` | `window.google_sheets_status_label = ...`, `window.status_controller = ...` | `-> StatusbarRefs` 반환 |

- `window.addSubInterface(...)` 호출은 **그대로 유지**.
- `_setup_dhr_settings_sync()` 호출은 빌더에서 **제거** → main_window로 이동(아래 2.4). 빌더가 window의 컨트롤러 셋업을 오케스트레이션하지 않도록.

### 2.3 register_sidebar_interfaces 본문 (After 골격)

```python
def register_sidebar_interfaces(window) -> SidebarRefs:
    from ui.panels.manual_input_interface import ManualInputInterface
    from ui.panels.recipe_management_interface import RecipeManagementInterface
    from ui.panels.bulk_creation_interface import BulkCreationInterface

    mixing, mixing_page_refs = build_mixing_page(window)
    window.addSubInterface(mixing, FIF.MIX_VOLUMES, "배합")

    manual = ManualInputInterface(window, dhr_db=window.services.dhr_db,
                                  lot_manager=window.services.lot_manager)
    window.addSubInterface(manual, FIF.EDIT, "수기 입력")

    bulk = BulkCreationInterface(window, dhr_db=window.services.dhr_db,
                                 lot_manager=window.services.lot_manager)
    window.addSubInterface(bulk, FIF.PASTE, "일괄 생성")

    recipe = RecipeManagementInterface(window, dhr_db=window.services.dhr_db)
    window.addSubInterface(recipe, FIF.LIBRARY, "DHR 관리")

    window.addSubInterface(window.dashboard_panel, FIF.PIE_SINGLE, "대시보드")
    # ... 기록 조회 / 설정 / 작업자 변경 (기존과 동일, window 인자만 사용) ...

    return SidebarRefs(
        mixing_page_refs=mixing_page_refs,
        mixing_status_bar=mixing_page_refs.status_bar,
        manual_interface=manual,
        bulk_interface=bulk,
        recipe_interface=recipe,
    )
```

### 2.4 main_window 호출부 변경

`_create_central_widget`:

```python
def _create_central_widget(self):
    self._create_panels()
    refs = register_sidebar_interfaces(self)
    self.mixing_page_refs = refs.mixing_page_refs
    self.mixing_status_bar = refs.mixing_status_bar
    self.manual_interface = refs.manual_interface
    self.bulk_interface = refs.bulk_interface
    self.recipe_interface = refs.recipe_interface
    self._setup_dhr_settings_sync()   # 빌더에서 이동(할당 직후)
    self._connect_panel_signals()
```

`_init_ui`의 `setup_statusbar(self)`:

```python
sb = setup_statusbar(self)
self.google_sheets_status_label = sb.google_sheets_status_label
self.status_controller = sb.status_controller
```

- `setup_statusbar`는 `window.mixing_status_bar`(이미 main_window가 할당)·`window.data_manager`를 읽으므로, `_create_central_widget`(할당) → `setup_statusbar` 순서를 유지하면 동작 불변.

### 2.5 순서/동작 보존 체크포인트

| 항목 | 보존 방법 |
|---|---|
| `_setup_dhr_settings_sync`가 `manual/bulk_interface.scan_effects_panel` 접근 | refs 할당 **직후** 호출 → 접근 경로 동일 |
| 대시보드 subinterface 등록 위치 | 빌더 내부 유지(sync와 무관, scan/sig만 동기화) |
| statusbar가 mixing_status_bar 의존 | 호출 순서 `_create_central_widget` → `setup_statusbar` 불변 |
| 공개 속성명 | 5개 sidebar + 2개 statusbar 속성명 **그대로** |

---

## 3. Part B — 패널 검증 순수 함수 추출

### 3.1 신규 모듈 `ui/panels/dhr_validation.py`

```python
"""DHR 패널 입력 검증 순수 함수 (PDCA #19). Qt 비의존, (ok, message) 반환."""
from typing import List, Tuple

# focus_field: 실패 시 포커스 이동 대상 키("product_name"/"amount"/""), 메시지 문자열
# 역매핑 대신 키로 명시. 자재 분기는 현행도 포커스 이동이 없으므로 "".
def validate_manual_input(product_name: str, amount: float,
                          material_row_count: int) -> Tuple[bool, str, str]:
    if not product_name.strip():
        return False, "제품명을 입력하세요.", "product_name"
    if amount <= 0:
        return False, "배합량을 입력하세요.", "amount"
    if material_row_count == 0:
        return False, "자재를 최소 1개 이상 입력하세요.", ""
    return True, "", ""

# bulk은 현행 분기 순서(제품명 검사 → 파싱 → entries 검사)를 보존하기 위해 두 함수로 분리.
# parse_bulk_entries는 빈 테이블에 []를 반환(예외 아님)하므로 entry_count==0 분기는 도달 가능(죽은 코드 아님).
def validate_bulk_product(product_name: str) -> Tuple[bool, str]:
    if not product_name.strip():
        return False, "제품명을 입력하세요."
    return True, ""

def validate_bulk_entries(entry_count: int) -> Tuple[bool, str]:
    if entry_count == 0:
        return False, "생성할 데이터가 없습니다."
    return True, ""

def validate_recipe_input(recipe_name: str) -> Tuple[bool, str]:
    if not recipe_name.strip():
        return False, "레시피명을 입력하세요."
    return True, ""
```

### 3.2 패널 적용 (뷰는 수집 + 표시만)

**manual_input_interface `_validate`** — 규칙은 순수 함수, **포커스 이동은 focus_field 키로 뷰가 인라인 처리**(메시지 문자열 역매핑 금지). 현행 동작(제품명→product_name_edit, 배합량→amount_spin, 자재→포커스 없음) 그대로 보존:

```python
def _validate(self) -> bool:
    ok, msg, focus = validate_manual_input(
        self.product_name_edit.text(),
        self.amount_spin.value(),
        self._get_effective_material_row_count(),
    )
    if ok:
        return True
    QMessageBox.warning(self, "입력 오류", msg)
    if focus == "product_name":
        self.product_name_edit.setFocus()
    elif focus == "amount":
        self.amount_spin.setFocus()
    return False
```

**bulk_creation_interface `_bulk_create`** — **현행 분기 순서를 비트 단위로 보존**(제품명 검사 → 파싱(ValueError 표시) → entries 검사). 제품명 검사를 파싱 뒤로 미루면 "제품명 공백 + 날짜 오류" 동시 입력 시 노출 메시지가 바뀌므로 순서 유지가 필수:

```python
product_name = self.product_name_edit.text().strip()  # strip 후 검증·생성기 전달(동작 일관)
ok, msg = validate_bulk_product(product_name)        # 파싱 '이전' (현행과 동일 위치)
if not ok:
    QMessageBox.warning(self, "입력 오류", msg); return
try:
    entries = self._parse_bulk_entries()
    materials = self._get_materials_for_bulk()
except ValueError as e:
    QMessageBox.warning(self, "입력 오류", str(e)); return
ok, msg = validate_bulk_entries(len(entries))         # 파싱 '이후'
if not ok:
    QMessageBox.warning(self, "입력 오류", msg); return
```

**recipe_management_interface `_save_recipe`**:

```python
ok, msg = validate_recipe_input(self.name_edit.text())
if not ok:
    QMessageBox.warning(self, "입력 오류", msg); return
name = self.name_edit.text().strip()
```

### 3.3 비-이관 항목 (의도적)

- DB 저장 실패/예외의 `QMessageBox.critical`(결과 표시)은 뷰 책임이므로 유지.
- bulk의 "Partial Success" 부분 실패 표시 — 결과 표시이므로 유지.
- 숫자 파싱 `ValueError`(`_recalc_theory` 등) — 입력 즉시성 보조라 유지.

---

## 4. 테스트 설계 (Part C)

### 4.1 신규 `tests/unit/test_dhr_validation.py` (Qt 비의존)

순수 함수만 테스트하므로 Qt/DB 불필요.

| 테스트 | 검증 |
|---|---|
| `test_manual_empty_product` | 제품명 공백 → `(False, "제품명...", "product_name")` |
| `test_manual_zero_amount` | amount 0 → `(False, "배합량...", "amount")` |
| `test_manual_no_material` | row 0 → `(False, "자재...", "")` (포커스 없음) |
| `test_manual_ok` | 정상 → `(True, "", "")` |
| `test_bulk_product_empty / ok` | `validate_bulk_product` 2종 |
| `test_bulk_entries_zero / ok` | `validate_bulk_entries` 2종 |
| `test_recipe_empty / ok` | `validate_recipe_input` 2종 |

### 4.2 빌더 테스트 — 범위 재조정 (design-validator C-1 반영)

`register_sidebar_interfaces`/`setup_statusbar`를 stub window로 단위 테스트하는 것은 비현실적이다. 두 함수는 내부에서 `build_mixing_page`·`build_settings_page`·`build_action_page`를 호출하며 window의 다수 속성/메서드(`recipe_panel`, `work_info_panel`, `material_panel`, `scan_effects_panel`, `signature_panel`, `_save_record`, `_open_records`, `_request_worker_and_refresh`, `is_sidebar_hover_expand_enabled`, `_set_sidebar_hover_expand_enabled`, `_set_status_message`, `dashboard_panel`, `services`, `data_manager`)와 **FluentWindow 인프라(`addSubInterface` → navigationInterface/stackedWidget)** 에 의존하므로 순수 더블로 재현 불가.

따라서:
- **단위 테스트(`tests/unit/test_builders.py`)는 `build_mixing_page`로 한정** — 이미 `Tuple[QWidget, MixingPageRefs]`를 반환하므로(현행), refs의 `save_btn`/`status_bar` 필드가 채워지는지 + 위젯 objectName을 검증. offscreen QApplication + 필요한 패널만 주입.
- **`register_sidebar_interfaces`/`setup_statusbar`의 refs 반환·할당 동일성은 4.3 시각 스모크에서 실제 `MainWindow` 경로로 커버.**

### 4.3 시각 스모크 (refactor-order visual-smoke.md) — refs 회귀의 1차 방어선

offscreen에서 실제 `MainWindow`를 생성하되 **작업자 입력 다이얼로그를 우회**(`config.last_worker` 사전 주입 또는 `request_worker_input`를 monkeypatch)하여:
- 4개 화면(배합/수기/일괄/DHR 관리) 진입 + DHR 설정 3-way sync 1회 토글 → 예외 0
- `main_window.manual_interface/bulk_interface/recipe_interface/mixing_status_bar/status_controller`가 None 아님(refs 할당 검증)

### 4.4 회귀 기준

- 기존 데이터/패널 테스트(누계 통과분) + 신규 테스트 전부 green
- 공개 속성 접근(`main_window.manual_interface` 등) 동작 불변

---

## 5. 위험 재확인

| 위험 | 결정 |
|---|---|
| refs 전환 시 sync 접근 경로 깨짐 | `_setup_dhr_settings_sync`를 refs 할당 **직후** 호출, Part A 첫 커밋에서 시각 스모크 필수 |
| `setup_statusbar` 순서 의존 | `_init_ui` 내 위치 그대로 유지(central로 이동 금지). `mixing_status_bar`는 `_create_central_widget`에서 할당되어 호출 시점에 존재 |
| 빌더 단위 테스트가 stub으로 불가(C-1) | 단위 테스트는 `build_mixing_page`로 한정, 전체 빌더는 시각 스모크(실제 MainWindow + 작업자 다이얼로그 우회)로 커버 |
| bulk 검증 순서 변경(M-2) | `validate_bulk_product`(파싱 전)/`validate_bulk_entries`(파싱 후) 2분리로 현행 순서 보존 |
| manual 포커스 회귀(M-3) | 순수 함수가 focus_field 키 반환, 뷰가 인라인 매핑(메시지 역매핑 금지) |
| Part A/B 동시 진행으로 회귀 추적난 | Part A(무동작) 전 커밋 완료·검증 후 Part B 착수 |

---

## 6. 단계별 커밋 계획

1. `refactor(ui): return SidebarRefs from register_sidebar_interfaces (PDCA #19 A1)` — 빌더 반환화 + main_window 할당, sync 호출 이동, **`register_sidebar_interfaces` docstring의 "3-way sync도 초기화" 문구 수정**(이제 main_window가 호출). `build_mixing_page`는 이미 refs 반환(MixingPageRefs)이므로 재작성 대상 아님 — `mixing_page_refs`로 그대로 활용
2. `refactor(ui): return StatusbarRefs from setup_statusbar (PDCA #19 A2)`
3. `test: add builders refs unit test (PDCA #19 A3)`
4. `refactor(ui): extract DHR panel validation to pure functions (PDCA #19 B1)` — dhr_validation.py + 3패널 적용
5. `test: add dhr_validation unit tests (PDCA #19 B2)`
6. `docs: PDCA #19 analysis + report` — 마지막

---

## 7. 다음 단계

`/pdca do ui_architecture_refactor` — 위 커밋 1번부터 순차 진행, 각 단계 후 데이터/패널 테스트 + 시각 스모크.

---

## 8. design-validator 검증 반영 (2026-05-29)

bkit:design-validator 1차 검증(완전성 78/100) 지적사항을 본 문서에 반영 완료:

| ID | 지적 | 반영 |
|---|---|---|
| C-1 | "최소 stub window" 빌더 단위 테스트 비현실적(패널·FluentWindow 다수 의존) | 4.2를 `build_mixing_page` 단위로 한정, 전체 빌더는 4.3 시각 스모크(실제 MainWindow+다이얼로그 우회)로 커버 |
| M-2 | bulk 검증 통합 시 제품명 검사가 파싱 뒤로 밀려 노출 메시지 변경(무동작변경 위반) | `validate_bulk_product`(파싱 전)/`validate_bulk_entries`(파싱 후) 2분리로 순서 보존. `parse_bulk_entries` 빈입력=[] 확인(죽은 코드 아님) |
| M-3 | `_focus_for_message` 메시지 역매핑은 자기모순·취약 | 순수 함수가 `focus_field` 키 반환, 뷰 인라인 매핑으로 현행 포커스 동작 보존 |
| M-1 | `setup_statusbar` 위치 오해 소지 | 위험표에 "`_init_ui` 위치 유지, central 이동 금지" 명시 |
| m-3 | `register_sidebar_interfaces` docstring "sync 초기화" 문구가 거짓이 됨 | 커밋 1 체크리스트에 docstring 수정 추가 |
| m-1 | `build_mixing_page` 이미 refs 반환 | 커밋 1 노트에 "재작성 대상 아님" 명시 |

잔여 판단: m-2(`SidebarRefs.mixing_status_bar` 파생 중복)는 현행도 동일 구조라 무동작변경 위해 **의도적 보존**, 후속 정리 후보로만 기록.
