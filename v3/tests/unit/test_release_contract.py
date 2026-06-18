"""
Release contract regression tests.

APP_NAME / RELEASE_VERSION / ZIP_PATTERN / MIN_EXE_SIZE_MB 등 배포 계약
상수가 의도치 않게 변경되면 이 테스트들이 즉시 감지한다.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

V3_ROOT = Path(__file__).resolve().parents[2]
if str(V3_ROOT) not in sys.path:
    sys.path.insert(0, str(V3_ROOT))

import check_release_artifacts as checker


class TestReleaseContract(unittest.TestCase):
    def test_app_name_is_dhr_generator(self):
        self.assertEqual(checker.APP_NAME, "DHR_Generator")

    def test_release_version_semver(self):
        self.assertRegex(checker.RELEASE_VERSION, r"^v\d+\.\d+\.\d+$")

    def test_zip_pattern_matches_canonical_name(self):
        name = f"{checker.APP_NAME}_{checker.RELEASE_VERSION}_20260415.zip"
        self.assertIsNotNone(checker.ZIP_PATTERN.match(name))

    def test_zip_pattern_rejects_other_versions(self):
        name = "DHR_Generator_v2.9.9_20260415.zip"
        self.assertIsNone(checker.ZIP_PATTERN.match(name))

    def test_required_package_items_include_exe_and_resources(self):
        items = checker.REQUIRED_PACKAGE_ITEMS
        self.assertIn("DHR_Generator.exe", items)
        self.assertIn("resources/", items)
        self.assertIn("DEPLOY_GUIDE.md", items)

    def test_min_exe_size_reasonable(self):
        self.assertGreaterEqual(checker.MIN_EXE_SIZE_MB, 5)
        self.assertLessEqual(checker.MIN_EXE_SIZE_MB, 200)

    def test_build_invokes_pyinstaller_via_sys_executable(self):
        """빌드는 build.py를 실행한 인터프리터의 PyInstaller만 사용해야 한다.

        bare "pyinstaller"는 PATH 1순위의 무관한 venv로 빌드되어 qfluentwidgets 등
        미설치 모듈이 번들에서 누락된다 (2026-06-11 ModuleNotFoundError 사고 회귀 가드).
        """
        source = (V3_ROOT / "build.py").read_text(encoding="utf-8")
        self.assertIn('sys.executable, "-m", "PyInstaller"', source)
        self.assertNotRegex(source, r'\[\s*\n?\s*"pyinstaller"')


if __name__ == "__main__":
    unittest.main()
