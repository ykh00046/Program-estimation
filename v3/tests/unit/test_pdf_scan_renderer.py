"""PdfScanRenderer 단독 단위 테스트 (PDCA #22).

win32com(실제 Excel) 없이 검증 가능한 부분만: excel 파일 부재 early-return,
스캔 효과 크기 보존, 임시파일 정리.
"""
import importlib
import os
import sys
import tempfile
import unittest


def _ensure_dependencies() -> None:
    missing = []
    for name in ("win32com", "fitz", "PIL", "numpy"):
        try:
            importlib.import_module(name)
        except ModuleNotFoundError:
            missing.append(name)
    if missing:
        raise unittest.SkipTest(f"PdfScanRenderer tests require: {', '.join(missing)}")


_ensure_dependencies()

current_dir = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(current_dir))
sys.path.insert(0, PROJECT_ROOT)

from PIL import Image

from models.pdf_scan_renderer import PdfScanRenderer


class TestPdfScanRenderer(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.pdf_folder = os.path.join(self._tmp.name, "pdf")
        self.excel_folder = os.path.join(self._tmp.name, "excel")
        for d in (self.pdf_folder, self.excel_folder):
            os.makedirs(d, exist_ok=True)
        self.renderer = PdfScanRenderer(self.pdf_folder, self.excel_folder)

    def tearDown(self):
        self._tmp.cleanup()

    def test_export_to_pdf_returns_none_when_excel_missing(self):
        # win32com 경로를 타지 않고 early-return(파일 부재) 검증
        self.assertIsNone(self.renderer.export_to_pdf(None, {}))
        self.assertIsNone(self.renderer.export_to_pdf("/no/such/file.xlsx", {}))

    def test_apply_scan_effects_preserves_size(self):
        img = Image.new("RGB", (40, 30), (200, 200, 200))
        out = self.renderer._apply_scan_effects(img, {})
        self.assertEqual(out.size, (40, 30))

    def test_cleanup_removes_existing_and_ignores_missing(self):
        existing = os.path.join(self._tmp.name, "temp_a.pdf")
        with open(existing, "w", encoding="utf-8") as f:
            f.write("x")
        missing = os.path.join(self._tmp.name, "temp_b.pdf")
        self.renderer._cleanup([existing, missing, None])  # 예외 없이 처리
        self.assertFalse(os.path.exists(existing))


if __name__ == "__main__":
    unittest.main()
