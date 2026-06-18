"""
배합 프로그램 메인 실행 파일

주요 기능:
- PySide6 애플리케이션 초기화
- 전역 예외 처리
- 메인 윈도우 생성
- 단일 인스턴스 실행 제어
"""
import sys
import traceback

# 단일 인스턴스 실행을 위한 Windows API 임포트
import win32event
import win32api
from winerror import ERROR_ALREADY_EXISTS

from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtGui import QFont
from qfluentwidgets import setTheme, Theme, setThemeColor, setFontFamilies
from ui.main_window import MainWindow
from utils.logger import logger
from utils.error_handler import show_error_message


class MixingApp(QApplication):
    """메인 애플리케이션"""

    def __init__(self, argv):
        super().__init__(argv)
        self.setApplicationName("배합 프로그램")
        setTheme(Theme.DARK)
        setThemeColor("#03DAC6")
        app_font = QFont("Segoe UI", 10)
        self.setFont(app_font)
        setFontFamilies(["Pretendard", "Segoe UI", "Noto Sans KR"])

        # 애플리케이션 시작 로그
        logger.info("배합 프로그램 시작")

        # 예외 처리
        sys.excepthook = self.exception_handler

        try:
            # 메인 윈도우
            self.main_window = MainWindow()
            self.main_window.show()
            logger.info("메인 윈도우 초기화 완료")
        except Exception as e:
            logger.critical(f"메인 윈도우 초기화 실패: {e}")
            show_error_message("프로그램 시작 실패", str(e))
            sys.exit(1)

    def exception_handler(self, exc_type, exc_value, exc_traceback):
        """전역 예외 처리"""
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return

        error_msg = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
        
        # 로그에 기록
        logger.critical(f"처리되지 않은 예외 발생: {exc_type.__name__}: {exc_value}")
        logger.debug(f"전체 트레이스백: {error_msg}")

        # 사용자에게 표시
        show_error_message(
            "예상치 못한 오류가 발생했습니다.",
            f"오류 유형: {exc_type.__name__}\n오류 내용: {exc_value}\n\n자세한 내용은 로그 파일을 확인하세요."
        )


if __name__ == '__main__':
    # 단일 인스턴스 실행 확인
    # Mutex를 생성하여 이미 실행 중인지 확인
    mutex_name = "DHR_배합프로그램_UNIQUE_MUTEX"
    mutex = win32event.CreateMutex(None, False, mutex_name)
    last_error = win32api.GetLastError()
    
    if last_error == ERROR_ALREADY_EXISTS:
        # 이미 프로그램이 실행 중임
        temp_app = QApplication(sys.argv)  # 메시지 박스 표시를 위해 필요
        QMessageBox.warning(
            None,
            "실행 중",
            "배합 프로그램이 이미 실행 중입니다.\n"
            "작업표시줄에서 실행 중인 프로그램을 확인해주세요."
        )
        logger.warning("프로그램 중복 실행 시도 차단됨")
        sys.exit(1)
    
    try:
        # 정상 실행
        app = MixingApp(sys.argv)
        exit_code = app.exec()
        logger.info(f"배합 프로그램 종료 (exit code: {exit_code})")
        sys.exit(exit_code)
    finally:
        # Mutex 해제 (프로그램 종료 시 자동으로 해제되지만 명시적으로 처리)
        if mutex:
            win32api.CloseHandle(mutex)
