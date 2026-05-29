"""models.lot_utils 순수 함수 단위 테스트 (PDCA 코드 검토 #4)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from models.lot_utils import max_lot_sequence, next_lot


class TestLotUtils(unittest.TestCase):
    def test_empty_returns_zero_and_first(self):
        self.assertEqual(max_lot_sequence([], "RX250529"), 0)
        self.assertEqual(next_lot("RX250529", []), "RX25052901")

    def test_finds_max_sequence(self):
        lots = ["RX25052901", "RX25052903", "RX25052902"]
        self.assertEqual(max_lot_sequence(lots, "RX250529"), 3)
        self.assertEqual(next_lot("RX250529", lots), "RX25052904")

    def test_ignores_other_base_and_malformed(self):
        lots = ["RX25052901", "AB25052905", "RX250529XX", None, "RX250529"]
        # AB...는 다른 base, XX/빈문자/접두만 있는 값은 무시
        self.assertEqual(max_lot_sequence(lots, "RX250529"), 1)
        self.assertEqual(next_lot("RX250529", lots), "RX25052902")

    def test_zero_padding_above_nine(self):
        lots = ["RX25052909"]
        self.assertEqual(next_lot("RX250529", lots), "RX25052910")


if __name__ == "__main__":
    unittest.main()
