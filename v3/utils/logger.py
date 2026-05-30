import logging
import logging.handlers
import os
import time
from typing import Any

from config.settings import LOG_FOLDER


class SafeTimedRotatingFileHandler(logging.handlers.TimedRotatingFileHandler):
    """롤오버 rename 실패(멀티프로세스 파일 잠금, Windows WinError 32 등)에 견디는 핸들러.

    stdlib는 `rotate()`(os.rename) 실패 시 stream을 닫은 채 예외를 던지고 traceback을
    stderr로 덤프하며, rolloverAt을 갱신하지 못해 매 emit마다 재시도한다.
    본 핸들러는 실패를 삼키고 현재 파일 스트림을 재오픈해 로깅을 지속하며,
    rolloverAt을 다음 주기로 advance해 재시도 스팸을 막는다(다음 주기 자가 재시도).
    """

    def doRollover(self) -> None:
        try:
            super().doRollover()
        except OSError:
            if self.stream is None:
                self.stream = self._open()
            self.rolloverAt = self.computeRollover(int(time.time()))


class Logger:
    """Application logger wrapper with safe file-handler fallback."""

    _instance = None
    _logger = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._setup_logger()
        return cls._instance

    def _setup_logger(self) -> None:
        self._logger = logging.getLogger("MixingProgram")
        self._logger.setLevel(logging.DEBUG)
        self._logger.propagate = False

        if self._logger.handlers:
            return

        formatter = logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(module)s:%(funcName)s:%(lineno)d | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(logging.Formatter("%(levelname)-8s | %(module)s | %(message)s"))
        self._logger.addHandler(console_handler)

        try:
            os.makedirs(LOG_FOLDER, exist_ok=True)
            self._add_file_handlers(LOG_FOLDER, formatter)
        except OSError as e:
            self._logger.warning(f"File logging disabled: {e}")

    def _add_file_handlers(self, log_dir: str, formatter: logging.Formatter) -> None:
        try:
            file_handler = SafeTimedRotatingFileHandler(
                filename=os.path.join(log_dir, "mixing_program.log"),
                when="D",
                interval=1,
                backupCount=30,
                encoding="utf-8",
            )
            file_handler.setLevel(logging.DEBUG)
            file_handler.setFormatter(formatter)
            self._logger.addHandler(file_handler)
        except OSError as e:
            self._logger.warning(f"Main log file handler disabled: {e}")

        try:
            error_handler = logging.FileHandler(
                filename=os.path.join(log_dir, "error.log"),
                encoding="utf-8",
            )
            error_handler.setLevel(logging.ERROR)
            error_handler.setFormatter(formatter)
            self._logger.addHandler(error_handler)
        except OSError as e:
            self._logger.warning(f"Error log file handler disabled: {e}")

    def debug(self, message: Any, **kwargs) -> None:
        self._logger.debug(message, **kwargs)

    def info(self, message: Any, **kwargs) -> None:
        self._logger.info(message, **kwargs)

    def warning(self, message: Any, **kwargs) -> None:
        self._logger.warning(message, **kwargs)

    def error(self, message: Any, **kwargs) -> None:
        self._logger.error(message, **kwargs)

    def critical(self, message: Any, **kwargs) -> None:
        self._logger.critical(message, **kwargs)

    def log_mixing_operation(self, operation, recipe_name, worker, **details):
        log_message = f"[Mixing] {operation} | recipe={recipe_name} | worker={worker}"
        if details:
            detail_str = " | ".join([f"{k}: {v}" for k, v in details.items()])
            log_message += f" | {detail_str}"
        self.info(log_message)

    def log_error_with_context(self, error, context=None):
        import traceback

        error_info = {
            "error_type": type(error).__name__,
            "error_message": str(error),
            "traceback": traceback.format_exc(),
        }
        if context:
            error_info["context"] = context
        self.error(f"Exception occurred: {error_info}")


logger = Logger()
