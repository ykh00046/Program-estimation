"""LOT 번호 시퀀스 파싱 공통 유틸 (PDCA 코드 검토 #4 DRY).

`{base}{seq:02d}` 형태의 제품 LOT에서 다음 시퀀스를 계산하는 순수 함수.
MixingDatabaseManager / DhrDatabaseManager / DataManager가 공유한다.
"""
from typing import Iterable, Optional


def max_lot_sequence(lots: Iterable[Optional[str]], base_lot: str) -> int:
    """base_lot 접두를 가진 LOT들에서 가장 큰 시퀀스 번호를 반환한다 (없으면 0)."""
    max_seq = 0
    for lot in lots:
        if not lot or not lot.startswith(base_lot):
            continue
        try:
            seq = int(lot[len(base_lot):])
        except (ValueError, IndexError):
            continue
        if seq > max_seq:
            max_seq = seq
    return max_seq


def next_lot(base_lot: str, lots: Iterable[Optional[str]]) -> str:
    """base_lot에 대해 다음 시퀀스를 2자리(zero-padded)로 붙인 LOT을 반환한다."""
    return f"{base_lot}{max_lot_sequence(lots, base_lot) + 1:02d}"
