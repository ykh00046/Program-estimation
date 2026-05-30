"""DHR 패널 입력 검증 순수 함수 (PDCA #19 Part B).

Qt/DB 비의존. 모든 함수는 ``(ok, message)`` 또는 ``(ok, message, focus_field)``
튜플을 반환하여, 뷰가 메시지 표시·포커스 이동만 담당하도록 분리한다.
"""
from typing import Tuple


def validate_manual_input(product_name: str, amount: float,
                          material_row_count: int) -> Tuple[bool, str, str]:
    """수기 입력 검증.

    Returns:
        (ok, message, focus_field). focus_field는 실패 시 포커스 이동 대상 키
        ("product_name" / "amount" / "") — 메시지 역매핑 없이 뷰가 직접 매핑한다.
        자재 누락 분기는 현행도 포커스 이동이 없으므로 "".
    """
    if not product_name.strip():
        return False, "제품명을 입력하세요.", "product_name"
    if amount <= 0:
        return False, "배합량을 입력하세요.", "amount"
    if material_row_count == 0:
        return False, "자재를 최소 1개 이상 입력하세요.", ""
    return True, "", ""


def validate_bulk_product(product_name: str) -> Tuple[bool, str]:
    """일괄 생성 — 제품명 검증 (엔트리 파싱 '이전'에 호출)."""
    if not product_name.strip():
        return False, "제품명을 입력하세요."
    return True, ""


def validate_bulk_entries(entry_count: int) -> Tuple[bool, str]:
    """일괄 생성 — 엔트리 개수 검증 (엔트리 파싱 '이후'에 호출)."""
    if entry_count == 0:
        return False, "생성할 데이터가 없습니다."
    return True, ""


def validate_recipe_input(recipe_name: str) -> Tuple[bool, str]:
    """레시피 저장 — 레시피명 검증."""
    if not recipe_name.strip():
        return False, "레시피명을 입력하세요."
    return True, ""
