"""FunctionWorker / start_worker 단위 테스트 (PDCA #33).

run()은 동기 직접 호출로 검증(스레드 미사용 — 타이밍 플레이크 방지),
start_worker는 실제 스레드 + wait + processEvents로 검증한다.
"""
import importlib
import os
import sys
import unittest
from unittest.mock import MagicMock, patch


def _ensure_ui_test_dependencies() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    try:
        importlib.import_module("PySide6")
    except ModuleNotFoundError:
        raise unittest.SkipTest("requires GUI deps: PySide6")


_ensure_ui_test_dependencies()

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from PySide6.QtWidgets import QApplication, QPushButton, QWidget

from ui.workers import FunctionWorker, start_worker, wait_for_workers

app = QApplication.instance() or QApplication(sys.argv)


class TestFunctionWorkerRun(unittest.TestCase):
    """run() 동기 직접 호출 — 시그널 방출 계약 검증."""

    def _make(self, fn, **kw):
        results, failures = [], []
        worker = FunctionWorker(fn, **kw)
        worker.result_ready.connect(results.append)
        worker.failed.connect(failures.append)
        return worker, results, failures

    def test_success_emits_result_ready_only(self):
        worker, results, failures = self._make(lambda a, b: a + b, args=(1, 2))
        worker.run()
        self.assertEqual(results, [3])
        self.assertEqual(failures, [])

    def test_kwargs_are_passed(self):
        worker, results, _ = self._make(
            lambda x=0, y=0: x * y, kwargs={"x": 3, "y": 4})
        worker.run()
        self.assertEqual(results, [12])

    def test_exception_emits_failed_only(self):
        def boom():
            raise ValueError("boom")
        worker, results, failures = self._make(boom)
        worker.run()
        self.assertEqual(results, [])
        self.assertEqual(failures, ["boom"])

    def test_use_com_initializes_and_uninitializes(self):
        fake_com = MagicMock()
        with patch.dict(sys.modules, {"pythoncom": fake_com}):
            worker, results, _ = self._make(lambda: "ok", use_com=True)
            worker.run()
        fake_com.CoInitialize.assert_called_once()
        fake_com.CoUninitialize.assert_called_once()
        self.assertEqual(results, ["ok"])

    def test_use_com_uninitializes_even_on_failure(self):
        fake_com = MagicMock()

        def boom():
            raise RuntimeError("com boom")
        with patch.dict(sys.modules, {"pythoncom": fake_com}):
            worker, _, failures = self._make(boom, use_com=True)
            worker.run()
        fake_com.CoUninitialize.assert_called_once()
        self.assertEqual(failures, ["com boom"])

    def test_no_com_when_use_com_false(self):
        fake_com = MagicMock()
        with patch.dict(sys.modules, {"pythoncom": fake_com}):
            worker, _, _ = self._make(lambda: None)
            worker.run()
        fake_com.CoInitialize.assert_not_called()


class TestStartWorker(unittest.TestCase):
    """start_worker 배선 검증 — FunctionWorker.start를 동기 실행으로 패치.

    headless 테스트에서 실제 QThread 기동은 크래시/타이밍 플레이크 위험이
    있으므로(설계 §4), run() + _on_finished()를 호출 스레드에서 그대로 실행해
    busy 가드/owner 추적/결과 전달 배선만 결정적으로 검증한다.
    """

    def setUp(self):
        def _sync_start(worker):
            worker.run()
            worker._on_finished()
        self._patcher = patch.object(FunctionWorker, "start", _sync_start)
        self._patcher.start()

    def tearDown(self):
        self._patcher.stop()

    def test_busy_widgets_disabled_during_run_and_restored(self):
        owner = QWidget()
        btn = QPushButton(owner)
        enabled_during_run, results = [], []

        def job():
            enabled_during_run.append(btn.isEnabled())
            return 42

        start_worker(
            owner, job,
            on_result=results.append,
            on_failed=lambda msg: self.fail(f"unexpected failure: {msg}"),
            busy_widgets=(btn,),
        )
        self.assertEqual(enabled_during_run, [False])
        self.assertEqual(results, [42])
        self.assertTrue(btn.isEnabled())
        self.assertEqual(owner._active_workers, set())

    def test_failure_restores_widgets_and_reports(self):
        owner = QWidget()
        btn = QPushButton(owner)
        failures = []

        def boom():
            raise ValueError("worker boom")

        start_worker(
            owner, boom,
            on_result=lambda r: self.fail("unexpected success"),
            on_failed=failures.append,
            busy_widgets=(btn,),
        )
        self.assertEqual(failures, ["worker boom"])
        self.assertTrue(btn.isEnabled())
        self.assertEqual(owner._active_workers, set())

    def test_wait_for_workers_after_completion_is_noop(self):
        owner = QWidget()
        results = []
        start_worker(
            owner, lambda: "done",
            on_result=results.append,
            on_failed=lambda msg: self.fail(msg),
        )
        wait_for_workers(owner, timeout_ms=1000)  # 이미 완료 — 즉시 반환
        self.assertEqual(results, ["done"])

    def test_wait_for_workers_no_workers_is_noop(self):
        owner = QWidget()
        wait_for_workers(owner)  # _active_workers 미존재 — 예외 없어야 함


if __name__ == "__main__":
    unittest.main()
