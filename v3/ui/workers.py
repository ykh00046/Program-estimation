"""범용 백그라운드 워커 인프라 (PDCA #33).

무거운 작업(네트워크 백업, Excel COM PDF 변환)을 UI 스레드 밖에서 실행한다.

규약:
- 워커 함수(fn)는 QWidget을 절대 만지지 않는다.
  위젯 읽기는 워커 시작 전에, 위젯 갱신은 시그널 슬롯에서만 수행한다.
- on_result/on_failed 슬롯은 QObject(위젯)의 바운드 메서드여야 한다 —
  PySide6는 QObject 수신자가 있어야 GUI 스레드로 queued 실행을 보장한다.
  (클로저/일반 함수를 연결하면 워커 스레드에서 직접 실행되므로 UI 갱신 금지)
- models 계층은 Qt 비의존을 유지한다 — 워커 생성/시그널 연결은 ui 계층 전용.
- COM(win32com) 사용 작업은 use_com=True로 스레드별 초기화를 보장한다.
"""
from typing import Any, Callable, Dict, Optional, Sequence, Tuple

from PySide6.QtCore import QThread, Signal

from utils.logger import logger


class FunctionWorker(QThread):
    """임의 함수를 백그라운드 스레드에서 실행하는 범용 워커.

    시그널명은 QThread 내장 ``finished``와 충돌하지 않도록
    ``result_ready``/``failed``를 사용한다.

    busy 위젯 복원/owner 정리는 워커 자신의 바운드 메서드(``_on_finished``)로
    수행한다 — QThread 객체는 생성(GUI) 스레드 소속이므로 ``finished`` 시그널이
    워커 스레드에서 방출되어도 슬롯은 GUI 스레드에서 queued 실행된다.
    """

    result_ready = Signal(object)
    failed = Signal(str)

    def __init__(self, fn: Callable, args: Tuple = (),
                 kwargs: Optional[Dict] = None,
                 use_com: bool = False,
                 busy_widgets: Sequence = (),
                 owner=None, parent=None) -> None:
        super().__init__(parent)
        self._fn = fn
        self._args = args
        self._kwargs = kwargs or {}
        self._use_com = use_com
        self._busy_widgets = tuple(busy_widgets)
        self._owner = owner
        self.finished.connect(self._on_finished)

    def run(self) -> None:
        com_initialized = False
        try:
            if self._use_com:
                import pythoncom
                pythoncom.CoInitialize()
                com_initialized = True
            result = self._fn(*self._args, **self._kwargs)
        except Exception as e:  # noqa: BLE001 — 워커 경계: 모든 예외를 failed 시그널로 변환
            logger.error(f"백그라운드 작업 실패: {e}", exc_info=True)
            self.failed.emit(str(e))
        else:
            self.result_ready.emit(result)
        finally:
            if com_initialized:
                import pythoncom
                pythoncom.CoUninitialize()

    def _on_finished(self) -> None:
        """busy 위젯 복원 + owner 추적 해제 (GUI 스레드에서 실행됨)."""
        for widget in self._busy_widgets:
            widget.setEnabled(True)
        if self._owner is not None:
            getattr(self._owner, "_active_workers", set()).discard(self)
        self.deleteLater()


def start_worker(owner, fn: Callable, *, args: Tuple = (),
                 kwargs: Optional[Dict] = None,
                 on_result: Callable[[Any], None],
                 on_failed: Callable[[str], None],
                 use_com: bool = False,
                 busy_widgets: Sequence = ()) -> FunctionWorker:
    """워커를 시작하고 owner에 참조를 보관한다.

    - busy_widgets: 실행 중 setEnabled(False) → 종료 시 복원 (중복 실행 가드)
    - owner._active_workers 에 참조 보관 (조기 GC 방지, wait_for_workers 대상)
    - on_result/on_failed 는 QObject 바운드 메서드 권장 (모듈 docstring 참조)
    """
    for widget in busy_widgets:
        widget.setEnabled(False)

    worker = FunctionWorker(fn, args=args, kwargs=kwargs, use_com=use_com,
                            busy_widgets=busy_widgets, owner=owner, parent=owner)
    if not hasattr(owner, "_active_workers"):
        owner._active_workers = set()
    owner._active_workers.add(worker)

    worker.result_ready.connect(on_result)
    worker.failed.connect(on_failed)
    worker.start()
    return worker


def wait_for_workers(owner, timeout_ms: int = 3000) -> None:
    """owner의 활성 워커가 끝날 때까지 대기한다 (창 닫기/앱 종료 시 호출)."""
    for worker in list(getattr(owner, "_active_workers", ())):
        if worker.isRunning():
            worker.wait(timeout_ms)
