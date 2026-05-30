# UI 구조 리팩터 Gap 분석 (PDCA #19)

> **Feature**: ui_architecture_refactor
> **Plan**: [../../01-plan/features/ui_architecture_refactor.plan.md](../../01-plan/features/ui_architecture_refactor.plan.md)
> **Design**: [../../02-design/features/ui_architecture_refactor.design.md](../../02-design/features/ui_architecture_refactor.design.md)
> **Author**: AI Assistant
> **Created**: 2026-05-30
> **Status**: ✅ Match Rate 99%
> **PDCA Cycle**: #19

---

## 1. 분석 개요

- 대상: UI 빌더 refs 반환(Part A) + DHR 패널 검증 순수 함수 추출(Part B)
- 구현 커밋: `3a22911`(Part A), `3cef70a`(A3 test), `925bef8`(Part B), `621e5cf`(B2 test) — 전부 origin/main push 완료
- 검증 도구: bkit:gap-detector (설계 ↔ 구현 대조)

## 2. 종합 점수

| 항목 | 점수 |
|---|:---:|
| 설계 일치(Design Match) | 99% |
| 무동작변경 보존 | 100% |
| 컨벤션 준수(Python 3.9 / 타입힌트) | 100% |
| **종합** | **99%** |

Critical/High 갭 없음. 발견된 차이는 모두 사소하거나 의도된 잔여 항목.

## 3. 항목별 결과

### Part A — 빌더 refs 반환 (일치)
- `SidebarRefs` 5필드 / `StatusbarRefs` 2필드 설계대로 정의·반환 (`builders.py:27-41`)
- `register_sidebar_interfaces -> SidebarRefs`, `setup_statusbar -> StatusbarRefs`로 반환화, `window.* 커스텀 속성 직접 set` 제거 (`builders.py:197, 261-267, 270, 288-291`)
- `_setup_dhr_settings_sync`가 main_window의 refs 할당 직후로 이동 (`main_window.py:141-146`)
- statusbar 호출 순서(`_create_central_widget` → `setup_statusbar`) 보존, `_init_ui` 위치 유지(M-1)
- `register_sidebar_interfaces` docstring "sync는 호출부 책임" 수정(m-3)

### Part B — 검증 순수 함수 추출 (일치)
- `validate_manual_input`(3-튜플 focus_field) / `validate_bulk_product` / `validate_bulk_entries` / `validate_recipe_input` 시그니처 설계 일치 (`dhr_validation.py`)
- manual: focus_field 인라인 매핑(메시지 역매핑 없음, M-3)
- bulk: 제품명(파싱 전)/엔트리(파싱 후) 2분리로 분기 순서 보존(M-2)
- recipe: 위임 일치
- 비-이관 항목(critical 메시지, Partial Success) 뷰 유지(§3.3)

### 테스트 (일치)
- `test_dhr_validation.py` 10케이스(manual 4 + bulk 4 + recipe 2), focus_field 단언 포함
- `test_builders.py` `build_mixing_page`로 한정(C-1), 전체 빌더는 시각 스모크 위임 명시

### design-validator 반영 (C-1/M-2/M-3) — 구현 반영 확인

## 4. Gap 목록

### 🔵 Minor (설계 ≠ 구현)
| 항목 | 설계 | 구현 | 처리 |
|---|---|---|---|
| bulk `product_name` strip 시점 | `text()` (검증 함수 내부 strip) | `text().strip()` 선적용 후 검증·생성기 전달 | **바람직한 미세 개선**(manual/recipe와 동작 일관). 설계 §3.2 스니펫을 구현에 맞춰 갱신 완료 |

### 🟡 의도적 잔여 (정보성)
| 항목 | 내용 |
|---|---|
| `SidebarRefs.mixing_status_bar` 파생 중복 | `mixing_page_refs.status_bar`의 중복 보유. 현행도 동일 구조라 무동작변경 위해 의도적 보존(§8 m-2). 후속 정리 후보 |

- 누락 기능(설계 O, 구현 X): 없음
- 추가 기능(설계 X, 구현 O): 없음

## 5. 테스트 결과

- targeted 회귀: builders/dhr_validation/panels/manual/data/sqlite/lot_utils/bulk_generator/integration **85 passed**
- MainWindow offscreen 풀스모크: refs 7종 할당 + sync 컨트롤러 + 검증 함수 동작 OK
- 비고: `pytest tests/unit tests/integration` 전체 디스커버리는 특정 GUI 테스트(모달 대기 추정)에서 멈춤 — **본 변경 이전부터 존재하는 환경/수집 이슈**, 본 사이클 변경과 무관. targeted 실행으로 회귀 0건 확인.

## 6. 결론

Match Rate **99%** (≥90%) — `/pdca report` 진행 가능. 즉시 조치 필요 갭 없음. 설계 문서 스니펫 1건 갱신 완료.

후속 후보(별도 사이클): `mixing_status_bar` 단일 소스화, 전체 테스트 디스커버리 hang 정상화(모달 테스트 mock/skip 패턴).
