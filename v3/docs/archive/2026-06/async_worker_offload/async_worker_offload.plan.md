# UI 스레드 분리 (비동기 워커 오프로드) — Plan

> PDCA Feature: `async_worker_offload` (PDCA #33)
> 작성일: 2026-06-10 · Level: Starter (Desktop / PySide6)

## 1. 배경 / 문제 정의

전체 코드 검토(2026-06-10, code-analyzer 82/100)에서 **Critical 등급 이슈 2건**이 확인되었다.
무거운 작업이 전부 **UI(메인) 스레드에서 동기 실행**되어, 작업 중 앱 전체가 멈춘다.

| # | 위치 | 작업 | 체감 증상 |
|---|------|------|-----------|
| 1 | `models/data_manager.py:193` (`save_record` → `_backup_to_google_sheets:142`) | gspread 네트워크 I/O (`open_by_url`/`append_rows`) | 배합 저장 버튼 클릭 → 네트워크 지연만큼 앱 정지 (현장 네트워크 불안정 시 수십 초) |
| 2 | `models/pdf_scan_renderer.py:69` (`_excel_to_temp_pdf`, win32com Excel) | Excel COM PDF 변환 (수 초~수십 초) | 기록 내보내기/대시보드 PDF 클릭 → 변환 끝날 때까지 UI 완전 정지, "응답 없음" 표시 |

해결 패턴은 코드베이스에 이미 존재한다: `ui/panels/admin_signature_panel.py:44`의
`GenerationWorker(QThread)` (finished/progress Signal 패턴), `pdf_processor_gui/worker.py`.
이번 사이클은 이 패턴을 **재사용 가능한 공통 워커**로 일반화해 두 핫스팟에 적용한다.

## 2. 목표 (Goals)

저장·내보내기 중에도 UI가 멈추지 않는다. 사용자는 진행 상태를 보고, 완료/실패를 알림으로 받는다.

### 요구사항 매핑

| # | 요구사항 | 충족 방법 |
|---|----------|-----------|
| 1 | 배합 저장 시 Sheets 백업이 UI를 막지 않음 | 백업을 백그라운드 워커로 분리. DB 저장(빠름)·재고 차감은 동기 유지 |
| 2 | PDF/Excel 내보내기가 UI를 막지 않음 | 내보내기 호출 경로를 워커로 이전 + 진행 표시 |
| 3 | 작업 중 중복 실행 방지 | 작업 중 해당 버튼 비활성화, 완료/실패 시 복원 |
| 4 | 실패가 조용히 사라지지 않음 | failed Signal → 기존 알림/상태 표시 경로로 메시지 전달 |
| 5 | COM 스레드 안전 | 워커 스레드에서 `pythoncom.CoInitialize()`/`CoUninitialize()` 보장 |

## 3. 범위 (Scope)

### In Scope
- **공통 워커 인프라** `v3/ui/workers.py` (신규): 함수 실행형 `FunctionWorker(QThread)`
  — `finished(object)` / `failed(str)` Signal, COM 초기화 옵션, 예외 → failed 변환
- **저장 경로 비동기화**: `save_record`에서 백업 호출 분리 → 저장 성공 직후 워커로 백업 실행
  (DB 저장 + 재고 차감은 기존 동기·동일 순서 유지, 백업 결과는 로그 + 상태 표시)
- **내보내기 비동기화 (3개 호출 경로)**:
  - 기록 조회 내보내기: `ui/record_ops_controller.py`
  - DHR 기록 내보내기: `ui/dhr_record_view_dialog.py` (`export_report`)
  - 대시보드 PDF/Excel: `ui/panels/dashboard_panel.py` (`_export_pdf`/`_export_excel`)
- 작업 중 버튼 비활성/대기 표시, 완료·실패 알림 (기존 UI 패턴 유지)
- 단위/통합(스모크) 테스트 + 기존 276개 테스트 회귀 없음

### Out of Scope (후속 사이클 후보)
- DHR 수기 입력 저장+내보내기(`manual_input_interface`)·대량 생성(`dhr_bulk_generator`) 비동기화
  — 오케스트레이션이 복잡해 별도 사이클로 분리
- Excel COM 탈피 (reportlab 등 네이티브 PDF 전환) — 근본 해결책이나 별도 혁신 사이클
- Sheets 백업 실패 시 로컬 큐 적재 + 재시도 (백업 견고화 사이클 #35 후보)
- 퍼센트 단위 진행률 바 (이번엔 busy 표시까지만)

## 4. 핵심 설계 결정 (요약 — 상세는 Design 문서)

1. **DataManager는 동기 순수성 유지**: `save_record`는 스레드를 직접 만들지 않는다.
   백업 페이로드 구성을 공개 메서드로 분리하고, **워커 실행은 UI 계층(controllers)** 책임.
   → models 계층에 Qt 의존성 유입 금지.
2. **QThread 함수 실행 패턴**: `GenerationWorker`처럼 케이스별 클래스 난립 대신,
   `FunctionWorker(fn, *args, use_com=False)` 하나로 일반화. 참조는 부모 위젯에 보관해 GC 방지.
3. **COM 안전**: `use_com=True`일 때 run() 진입/종료 시 CoInitialize/CoUninitialize.
   Excel COM은 워커 스레드에서만 Dispatch.
4. **순서 보장**: 저장 흐름은 "DB 저장 → 재고 차감(동기) → 백업(비동기 발사)" —
   백업 실패는 지금처럼 저장을 막지 않음(best-effort 의미 유지, 결과는 알림으로 승격).
5. **중복 실행 가드**: 워커 활성 중 해당 트리거 버튼 disable (전역 락 아님, 기능 단위).

## 5. 영향 범위 (변경 파일 예상)

| 파일 | 변경 |
|------|------|
| `v3/ui/workers.py` | **신규** — FunctionWorker 공통 인프라 |
| `v3/models/data_manager.py` | 백업 페이로드 구성 분리 (`build_backup_records` 류), `save_record`에서 백업 직접 호출 제거 |
| `v3/ui/controllers.py` | 저장 성공 후 백업 워커 실행 + 상태 표시 |
| `v3/ui/record_ops_controller.py` | 내보내기 워커 적용 + 버튼 가드 |
| `v3/ui/dhr_record_view_dialog.py` | export_report 워커 적용 |
| `v3/ui/panels/dashboard_panel.py` | PDF/Excel 내보내기 워커 적용 |
| `v3/tests/unit/test_workers.py` | **신규** — 워커 단위 테스트 |
| `v3/tests/` 기존 스모크 | 비동기 전환에 따른 호출 검증 보강 |

## 6. 리스크 / 완화

| 리스크 | 영향 | 완화 |
|--------|------|------|
| COM을 워커 스레드에서 호출 시 초기화 누락 → 크래시 | 높음 | `use_com` 옵션으로 CoInitialize 강제, finally에서 CoUninitialize |
| 워커 객체 GC로 스레드 조기 소멸 | 중 | 부모 위젯 속성에 워커 참조 보관, finished 시 해제 |
| 백업 비동기화로 "저장 완료" 알림 시점과 백업 결과 분리 | 중 | 저장 알림은 즉시, 백업 결과는 별도 상태 표시(성공 로그/실패 알림) — 기존 UX와 동일 의미 |
| 테스트 환경(headless)에서 QThread 타이밍 플레이크 | 중 | 단위 테스트는 run()을 동기 직접 호출, 통합은 시그널 spy + waitForFinished |
| 앱 종료 시 워커 미완료 | 저 | 종료 시 wait(타임아웃) 또는 데몬성 허용 — Design에서 결정 |
| Python 3.9 호환 | 중 | `Optional`/`Callable` typing 사용, `|` 유니온 금지 |

## 7. 완료 기준 (Definition of Done)

- [ ] 요구사항 1~5 모두 구현
- [ ] 저장/내보내기 중 UI 이벤트 루프 응답 유지 (수동 확인 + 스모크)
- [ ] gap-detector 일치율 ≥ 90%
- [ ] 신규 테스트 통과 + 기존 276개 테스트 회귀 없음
- [ ] UITheme 토큰 외 신규 스타일 하드코딩 없음
- [ ] 완료 보고서 작성

## 8. 다음 단계

→ `/pdca design async_worker_offload`
