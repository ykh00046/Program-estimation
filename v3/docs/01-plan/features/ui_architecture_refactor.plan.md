# UI 구조 리팩터 계획서 (PDCA #19)

> **Feature**: ui_architecture_refactor
> **Summary**: (3-a) `builders.py`가 `window.*` 속성을 직접 mutate하는 방식을 refs 반환 + 명시적 소유로 전환, (5) DHR 패널의 비즈니스 검증 로직을 controller로 이관
> **Author**: AI Assistant
> **Created**: 2026-05-29
> **Status**: ✅ Plan
> **PDCA Cycle**: #19 (UI 아키텍처 리팩터 — 무동작변경 우선)

---

## 1. 배경

2026-05-29 코드 검토(UI 아키텍처 + 코드 품질)에서 데이터 정합성·DI·DRY 4건은 즉시 처리하여 `origin/main`에 반영 완료(`5fba142`, `1d36573`, `f2af48f`, `8d45c10`). 남은 2건은 **동일한 UI 구조 리팩터 위험군**으로 분리하여 전용 사이클로 다룬다.

### 남은 2건

- **(3-a) 빌더의 window 속성 변형**: `register_sidebar_interfaces`/`setup_statusbar`(`builders.py`)가 `window.manual_interface`, `window.bulk_interface`, `window.recipe_interface`, `window.mixing_page_refs`, `window.mixing_status_bar`, `window.google_sheets_status_label`, `window.status_controller` 등을 함수 내부에서 직접 set → 소유권/생명주기 추적이 어렵고 숨은 의존이 산재.
- **(5) 패널의 비즈니스 검증 혼재**: `manual_input_interface` / `bulk_creation_interface` / `recipe_management_interface`가 입력검증 + `QMessageBox` + 변환을 한 메서드에서 수행. 뷰가 비즈니스 규칙을 직접 들고 있어 테스트성이 낮음.

> **명시적 비-대상**: 코드 검토 #5의 "예외 협소화"는 검토 결과 대부분 의도적(재전파/UI 이벤트 경계/로그 후 graceful 반환)이라 변경하지 않는다. 본 사이클은 "검증 로직 이관"만 다룬다.

---

## 2. 범위 (In Scope)

### Part A — 빌더 refs 반환 (무동작변경, refactor-order Phase A-3)

`builders.py`의 window 변형 함수를 **refs 데이터클래스(또는 NamedTuple)를 반환**하도록 변경하고, 호출부(`main_window`)가 반환값을 명시적으로 자기 속성에 할당한다.

| 대상 | 변경 |
|---|---|
| `register_sidebar_interfaces(window)` | `SidebarRefs`(manual/bulk/recipe/dashboard 등) 반환, window 직접 set 제거 |
| `setup_statusbar(window)` | `StatusbarRefs`(google_sheets_status_label, status_controller) 반환 |
| `main_window` 호출부 | `refs = register_sidebar_interfaces(self); self.manual_interface = refs.manual` 식으로 명시 할당 |

- 공개 속성명(`self.manual_interface` 등)은 **그대로 유지** → 외부/테스트 영향 없음.
- 한 함수씩 작게 쪼개 커밋 (manual → bulk → recipe → statusbar 순), 각 단계 후 시각 스모크.

### Part B — 패널 검증 로직 controller 이관 (refactor-order Phase C)

각 패널의 "저장/생성 전 비즈니스 검증"을 controller/service로 이동. 뷰는 입력 수집 + 결과 메시지 표시만 담당.

| 패널 | 이관 대상 | 이관 위치(후보) |
|---|---|---|
| `manual_input_interface` | 제품명/배합량/자재 검증 (285~320 부근) | `controllers.py`의 SaveController 또는 `DataManager.validate_record_inputs` 재사용 |
| `bulk_creation_interface` | 제품명/엔트리 검증 (245~288 부근) | Bulk 전용 controller 메서드 |
| `recipe_management_interface` | 레시피명/항목 검증 (320 부근) | RecipeController |

- 검증 함수는 `(bool, message)` 튜플 반환 패턴으로 통일(이미 `validate_record_inputs`가 사용).
- 뷰는 `ok, msg = controller.validate(...)` 후 `if not ok: QMessageBox.warning(...)`.

### Part C — 테스트 / 검증

| 테스트 | 위치 | 항목 |
|---|---|---|
| 단위 — refs 반환 | `tests/unit/test_builders.py` (신규) | 각 빌더가 기대 refs 필드를 반환, window 속성 매핑 일치 |
| 단위 — controller 검증 | 기존 `test_manual_input_*` 확장 | 검증 분기 controller 경유 동작 |
| 시각 스모크 | `references/visual-smoke.md` 절차 | 4개 화면(배합/수기/일괄/DHR관리) offscreen 인스턴스화 + 진입 |

---

## 3. 비-범위 (Out of Scope)

- 예외(`except Exception`) 협소화 — 의도적이라 변경 안 함
- `record_view_dialog` 책임 분해 (별도 후보)
- `excel_exporter` 책임 분리 (별도 후보)
- 패널 lazy 초기화 (refactor-order Phase D, 후속)
- 신규 기능/동작 변경 일체

---

## 4. 의존성 / 제약

- **Python 3.9** 유지 (`typing` 사용, `|` 유니온 금지)
- **무동작변경 원칙**: Part A는 런타임 동작 동일해야 함 (공개 속성명·생성 순서 보존)
- **UITheme 토큰만 사용**, 신규 색 금지
- `_setup_dhr_settings_sync`가 `self.manual_interface.scan_effects_panel` 등에 의존 → refs 전환 시 생성 순서/접근 경로 깨지지 않도록 주의
- 작게 쪼갠 커밋 + 단계별 검증 (refactor-order Guardrails)

---

## 5. 성공 기준

- [ ] `builders.py`가 window를 직접 mutate하지 않고 refs 반환 (Part A)
- [ ] 패널에서 비즈니스 검증 분기 제거, controller 경유 (Part B)
- [ ] 공개 속성명/런타임 동작 불변 (회귀 0건)
- [ ] 기존 데이터/패널 테스트 + 신규 테스트 전부 통과
- [ ] 4개 주요 화면 시각 스모크 통과
- [ ] Match Rate >= 90%

---

## 6. 일정

| 단계 | 예상 |
|---|---|
| Plan + Design | 30분 |
| Do — Part A (빌더 refs, 4커밋) | 1시간 |
| Do — Part B (검증 이관, 3커밋) | 1시간 |
| Do — Part C (테스트/스모크) | 40분 |
| Check + Iterate | 30분 |
| Report + Archive | 15분 |

---

## 7. 위험 & 완화

| 위험 | 영향 | 완화 |
|---|---|---|
| refs 전환 시 생성 순서/접근 경로 변경 → 3-way sync 깨짐 | DHR 설정 동기화 오동작 | Part A를 함수 단위로 쪼개고 매 단계 시각 스모크; `_setup_dhr_settings_sync` 경로 우선 검증 |
| 검증 이관 중 메시지/분기 누락 | 잘못된 입력 통과 | controller 검증에 단위 테스트 선작성(테스트 우선) |
| 동작변경과 구조이동 동시 발생 | 회귀 추적 난이도 | Phase A(무동작) 완료 후 Phase B 착수, 커밋 분리 |
| 공개 속성명 변경 유혹 | 외부/테스트 깨짐 | 속성명 보존 강제, 내부만 이동 |

---

## 8. 다음 단계

`/pdca design ui_architecture_refactor` 로 설계 문서 작성 (refs 데이터클래스 필드 정의 + 검증 이관 시그니처 확정) 후 `/pdca do`.
