# record_view_dialog 책임 분해 설계서 (PDCA #23)

> **Feature**: record_view_dialog_decomposition
> **Plan**: [../../01-plan/features/record_view_dialog_decomposition.plan.md](../../01-plan/features/record_view_dialog_decomposition.plan.md)
> **Author**: AI Assistant
> **Created**: 2026-05-31
> **Status**: 🔄 Design
> **PDCA Cycle**: #23

---

## 1. 설계 원칙
- **무동작변경**: 요약 메시지 문구·확인 다이얼로그·폴더 열기·새로고침·로그 메시지를 비트 보존.
- **뷰/오케스트레이션 분리**: 일괄 처리 루프·집계·per-item 로깅은 컨트롤러, 선택검사·확인·메시지·폴더열기는 뷰.
- **Qt 비의존 컨트롤러**: `RecordOpsController`는 PySide6 import 없이 data_manager만 의존 → 단독 단위 테스트.
- **DRY**: export/delete의 동일 루프를 `_run_batch`로 통합.
- **Python 3.9 / typing.**

## 2. RecordOpsController (`ui/record_ops_controller.py` 신설)

```python
from dataclasses import dataclass, field
from typing import Callable, List
from utils.logger import logger


@dataclass
class BatchResult:
    total: int
    success_count: int = 0
    fail_count: int = 0
    failed_lots: List[str] = field(default_factory=list)


class RecordOpsController:
    """기록 일괄 작업(출력/삭제)의 집계 오케스트레이션. Qt 비의존."""

    def __init__(self, data_manager) -> None:
        self.data_manager = data_manager

    def export_records(self, lots: List[str], effects_params,
                       include_work_time: bool = True) -> BatchResult:
        def op(lot: str) -> bool:
            logger.info(f"엑셀/PDF 재출력 시작: LOT {lot}")  # 현행 per-item 로그 보존
            return bool(self.data_manager.export_existing_record(
                lot, effects_params, include_work_time=include_work_time))
        return self._run_batch(lots, op, "엑셀/PDF 재출력")

    def delete_records(self, lots: List[str]) -> BatchResult:
        def op(lot: str) -> bool:
            return bool(self.data_manager.delete_record(lot))
        return self._run_batch(lots, op, "배합 기록 삭제")

    def _run_batch(self, lots: List[str], op: Callable[[str], bool],
                   action_label: str) -> BatchResult:
        result = BatchResult(total=len(lots))
        for lot in lots:
            try:
                if op(lot):
                    result.success_count += 1
                else:
                    result.fail_count += 1
                    result.failed_lots.append(lot)
            except Exception as e:
                result.fail_count += 1
                result.failed_lots.append(lot)
                logger.error(f"{action_label} 오류: LOT {lot}, 오류: {e}")
        return result
```

### 2.1 로그 메시지 보존 매핑
| 원본(record_view_dialog) | 컨트롤러 |
|---|---|
| `엑셀/PDF 재출력 시작: LOT {lot}` (export 루프 진입) | `export_records.op` 내부 |
| `엑셀/PDF 재출력 오류: LOT {lot}, 오류: {e}` | `_run_batch` action_label="엑셀/PDF 재출력" |
| `배합 기록 삭제 오류: LOT {lot}, 오류: {e}` | `_run_batch` action_label="배합 기록 삭제" |

(export의 pdf 실패(None)→fail 무로그, delete의 시작 무로그 — 현행과 동일)

## 3. 다이얼로그 위임 (`record_view_dialog.py`)

### 3.1 `RecordViewDialog.__init__`
```python
from ui.record_ops_controller import RecordOpsController
...
self._ops = RecordOpsController(data_manager)
```

### 3.2 `export_selected_record`
```python
def export_selected_record(self):
    checked = self._get_checked_lots()
    if not checked:
        QMessageBox.warning(self, "경고", "출력할 기록을 선택하세요.")
        return
    include_time = self.chk_include_time_export.isChecked()
    result = self._ops.export_records(checked, self.effects_params, include_work_time=include_time)
    summary = f"총 {result.total}건 중 {result.success_count}건 성공, {result.fail_count}건 실패."
    if result.failed_lots:
        summary += f"\n실패 LOT: {', '.join(result.failed_lots)}"
    if result.success_count > 0:
        reply = QMessageBox.question(
            self, "출력 완료" if result.fail_count == 0 else "부분 출력 완료",
            f"{summary}\n\n결과 폴더를 확인하시겠습니까?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
        if reply == QMessageBox.Yes:
            self._open_output_folder()
    else:
        QMessageBox.warning(self, "출력 실패", summary)
```

### 3.3 `delete_selected_record`
```python
def delete_selected_record(self):
    checked = self._get_checked_lots()
    if not checked:
        QMessageBox.warning(self, "경고", "삭제할 기록을 선택하세요.")
        return
    reply = QMessageBox.question(
        self, "삭제 확인",
        f"총 {len(checked)}개의 기록을 정말 삭제하시겠습니까?\n\n이 작업은 되돌릴 수 없습니다.",
        QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
    if reply == QMessageBox.No:
        return
    result = self._ops.delete_records(checked)
    summary = f"총 {result.total}건 중 {result.success_count}건 삭제 성공, {result.fail_count}건 실패."
    if result.failed_lots:
        summary += f"\n실패 LOT: {', '.join(result.failed_lots)}"
    QMessageBox.information(self, "삭제 완료", summary)
    self.load_records()
```

- 기존 `_get_checked_lots`·`_open_output_folder`·`load_records`는 뷰에 유지.
- 메시지 문구(success "성공" vs delete "삭제 성공")는 뷰에 유지 → 컨트롤러는 수치만.

## 4. 테스트 설계

### 4.1 `tests/unit/test_record_ops_controller.py` (Qt 비의존)
mock `data_manager`로:
- `test_export_all_success`: export_existing_record가 항상 경로 반환 → success=total, fail=0.
- `test_export_partial_failure`: 일부 None 반환 → fail 집계 + failed_lots.
- `test_export_exception`: 일부 예외 → fail 집계(예외 전파 안 함).
- `test_export_passes_params`: effects_params/include_work_time가 data_manager에 전달됨(call_args 검증).
- `test_delete_all_success` / `test_delete_partial` / `test_delete_exception`: delete 동일 패턴.
- `BatchResult` 기본값(success/fail 0, failed_lots 빈 리스트) 검증.

### 4.2 시각 스모크 (offscreen)
- `RecordViewDialog(data_manager, effects_params)` 인스턴스화 + `self._ops`가 `RecordOpsController`인지.
- mock data_manager로 `export_selected_record`/`delete_selected_record`를 (체크 0건 경고 경로) 호출 시 예외 0.
- (기존 `test_record_view_dialog_helpers`가 있으면 회귀 포함.)

### 4.3 전체 회귀
- `pytest tests/unit tests/integration` 통과(현 128 + 신규), stderr 노이즈 0.

## 5. 위험 재확인
| 위험 | 결정 |
|---|---|
| 요약 문구 변경 | 문구 뷰 유지, 컨트롤러 수치만 — 비트 보존 |
| per-item 로그 누락 | export "재출력 시작" op 내부 보존, 오류 로그 action_label 매핑 |
| effects_params/include_work_time 누락 | export_records 시그니처에 동일 전달, call_args 테스트 |
| 다이얼로그 시각 회귀 | offscreen 스모크 + 기존 helper 테스트 |

## 6. 커밋 계획
1. `feat(ui): add RecordOpsController for batch export/delete (PDCA #23 A)`
2. `refactor(ui): delegate batch export/delete to RecordOpsController (PDCA #23 B)`
3. `test: RecordOpsController batch tests + dialog smoke (PDCA #23)`
4. `docs: PDCA #23 analysis + report`

## 7. 다음 단계
`/pdca do record_view_dialog_decomposition` — 커밋 1부터, 각 단계 후 전체 스위트 + 시각 스모크.
