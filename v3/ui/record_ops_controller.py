"""기록 일괄 작업 컨트롤러 (PDCA #23).

선택된 기록의 일괄 출력/삭제를 오케스트레이션하고 성공·실패를 집계한다.
PySide6 비의존 — data_manager만 의존하여 단독 단위 테스트가 가능하다.
"""
from dataclasses import dataclass, field
from typing import Callable, List

from utils.logger import logger


@dataclass
class BatchResult:
    """일괄 작업 집계 결과."""
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
        """선택 LOT들을 엑셀/PDF로 재출력하고 결과를 집계한다."""
        def op(lot: str) -> bool:
            logger.info(f"엑셀/PDF 재출력 시작: LOT {lot}")
            return bool(self.data_manager.export_existing_record(
                lot, effects_params, include_work_time=include_work_time))
        return self._run_batch(lots, op, "엑셀/PDF 재출력")

    def delete_records(self, lots: List[str]) -> BatchResult:
        """선택 LOT들을 삭제하고 결과를 집계한다."""
        def op(lot: str) -> bool:
            return bool(self.data_manager.delete_record(lot))
        return self._run_batch(lots, op, "배합 기록 삭제")

    def _run_batch(self, lots: List[str], op: Callable[[str], bool],
                   action_label: str) -> BatchResult:
        """공통 일괄 루프: per-item 성공/실패 집계, 예외는 실패로 흡수(전파 안 함)."""
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
