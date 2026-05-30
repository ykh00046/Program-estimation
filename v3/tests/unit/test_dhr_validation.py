"""ui.panels.dhr_validation 순수 함수 단위 테스트 (PDCA #19 Part B). Qt 비의존."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from ui.panels.dhr_validation import (
    validate_manual_input,
    validate_bulk_product,
    validate_bulk_entries,
    validate_recipe_input,
)


class TestManualValidation(unittest.TestCase):
    def test_empty_product(self):
        ok, msg, focus = validate_manual_input("  ", 100.0, 1)
        self.assertFalse(ok)
        self.assertIn("제품명", msg)
        self.assertEqual(focus, "product_name")

    def test_zero_amount(self):
        ok, msg, focus = validate_manual_input("RX", 0, 1)
        self.assertFalse(ok)
        self.assertIn("배합량", msg)
        self.assertEqual(focus, "amount")

    def test_no_material(self):
        ok, msg, focus = validate_manual_input("RX", 100.0, 0)
        self.assertFalse(ok)
        self.assertIn("자재", msg)
        self.assertEqual(focus, "")  # 현행도 포커스 이동 없음

    def test_ok(self):
        self.assertEqual(validate_manual_input("RX", 100.0, 2), (True, "", ""))


class TestBulkValidation(unittest.TestCase):
    def test_product_empty(self):
        ok, msg = validate_bulk_product("")
        self.assertFalse(ok)
        self.assertIn("제품명", msg)

    def test_product_ok(self):
        self.assertEqual(validate_bulk_product("RX"), (True, ""))

    def test_entries_zero(self):
        ok, msg = validate_bulk_entries(0)
        self.assertFalse(ok)
        self.assertIn("생성할 데이터", msg)

    def test_entries_ok(self):
        self.assertEqual(validate_bulk_entries(3), (True, ""))


class TestRecipeValidation(unittest.TestCase):
    def test_empty(self):
        ok, msg = validate_recipe_input("   ")
        self.assertFalse(ok)
        self.assertIn("레시피명", msg)

    def test_ok(self):
        self.assertEqual(validate_recipe_input("연질A"), (True, ""))


if __name__ == "__main__":
    unittest.main()
