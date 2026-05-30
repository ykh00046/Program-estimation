# test_hang_and_statusbar_cleanup — Completion Report (PDCA #20, 경량)

> **Feature**: test_hang_and_statusbar_cleanup
> **Author**: AI Assistant
> **Created**: 2026-05-31
> **Status**: ✅ Completed
> **Plan**: [../../01-plan/features/test_hang_and_statusbar_cleanup.plan.md](../../01-plan/features/test_hang_and_statusbar_cleanup.plan.md)
> **PDCA Cycle**: #20 (경량 — Plan + Report)

---

## 1. 요약

PDCA #19 후속 후보 2건을 경량 사이클로 종결.

1. **전체 테스트 디스커버리 hang 근절** — `pytest tests/unit tests/integration`가 모달 다이얼로그에서 무한 정지하던 문제 해결. 이제 **120 케이스 전체가 hang 없이 완주**(13.85s).
2. **`SidebarRefs.mixing_status_bar` 단일소스화** — 파생 중복 필드 제거.

## 2. 진단 (근본 원인)

전체 스위트 hang의 범인은 `test_bulk_helpers.py::test_generate_product_lot_logs_korean_fallback_message`:
- `_generate_product_lot_with_conn`을 예외로 모킹 → `@handle_exceptions` → `show_error_message` → `_show_message`의 **`QMessageBox.exec()`가 offscreen에서 무한 블록**.

`pytest-timeout`(`--timeout=20 --timeout-method=thread`)으로 정지 스택을 떠서 정확히 특정.

추가로, 진단 중 **잠재 버그** 발견: `get_connection`(SqliteManagerBase, #18)이 `sqlite3.Error`를 `DatabaseError`로 변환하므로, `generate_product_lot`의 `except sqlite3.Error` fallback은 in-block DB 오류를 **절대 포착 못 하는 죽은 코드**였다. hang이 이 결함을 가리고 있었다.

## 3. 변경 (커밋)

| 커밋 | 내용 |
|---|---|
| `1de733a` | **Part A**: `SidebarRefs`에서 `mixing_status_bar` 필드 제거, `main_window`가 `mixing_page_refs.status_bar`에서 파생(속성 유지, 무동작변경) |
| `4a76686` | **Part B**: ① `error_handler._show_message` 헤드리스 가드(offscreen→로그 폴백) ② `generate_product_lot` except를 `(sqlite3.Error, DatabaseError)`로 교정(fallback 실동작화) ③ `test_bulk_helpers` 모킹을 `sqlite3.OperationalError`로, 기대 메시지를 DatabaseError 래핑 형태로 갱신 |

## 4. 검증

- **`pytest tests/unit tests/integration` → 120 passed, hang 0, 13.85s** (이전: 영구 정지)
- MainWindow offscreen 스모크: `mixing_status_bar is mixing_page_refs.status_bar` 단일소스 확인, `_set_status_message`/statusbar 정상
- 회귀 0건

## 5. 성공 기준 달성 (Plan §4)

- [x] 전체 스위트 hang 없이 완료 (120 케이스)
- [x] `test_generate_product_lot_logs_korean_fallback_message` 통과
- [x] `SidebarRefs`에 `mixing_status_bar` 필드 없음, MainWindow 동작 불변
- [x] 회귀 0건

## 6. 스코프 조정 (Plan 대비)

Plan은 `generate_product_lot` except 변경을 "비-범위(광역화 안 함)"로 두었으나, 진단 결과 **`except sqlite3.Error`가 post-#18 죽은 코드**임이 드러났다. 이는 "광역화"가 아니라 `get_connection`이 실제 던지는 `DatabaseError`를 포착하도록 하는 **타입 교정(버그 수정)**이므로 범위에 포함. 프로그래밍 오류(RuntimeError 등)는 여전히 전파되어 설계 의도 보존.

## 7. 교훈

1. **`pytest-timeout`은 hang 진단의 표준 도구** — `--timeout-method=thread`로 정지 스택을 떠 모달 `exec()` 호출 지점을 즉시 특정.
2. **헤드리스 가드는 UI 유틸의 필수 방어** — `QMessageBox.exec()` 같은 모달은 offscreen에서 영구 블록. `platformName()=="offscreen"` 가드로 전 테스트 클래스의 hang을 근절(개별 테스트 mock보다 견고).
3. **공통 인프라 변경(#18 get_connection)은 호출자의 예외 처리를 무력화할 수 있다** — `except sqlite3.Error`가 DatabaseError 변환으로 죽은 코드가 됨. 인프라 도입 시 호출자 except 절 전수 점검 필요.
4. **hang은 그 뒤의 단언 실패를 가린다** — 모달 블록이 없었다면 이 테스트는 진작 단언 실패로 잡혔을 것. hang 정상화가 잠재 결함 발견의 전제.

## 8. 후속 / 잔여 관찰

- **로그 로테이션 PermissionError** — 동시 테스트 실행 시 `TimedRotatingFileHandler.doRollover`가 잠긴 로그 파일 rename에 실패(WinError 32). 테스트 실패는 아니나 stderr 노이즈. 별도 후보(로깅 핸들러 동시성/테스트 격리).
- 예외 협소화(코드검토 잔여)는 대부분 의도적이라 보류 유지.

## 9. 결론

PDCA #20 완료. 전체 테스트 스위트가 신뢰성 있게 완주하게 되어, 향후 회귀 검증이 targeted 우회 없이 전체 실행으로 가능. statusbar 중복도 단일소스화. 다음은 `/pdca archive`로 #20 문서 이관(경량: plan/report 2종) 가능.
