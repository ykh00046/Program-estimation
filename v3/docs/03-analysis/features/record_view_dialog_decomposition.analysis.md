# record_view_dialog 책임 분해 Gap 분석 (PDCA #23)

> **Feature**: record_view_dialog_decomposition
> **Plan**: [../../01-plan/features/record_view_dialog_decomposition.plan.md](../../01-plan/features/record_view_dialog_decomposition.plan.md)
> **Design**: [../../02-design/features/record_view_dialog_decomposition.design.md](../../02-design/features/record_view_dialog_decomposition.design.md)
> **Author**: AI Assistant
> **Created**: 2026-05-31
> **Status**: ✅ Match Rate 100% (§4.2 스모크 보강 후)
> **PDCA Cycle**: #23

---

## 1. 분석 개요
- 대상: 일괄 출력/삭제 tally 루프를 `RecordOpsController`로 추출 + 다이얼로그 위임
- 구현 커밋: `2a23d2f`(컨트롤러), `a4b368e`(위임), `9d72f44`(단위 테스트), `5390b92`(다이얼로그 스모크)
- 검증: bkit:gap-detector

## 2. 종합 점수

| 항목 | 점수 |
|---|:---:|
| 컨트롤러(§2) | 100% |
| 로그 보존(§2.1) | 100% |
| 다이얼로그 위임(§3) | 100% |
| 무동작변경(§1) | 100% |
| 테스트(§4) | 100% (스모크 보강) |
| **종합** | **100%** |

## 3. 항목별 결과 (전부 일치)
- **RecordOpsController**: `BatchResult` 4필드 + `export_records(lots, effects_params, include_work_time)`/`delete_records(lots)` + `_run_batch`(per-item try/집계/예외흡수). Qt import 0(`dataclasses/typing/utils.logger`만).
- **로그 보존**: export "재출력 시작" per-item, 오류 로그 action_label 매핑("엑셀/PDF 재출력 오류"/"배합 기록 삭제 오류")으로 원본과 동일.
- **다이얼로그 위임**: `__init__`의 `self._ops`, export/delete_selected_record가 컨트롤러 호출 + 요약 문구("성공" vs "삭제 성공") 뷰 유지. tally 루프·data_manager 직접호출 제거.
- **무동작변경**: 경고/확인 문구·기본 No·제목 분기·`_open_output_folder`·`load_records` 보존.
- **테스트**: 단위 8케이스(export 4 + delete 3 + BatchResult 1) + 다이얼로그 스모크 3케이스.

## 4. Gap (gap-detector 1차 97% → 보강 후 100%)
| Gap | 조치 |
|---|---|
| §4.2 다이얼로그 offscreen 스모크 미커밋(Low) | `tests/integration/test_record_view_dialog_smoke.py` 추가(인스턴스화 + 위임 + 빈선택 경고 경로 3케이스, `5390b92`) → 해소 |
| 단위 테스트 명명 간결화(정보성) | 케이스 커버리지 동일, 영향 없음 |

## 5. 범위 외 관찰 (다음 후보)
- `RecordDetailDialog._build_button_bar`가 **두 번 정의**(record_view_dialog.py:103, :196) — 두 번째가 첫 번째를 덮어씀. #23 이전부터 존재한 별개 결함. 본 사이클 무관(비-범위), **PDCA #24 후보로 기록**.

## 6. 실행 검증
- 단위(RecordOpsController 8 + helper) + 스모크 3 통과.
- 전체 스위트 `pytest tests/unit tests/integration`: **136 passed**(128→136), hang 0, stderr 노이즈 0.
- offscreen 위임 스모크: export/delete 각 2회 위임 + `include_work_time=True` 전달 확인.

## 7. 결론
Match Rate **100%** → `/pdca report` 진행 가능. 코드검토 SRP 후보(excel_exporter, record_view_dialog) 모두 종결.
