import functools
from typing import Any, Callable

try:
    from PySide6.QtWidgets import QMessageBox  # type: ignore
except ImportError:  # pragma: no cover - optional GUI dependency
    QMessageBox = None

from .logger import logger

_DEFAULT_TEXT_COLOR = "#F5F7FA"


class MixingProgramError(Exception):
    pass


class RecipeNotFoundError(MixingProgramError):
    pass


class InvalidMixingRatioError(MixingProgramError):
    pass


class FileOperationError(MixingProgramError):
    pass


class DatabaseError(MixingProgramError):
    pass


def handle_exceptions(
    show_user_message: bool = True,
    user_message: str = "작업 중 오류가 발생했습니다.",
    reraise: bool = False,
    default_return: Any = None,
):
    """Decorator for consistent exception handling in UI/service code."""

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                context = {
                    "function": func.__name__,
                    "args": str(args)[:200],
                    "kwargs": str(kwargs)[:200],
                }
                logger.log_error_with_context(e, context)

                if show_user_message:
                    show_error_message(user_message, str(e))

                if reraise:
                    raise
                return default_return

        return wrapper

    return decorator


def safe_execute(
    func: Callable,
    args: tuple = (),
    kwargs: dict = None,
    error_message: str = "작업 실행 중 오류가 발생했습니다.",
    default_return: Any = None,
) -> Any:
    if kwargs is None:
        kwargs = {}

    try:
        return func(*args, **kwargs)
    except Exception as e:
        logger.log_error_with_context(
            e,
            {
                "function": func.__name__,
                "args": str(args)[:200],
                "kwargs": str(kwargs)[:200],
            },
        )
        show_error_message(error_message, str(e))
        return default_return


def _is_headless() -> bool:
    """GUI 이벤트 루프가 없는 환경(offscreen/테스트/CI)인지 판별.

    이 경우 모달 `exec()`는 무한 블록되므로 로그 폴백으로 전환한다.
    프로덕션은 실제 플랫폼으로 구동되어 영향이 없다.
    """
    try:
        from PySide6.QtGui import QGuiApplication  # type: ignore
    except ImportError:
        return True
    app = QGuiApplication.instance()
    if app is None:
        return True
    return app.platformName() == "offscreen"


def _show_message(icon_name: str, title_text: str, title: str, detail: str = "", parent=None):
    if QMessageBox is None or _is_headless():
        if icon_name == "error":
            logger.error(f"{title} | {detail}")
        elif icon_name == "warning":
            logger.warning(f"{title} | {detail}")
        else:
            logger.info(f"{title} | {detail}")
        return

    msg_box = QMessageBox(parent)
    if icon_name == "error":
        msg_box.setIcon(QMessageBox.Critical)
    elif icon_name == "warning":
        msg_box.setIcon(QMessageBox.Warning)
    else:
        msg_box.setIcon(QMessageBox.Information)

    msg_box.setWindowTitle(title_text)
    msg_box.setText(title)
    msg_box.setStyleSheet(
        f"QLabel {{ color: {_DEFAULT_TEXT_COLOR}; }} QAbstractButton {{ color: {_DEFAULT_TEXT_COLOR}; }}"
    )
    if detail:
        msg_box.setDetailedText(detail)
    msg_box.exec()


def show_error_message(title: str, detail: str = "", parent=None):
    _show_message("error", "오류", title, detail, parent)


def show_warning_message(title: str, detail: str = "", parent=None):
    _show_message("warning", "경고", title, detail, parent)


def show_info_message(title: str, detail: str = "", parent=None):
    _show_message("info", "정보", title, detail, parent)


def validate_mixing_ratio(actual: float, theory: float, tolerance: float) -> bool:
    if abs(actual - theory) > tolerance:
        raise InvalidMixingRatioError(
            f"배합량이 허용 오차를 벗어났습니다. 이론값 {theory}, 실제값 {actual}, 허용오차: ±{tolerance}"
        )
    return True


def validate_file_exists(file_path: str, file_description: str = "파일"):
    import os

    if not os.path.exists(file_path):
        raise FileOperationError(f"{file_description}을(를) 찾을 수 없습니다: {file_path}")


def validate_recipe_data(recipe_data: dict):
    required_fields = ["항목코드", "항목명", "배합비율"]

    for field in required_fields:
        if field not in recipe_data:
            raise RecipeNotFoundError(f"레시피 데이터에 필수 필드가 없습니다: {field}")

    ratio = recipe_data.get("배합비율")
    if not isinstance(ratio, (int, float)) or ratio <= 0:
        raise RecipeNotFoundError("배합비율은 0보다 큰 숫자여야 합니다")
