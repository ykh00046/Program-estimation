import os
import sys
import tempfile
import unittest


def _bootstrap_environment() -> str:
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(current_dir)

    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    # 테스트 로그를 임시 경로로 격리(공유 프로덕션 로그 경합 방지). PDCA #21.
    os.environ.setdefault("MIXING_LOG_DIR", tempfile.mkdtemp(prefix="mixing_test_logs_"))
    return current_dir


def run_tests() -> None:
    start_dir = _bootstrap_environment()

    loader = unittest.TestLoader()
    suite = loader.discover(start_dir, pattern="test_*.py")

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    if not result.wasSuccessful():
        sys.exit(1)


if __name__ == "__main__":
    run_tests()
