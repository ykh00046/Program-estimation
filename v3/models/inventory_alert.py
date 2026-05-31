"""자재 재고 임계값 평가 — 순수 로직 (Qt·DB 무의존, 단독 테스트 대상).

PDCA #27 inventory_threshold_alert. 사용자가 자재별 **현재 재고**(current_stock)와
**최소 임계값**(min_stock_threshold)을 수동 관리하고, 현재 재고가 임계값 이하로
떨어지면 경고한다. 입고/발주/자동 차감은 비-범위(경량 수동 재고 모델).

DB 스키마는 기존 ``material_stock`` 테이블을 재사용한다
(``get_all_material_stock`` 반환 행 형태를 입력으로 받는다).
"""
from typing import Dict, List, NamedTuple

LEVEL_OUT = "OUT_OF_STOCK"  # 현재고 <= 0 (품절)
LEVEL_LOW = "LOW_STOCK"  # 0 < 현재고 <= 임계값 (부족)


class MaterialAlert(NamedTuple):
    """단일 자재의 재고 경고."""

    material_code: str
    material_name: str
    current_stock: float
    threshold: float
    shortfall: float  # max(0, threshold - current_stock)
    level: str  # LEVEL_OUT | LEVEL_LOW


def _coerce_float(value: object) -> float:
    """None/문자열 등을 안전하게 float로 변환 (실패 시 0.0)."""
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0.0


def evaluate_inventory_alerts(
    inventory_rows: List[Dict], default_threshold: float = 0.0
) -> List[MaterialAlert]:
    """재고 행에서 임계값 이하 자재의 경고 목록을 만든다.

    유효 임계값 = 자재별 ``min_stock_threshold`` > 0 이면 그 값, 아니면
    ``default_threshold``(전역 기본 임계값). 유효 임계값이 0 이하인 자재는 제외한다.
    현재고 <= 유효 임계값이면 경고: 현재고 <= 0 → OUT_OF_STOCK, 아니면 LOW_STOCK.
    현재고 > 유효 임계값(OK)은 제외한다. 부족분 내림차순 정렬.

    이 함수는 DB 계층 ``get_low_stock_materials`` SQL 평가와 동일 규칙을 가지며
    (parity), Qt·DB 무의존 순수 함수로 단독 테스트의 SSOT 역할을 한다.

    Args:
        inventory_rows: ``get_all_material_stock`` 형태의 행 목록
            (``material_code`` / ``material_name`` / ``current_stock`` /
            ``min_stock_threshold``).
        default_threshold: 자재별 임계값이 0 이하일 때 적용할 전역 기본 임계값.
    """
    fallback = max(0.0, _coerce_float(default_threshold))
    alerts: List[MaterialAlert] = []
    for row in inventory_rows or []:
        code = str(row.get("material_code") or "")
        if not code:
            continue
        threshold = _coerce_float(row.get("min_stock_threshold"))
        if threshold <= 0:
            threshold = fallback  # 미설정 → 전역 기본 임계값 적용
        if threshold <= 0:
            continue
        current = _coerce_float(row.get("current_stock"))
        if current > threshold:
            continue  # OK — 충분
        shortfall = max(0.0, round(threshold - current, 6))
        level = LEVEL_OUT if current <= 0 else LEVEL_LOW
        name = str(row.get("material_name") or "")
        alerts.append(
            MaterialAlert(code, name, current, threshold, shortfall, level)
        )

    alerts.sort(key=lambda alert: alert.shortfall, reverse=True)
    return alerts


__all__ = [
    "LEVEL_OUT",
    "LEVEL_LOW",
    "MaterialAlert",
    "evaluate_inventory_alerts",
]
