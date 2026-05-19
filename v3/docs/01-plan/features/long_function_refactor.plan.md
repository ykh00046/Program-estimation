# 긴 함수 리팩토링 계획서 (PDCA #13)

> **Feature**: long_function_refactor
> **Summary**: 20줄 권장 기준을 크게 초과하는 `_init_ui` 계열 함수를 빌더 메서드로 분해
> **Author**: AI Assistant
> **Created**: 2026-05-19
> **Status**: ✅ Plan 승인됨 (2026-05-19, 범위: _init_ui 5종)
> **PDCA Cycle**: #13

---

## 1. 배경

`improvement.plan.md` #9(함수 길이 리팩토링)의 미완료 항목. 코드베이스 전체
실사 결과 **35줄 초과 함수가 63개**이며, 단일 PDCA 사이클로 전부 처리하는 것은
비현실적이다. 따라서 #13은 **가장 크고 회귀 위험이 낮은 영역**으로 범위를 좁힌다.

### 원래 계획의 정정

`improvement.plan.md`는 `DatabaseManager.save_mixing_record`를 "92줄"로 기재했으나
현재 실측 **57줄**이다. `MainWindow._init_ui`(과거 213줄)는 PDCA #7에서 이미 해소됨.

---

## 2. #13 범위 (Scope)

### 대상: 패널/다이얼로그의 `_init_ui` 메서드 5종

| 파일 | 함수 | 현재 LOC | 테스트 |
| --- | --- | --- | --- |
| `ui/dhr_recipe_manager_dialog.py` | `_init_ui` | 221 | 없음 |
| `ui/panels/recipe_management_interface.py` | `_init_ui` | 206 | 없음 |
| `ui/panels/manual_input_interface.py` | `_init_ui` | 164 | ✅ 있음 |
| `ui/panels/bulk_creation_interface.py` | `_init_ui` | 137 | 없음 |
| `ui/panels/admin_signature_panel.py` | `_init_ui` | 123 | 없음 |

합계 약 851줄.

### 범위 제외 (다음 사이클로 이연)

- **로직 함수**(`save_to_excel` 94, `_save_and_export` 82, `dhr_bulk_generator.generate`
  82, `record_view_dialog.save_changes` 64, `save_mixing_record` 57 등) — 분기/상태가
  있어 회귀 위험이 크고 테스트 보강이 선행되어야 함. → PDCA #14 후보.
- 60줄 이하 `_init_ui`(work_info 74, material_table 69, dhr_recipe_loader 64 등) —
  효과 대비 작아 후순위.
- 빌드/배포 스크립트(`build.py`, `deploy.py`, `check_release_artifacts.py`) — 도구.

---

## 3. 목표 (Goals)

1. 대상 5개 `_init_ui`를 **얇은 오케스트레이터(≤40줄)**로 축소.
2. 추출한 빌더 메서드는 각각 **하나의 시각적 섹션**만 담당, 각 ≤40줄.
3. **동작 0 변경** — 위젯 트리·시그널 연결·레이아웃 결과가 리팩토링 전후 동일.
4. 기존 65개 테스트 전부 통과 유지.

### 비목표 (Non-Goals)

- 위젯 구성·스타일·동작 변경 금지.
- 로직 함수 리팩토링(이연).
- 새 테스트 작성(별도 항목, coverage 사이클 소관).

---

## 4. 접근 방식

순수 **Extract Method** 리팩토링:

```
# Before
def _init_ui(self):
    # 섹션 A 위젯 200줄...
    # 섹션 B...
    # 섹션 C...

# After
def _init_ui(self):
    layout = QVBoxLayout(self)
    layout.addWidget(self._build_header())
    layout.addWidget(self._build_table_section())
    layout.addLayout(self._build_action_bar())

def _build_header(self) -> QWidget: ...
def _build_table_section(self) -> QWidget: ...
def _build_action_bar(self) -> QLayout: ...
```

- 인스턴스 속성(`self.xxx`)으로 노출돼야 하는 위젯은 빌더 안에서 그대로 `self.`에 할당.
- 섹션 경계는 기존 코드의 주석·시각 그룹을 따른다.
- 파일 단위로 진행하고 파일마다 스모크 실행으로 확인.

---

## 5. 리스크 및 대응

| 리스크 | 수준 | 대응 |
| --- | --- | --- |
| 위젯 참조 누락(`self.` 할당 빠짐) | 중 | 추출 후 `AttributeError` 스모크 확인, 파일별 검증 |
| 시그널 연결 순서 변동 | 중 | 빌더 호출 순서를 원본 코드 순서와 동일하게 유지 |
| 테스트 없는 4개 파일 | 중 | 리팩토링 전후 위젯 트리 스냅샷 수동 비교 + 앱 스모크 실행 |
| Python 3.9 호환 | 저 | 타입 힌트 `typing` 모듈 사용(CLAUDE.md 규칙) |

---

## 6. 검증 기준 (Definition of Done)

- [ ] 대상 5개 `_init_ui` 각각 ≤40줄
- [ ] 추출 빌더 메서드 각각 ≤40줄
- [ ] `python tests/run_tests.py` 65/65 통과
- [ ] 앱 스모크 실행 — 5개 화면 정상 렌더링
- [ ] `git diff` 검토 — 동작 변경 없음 확인

---

## 7. 다음 단계

1. **범위 승인** (이 문서) — 사용자 확인
2. `/pdca design long_function_refactor` — 파일별 섹션 분해 설계
3. `/pdca do` — 파일 단위 순차 구현
4. `/pdca analyze` — Gap 분석
5. `/pdca report` — 완료 보고

---

**작성일**: 2026-05-19
**버전**: 1.0
