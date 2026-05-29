"""ui.builders 단위 테스트 (PDCA #19 Part A3).

register_sidebar_interfaces / setup_statusbar 전체는 FluentWindow 인프라와
다수 패널에 의존하므로 시각 스모크(통합)에서 커버한다. 여기서는 순수 빌더인
build_mixing_page가 refs를 올바로 반환하는지 단위 검증한다.
"""
import importlib
import os
import sys
import types
import unittest


def _ensure_ui_test_dependencies() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    missing = []
    for module_name in ("PySide6", "qfluentwidgets"):
        try:
            importlib.import_module(module_name)
        except ModuleNotFoundError:
            missing.append(module_name)
    if missing:
        raise unittest.SkipTest(
            f"UI builder tests require optional GUI dependencies: {', '.join(missing)}"
        )


_ensure_ui_test_dependencies()

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))
sys.path.insert(0, project_root)

from PySide6.QtWidgets import QApplication, QWidget

from ui.builders import build_mixing_page, MixingPageRefs

app = QApplication.instance() or QApplication(sys.argv)


class TestBuildMixingPage(unittest.TestCase):
    def _make_window(self):
        """build_mixing_page가 읽는 최소 속성만 갖춘 stub window."""
        saved = {"called": False}
        win = types.SimpleNamespace(
            recipe_panel=QWidget(),
            work_info_panel=QWidget(),
            material_panel=QWidget(),
            _save_record=lambda: saved.__setitem__("called", True),
        )
        return win, saved

    def test_returns_page_and_refs(self):
        win, _ = self._make_window()
        page, refs = build_mixing_page(win)
        self.assertEqual(page.objectName(), "MixingPage")
        self.assertIsInstance(refs, MixingPageRefs)
        self.assertIsNotNone(refs.save_btn)
        self.assertIsNotNone(refs.status_bar)

    def test_save_button_disabled_initially(self):
        win, _ = self._make_window()
        _, refs = build_mixing_page(win)
        self.assertFalse(refs.save_btn.isEnabled())

    def test_save_button_wired_to_window_save(self):
        win, saved = self._make_window()
        _, refs = build_mixing_page(win)
        refs.save_btn.setEnabled(True)  # 초기 비활성이므로 클릭 발화 위해 활성화
        refs.save_btn.click()
        self.assertTrue(saved["called"])


if __name__ == "__main__":
    unittest.main()
