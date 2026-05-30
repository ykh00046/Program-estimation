"""로그 로테이션 동시성 안정화 테스트 (PDCA #21).

- SafeTimedRotatingFileHandler가 롤오버 rename 실패를 견디는지
- LOG_FOLDER가 MIXING_LOG_DIR 환경변수를 존중하는지
"""
import importlib
import logging
import os
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from utils.logger import SafeTimedRotatingFileHandler


def _raise_oserror(*args, **kwargs):
    raise OSError("simulated file lock (WinError 32)")


class TestSafeTimedRotatingFileHandler(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="logtest_")
        self.path = os.path.join(self.tmp, "app.log")
        self.handler = SafeTimedRotatingFileHandler(
            self.path, when="D", interval=1, backupCount=3, encoding="utf-8"
        )

    def tearDown(self):
        self.handler.close()

    def test_tolerates_rename_failure(self):
        """rename 실패 시 예외 없이 스트림 유지 + rolloverAt advance."""
        self.handler.rotate = _raise_oserror
        self.handler.doRollover()  # 예외가 전파되면 테스트 실패
        self.assertIsNotNone(self.handler.stream)
        self.assertGreater(self.handler.rolloverAt, int(time.time()))

    def test_emit_after_failed_rollover(self):
        """실패한 롤오버 이후에도 로깅이 지속된다."""
        self.handler.rotate = _raise_oserror
        self.handler.doRollover()
        record = logging.LogRecord(
            "t", logging.INFO, __file__, 1, "after-rollover-line", None, None
        )
        self.handler.emit(record)
        self.handler.flush()
        with open(self.path, encoding="utf-8") as f:
            self.assertIn("after-rollover-line", f.read())


class TestLogFolderEnvOverride(unittest.TestCase):
    def test_honors_env_override(self):
        import config.settings as settings

        original = os.environ.get("MIXING_LOG_DIR")
        tmp = tempfile.mkdtemp(prefix="logdir_")
        try:
            os.environ["MIXING_LOG_DIR"] = tmp
            importlib.reload(settings)
            self.assertEqual(settings.LOG_FOLDER, tmp)
        finally:
            if original is None:
                os.environ.pop("MIXING_LOG_DIR", None)
            else:
                os.environ["MIXING_LOG_DIR"] = original
            importlib.reload(settings)


if __name__ == "__main__":
    unittest.main()
