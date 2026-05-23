# database_save_refactor — Plan

> **PDCA #16**
> **Author**: AI Assistant
> **Created**: 2026-05-23
> **Status**: 🔄 In Progress
> **Origin**: `improvement.plan.md` #9 — 함수 길이 리팩토링 (잔여분 종결)

---

## 1. 배경 및 동기

`improvement.plan.md` #9(함수 길이 리팩토링)는 SRP/20줄 기준에 따라 다음 후보를 식별했다.

| 함수 | 원본 LOC | 기존 처리 |
| --- | --- | --- |
| `MainWindow._init_ui()` | 213 | PDCA #7에서 MainWindow 리팩토링으로 해소 |
| `DataManager.save_record()` | 51 | PDCA #15 Part C에서 처리(또는 임계 근접) |
| `DatabaseManager.save_mixing_record()` | 57 (실측) | **본 PDCA에서 처리** |
| `RecordViewDialog.save_changes()` | 64 (실측) | **본 PDCA에서 처리** |

`logic_function_refactor.plan.md` (PDCA #15)에서 두 함수는 **범위 초과**로 명시적 이연했고, `logic_function_refactor.analysis.md`는 둘을 **PDCA #16 후보**로 못박았다. 본 PDCA가 그 #16이며, 완료 시 `improvement.plan.md` #9는 완전 종결된다.

---

## 2. 목표

1. `database.save_mixing_record` 본문을 **20줄 이내**로 축소하면서 동작·서명·외부 인터페이스는 동일 유지.
2. `record_view_dialog.save_changes` 본문을 **20줄 이내**로 축소하면서 동작·시그널 흐름은 동일 유지.
3. `save_changes` 헬퍼는 **단위 테스트 가능한 형태**로 추출하여 회귀 안전망 확보 (현재 단위 테스트 0건).
4. `improvement.plan.md` 진행 현황 표에서 #9를 **✅ 완료** 로 갱신.

### 비목표 (Non-Goals)

- 새로운 기능 추가, DB 스키마 변경, 시그널 시그니처 변경.
- `data_manager.save_record` 추가 분해 (PDCA #15 범위, 본 PDCA에서 손대지 않음).
- UI 룩앤필 변경 — 본 작업은 코드 구조만 다룬다.

---

## 3. 범위

### 수정 파일

- `v3/models/database.py` — `save_mixing_record` 분해
- `v3/ui/record_view_dialog.py` — `save_changes` 분해
- `v3/tests/unit/` — `save_changes` 헬퍼 단위 테스트 신설 (DB·UI에 의존하지 않는 추출 영역만)

### 영향 받지 않는 파일

- `data_manager.py` 호출부, `record_view_dialog` 외부 사용자, 기존 시그널 핸들러.

---

## 4. 리스크 및 대응

| 리스크 | 수준 | 대응 |
| --- | --- | --- |
| `save_mixing_record` 동작 회귀 | 낮음 | `data_manager` 통합 테스트(`tests/integration/test_data_integration.py`)와 `unit/test_data_manager.py`로 간접 커버. |
| `save_changes` 동작 회귀 | **중간** | 단위 테스트 0건이므로 헬퍼를 **DB/UI 디펜던시에서 분리 가능한 단위**로 추출 후 신규 단위 테스트 작성 (Part C). |
| 메인 함수 본문이 헬퍼 호출로 과도하게 얇아져 가독성 저하 | 낮음 | 헬퍼 명세는 동사구 + 단일 책임 유지, 메인 함수에 절차 흐름이 그대로 읽히는 형태로 추출. |

---

## 5. 성공 기준 (Definition of Done)

- [ ] `save_mixing_record` 본문 ≤ 20줄 (docstring/공백 제외).
- [ ] `save_changes` 본문 ≤ 20줄 (docstring/공백 제외).
- [ ] 기존 테스트 전부 통과: `python v3/tests/run_tests.py` 또는 동등.
- [ ] `save_changes` 헬퍼에 대한 신규 단위 테스트 1개 이상 통과.
- [ ] gap-detector Match Rate ≥ 90%.
- [ ] `improvement.plan.md` 진행 현황 표 #9 = ✅ 완료.

---

## 6. 후속 작업

- `improvement.plan.md` #2(.venv 정리), #10(DRY 재정의)만 잔여 → 별도 PDCA에서 처리.
- PDCA #15 Part B/C는 본 PDCA와 독립 — 본 PDCA 완료가 #15 진행을 차단하거나 보조하지 않음.
