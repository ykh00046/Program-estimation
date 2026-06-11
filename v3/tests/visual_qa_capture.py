"""전체 화면 시각 QA 캡처 하네스.

offscreen Qt로 실제 MainWindow를 구동해 사이드바 화면 전부를 PNG로 저장한다.
AI가 이미지를 직접 검토하는 시각 QA의 입력을 만든다.

실행:  cd v3 && ..\\.venv\\Scripts\\python.exe tests\\visual_qa_capture.py
출력:  v3/qa_screens/NN_<objectName>.png

읽기 전용 운용 — 화면 전환과 grab만 수행하고 저장/삭제 등 버튼은 클릭하지 않는다.
(MainWindow 초기화 자체의 부수효과는 정상 실행과 동일.)
"""
import os
import sys

# offscreen 플랫폼은 FluentWindow 풀 구성에서 access violation(#30 교훈 계열) —
# 실제 플랫폼으로 구동하되 창을 화면 밖 좌표로 옮겨 시각적 방해를 없앤다.

V3_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if V3_ROOT not in sys.path:
    sys.path.insert(0, V3_ROOT)
os.chdir(V3_ROOT)

import faulthandler  # noqa: E402
faulthandler.enable()

from PySide6.QtGui import QFont  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402
from qfluentwidgets import Theme, setFontFamilies, setTheme, setThemeColor  # noqa: E402


def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    # main.py(MixingApp.__init__)와 동일한 전역 초기화 재현
    app.setApplicationName("배합 프로그램")
    setTheme(Theme.DARK)
    setThemeColor("#03DAC6")
    app.setFont(QFont("Segoe UI", 10))
    setFontFamilies(["Pretendard", "Segoe UI", "Noto Sans KR"])
    out_dir = os.path.join(V3_ROOT, "qa_screens")
    os.makedirs(out_dir, exist_ok=True)

    # 작업자 선택 모달(시작 시 exec) 우회.
    # ⚠ unittest.mock.patch.object는 QWidget 클래스에 MagicMock을 심어
    # Qt 메타오브젝트를 깨뜨림(첫 signal connect에서 access violation) —
    # 일반 함수 할당으로 대체한다.
    from ui.panels.work_info_panel import WorkInfoPanel
    _orig = WorkInfoPanel.request_worker_input
    WorkInfoPanel.request_worker_input = lambda self, initial=False: "QA작업자"
    try:
        from ui.main_window import MainWindow
        window = MainWindow()
    finally:
        WorkInfoPanel.request_worker_input = _orig

    window.resize(1600, 1000)  # 실사용(FHD 모니터) 근사 — 작은 창 시나리오는 별도 점검
    window.move(-2600, -2600)  # 화면 밖 — grab()은 위젯 렌더 기반이라 캡처엔 무관
    window.show()
    app.processEvents()

    stack = window.stackedWidget
    saved = []
    for i in range(stack.count()):
        widget = stack.widget(i)
        name = widget.objectName() or f"page{i}"
        try:
            window.switchTo(widget)
        except Exception:
            stack.setCurrentWidget(widget)
        # 페이지 전환 팝업 애니메이션(~250ms)이 끝나기 전에 grab하면
        # 위젯이 아래로 밀린 중간 프레임이 찍힌다(하단 잘림처럼 보임) — 대기 필수
        from PySide6.QtTest import QTest
        QTest.qWait(400)
        path = os.path.join(out_dir, f"{i:02d}_{name}.png")
        if window.grab().save(path):
            saved.append(path)
            print(f"saved: {path}")
        else:
            print(f"FAILED to save: {path}")

    print(f"done: {len(saved)}/{stack.count()} pages captured")
    return 0 if saved else 1


if __name__ == "__main__":
    sys.exit(main())
