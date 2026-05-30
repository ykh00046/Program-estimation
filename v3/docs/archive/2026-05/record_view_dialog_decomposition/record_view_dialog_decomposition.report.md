# record_view_dialog_decomposition — Completion Report (PDCA #23)

> **Feature**: record_view_dialog_decomposition
> **Author**: AI Assistant
> **Created**: 2026-05-31
> **Status**: ✅ Completed
> **Match Rate**: 100%
> **Plan**: [../../01-plan/features/record_view_dialog_decomposition.plan.md](../../01-plan/features/record_view_dialog_decomposition.plan.md)
> **Design**: [../../02-design/features/record_view_dialog_decomposition.design.md](../../02-design/features/record_view_dialog_decomposition.design.md)
> **Analysis**: [../../03-analysis/features/record_view_dialog_decomposition.analysis.md](../../03-analysis/features/record_view_dialog_decomposition.analysis.md)

---

## 1. 요약

코드 검토(2026-05-29) SRP 후보의 마지막 항목 종결. `record_view_dialog.py`의 일괄 출력/삭제 **tally 루프**(성공·실패 집계가 `QMessageBox`와 뒤섞여 Qt 없이 검증 불가)를 Qt 비의존 `RecordOpsController`로 추출.

- `ui/record_ops_controller.py`: `BatchResult` + `export_records`/`delete_records` + 공통 `_run_batch`. data_manager만 의존 → 단독 테스트 가능.
- 다이얼로그는 선택검사·확인·요약 메시지·폴더열기·새로고침만 담당(데이터 루프 제거).

## 2. 변경 (커밋, origin/main 반영 예정)

| 커밋 | 내용 |
|---|---|
| `2a23d2f` | RecordOpsController 추가(Part A) |
| `a4b368e` | 다이얼로그 위임(Part B) |
| `9d72f44` | 컨트롤러 단위 테스트 8케이스 |
| `5390b92` | RecordViewDialog offscreen 스모크 3케이스(§4.2) |

## 3. 검증
- 단위 8 + 스모크 3 통과, 전체 스위트 **136 passed**(128→136), hang 0, stderr 노이즈 0.
- offscreen 위임 스모크: export/delete 각 2회 위임 + include_work_time 전달.
- gap-detector **Match 100%**(1차 97% → §4.2 스모크 보강).

## 4. 성공 기준 달성 (Plan §4)
- [x] 일괄 출력/삭제 집계가 Qt 비의존 컨트롤러로 분리, 단독 테스트 가능
- [x] 다이얼로그는 선택검사·확인·메시지·폴더열기만(데이터 루프 제거)
- [x] 메시지/동작 현행 보존(무동작변경)
- [x] 전체 스위트 통과 + 시각 스모크
- [x] Match Rate ≥ 90% (100%)

## 5. 교훈
1. **UI 다이얼로그의 직접 `QMessageBox.warning/question` 정적 호출도 offscreen에서 모달 블록** — PDCA #21 헤드리스 가드는 `error_handler`만 커버. 다이얼로그 메서드를 스모크로 호출하려면 `QMessageBox`를 patch해야 함(빈 선택 경고 경로가 모달 트리거).
2. **일괄 처리 tally 루프는 컨트롤러로 빼면 즉시 테스트 가능** — try/집계/예외흡수가 UI와 분리되어 mock data_manager만으로 전체성공/부분실패/예외 흡수 검증.
3. **메시지 문구는 뷰에, 수치는 컨트롤러에** — export "성공" vs delete "삭제 성공" 차등을 컨트롤러로 올리지 않아 무동작변경 보장 + 결합 최소화.

## 6. 범위 외 관찰 (PDCA #24 후보)
- `RecordDetailDialog._build_button_bar`가 두 번 정의(record_view_dialog.py:103, :196)되어 첫 정의가 덮어써짐 — 본 사이클 이전부터의 별개 결함. 정리 후보.

## 7. 결론
PDCA #23 완료. 2026-05-29 코드 검토에서 도출된 SRP 후보(excel_exporter #22, record_view_dialog #23)가 모두 종결됨. 다음은 `/pdca archive record_view_dialog_decomposition`.
