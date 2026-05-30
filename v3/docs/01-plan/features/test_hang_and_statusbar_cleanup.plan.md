# 테스트 hang 정상화 + statusbar 단일소스 (PDCA #20, 경량)

> **Feature**: test_hang_and_statusbar_cleanup
> **Author**: AI Assistant
> **Created**: 2026-05-30
> **Status**: ✅ Plan
> **PDCA Cycle**: #20 (경량 — Plan + Report, PDCA #19 후속 정리 2건)

---

## 1. 배경

PDCA #19 보고서가 후속 후보로 남긴 2건을 경량 사이클로 종결.

1. **전체 테스트 디스커버리 hang** — `pytest tests/unit tests/integration` 전체 실행이 특정 테스트에서 무한 정지하여, 그동안 targeted 실행으로만 회귀를 검증해 왔다.
2. **`SidebarRefs.mixing_status_bar` 파생 중복** — refs가 `mixing_page_refs.status_bar`를 별도 필드로 중복 보유(PDCA #19에서 무동작변경 위해 의도적 보존).

### hang 근본 원인 (진단 완료)

`tests/unit/test_bulk_helpers.py::test_generate_product_lot_logs_korean_fallback_message`:
- `_generate_product_lot_with_conn`을 `RuntimeError("boom")`로 모킹
- `dhr_database.generate_product_lot`의 내부 `except sqlite3.Error`가 RuntimeError를 못 잡음 → 예외 전파
- `@handle_exceptions` → `show_error_message` → `error_handler._show_message`의 **`msg_box.exec()` 모달이 offscreen(헤드리스)에서 무한 블록**

→ 인프라 결함(모달 블록)과 테스트 결함(비현실적 예외 타입)이 겹침.

## 2. 범위 (In Scope)

### Part A — statusbar 단일소스 (무동작변경)
- `SidebarRefs`에서 `mixing_status_bar` 필드 제거 (단일 소스 = `mixing_page_refs.status_bar`).
- `register_sidebar_interfaces` 반환에서 해당 키 제거.
- `main_window._create_central_widget`: `self.mixing_status_bar = refs.mixing_page_refs.status_bar`로 파생.
- `self.mixing_status_bar` window 속성은 `_set_status_message`/`setup_statusbar`가 소비하므로 **유지**.

### Part B — 테스트 hang 정상화
- **인프라 가드**: `error_handler._show_message`가 offscreen(헤드리스)에서는 모달 대신 로그로 폴백 → 예외 경로를 타는 모든 테스트의 hang 근절. 프로덕션은 offscreen이 아니므로 영향 없음.
- **테스트 수정**: `test_bulk_helpers`의 모킹을 `RuntimeError` → `sqlite3.OperationalError`(실제 fallback이 처리하는 `sqlite3.Error`)로 교체. `generate_product_lot`의 좁은 except는 설계상 정당(프로그래밍 오류 RuntimeError는 전파되어야 함)하므로 프로덕션 변경 없음.

## 3. 비-범위 (Out of Scope)
- `generate_product_lot` except 광역화(프로그래밍 오류 전파가 옳음 — 변경 안 함)
- 다른 패널의 예외 협소화 (대부분 의도적, 별도 후보)
- 모달 헬퍼의 추가 리팩터(스타일 등)

## 4. 성공 기준
- [ ] `pytest tests/unit tests/integration` 전체가 hang 없이 완료 (120 케이스)
- [ ] `test_generate_product_lot_logs_korean_fallback_message` 통과
- [ ] `SidebarRefs`에 `mixing_status_bar` 필드 없음, MainWindow 동작 불변
- [ ] 회귀 0건

## 5. 위험 & 완화
| 위험 | 완화 |
|---|---|
| 헤드리스 가드가 프로덕션 모달까지 막음 | 가드는 `platformName()=="offscreen"` 또는 QApplication 부재일 때만 발동. 프로덕션은 실제 플랫폼 → 영향 없음 |
| statusbar 파생 변경으로 setup_statusbar 깨짐 | `self.mixing_status_bar` 속성 유지, 소스만 `mixing_page_refs.status_bar`로 명시 |
| 다른 hang 테스트 잔존 | 전체 스위트 1회 완주로 확인 |

## 6. 커밋 계획
1. `fix(ui): guard modal dialogs in headless + single-source mixing_status_bar (PDCA #20)`
2. `test: fix bulk_helpers to raise sqlite3 error (PDCA #20)`
3. `docs: PDCA #20 report`

## 7. 다음 단계
구현 → `pytest tests/unit tests/integration` 전체 완주 검증 → `/pdca report`.
