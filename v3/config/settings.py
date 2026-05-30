"""
배합 프로그램 설정 파일

모든 설정값들을 여기서 관리합니다.
"""

import logging
import os
import sys

_logger = logging.getLogger(__name__)


# 기본 경로 설정
if getattr(sys, 'frozen', False):
    # 실행 파일로 만들어졌을 때 (PyInstaller)
    BASE_PATH = os.path.dirname(sys.executable)
else:
    # 파이썬 스크립트로 실행할 때 (개발 환경)
    BASE_PATH = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

APP_NAME = "MixingProgram"


def _resolve_user_data_dir():
    """
    사용자 데이터 디렉토리를 결정합니다.
    여러 후보 경로를 순서대로 시도합니다.
    """
    candidates = []
    env_override = os.environ.get("MIXING_APP_DATA_DIR")
    if env_override:
        candidates.append(env_override)
    if os.name == "nt":
        local_appdata = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
        if local_appdata:
            candidates.append(os.path.join(local_appdata, APP_NAME))
    home_dir = os.path.expanduser("~")
    if home_dir:
        candidates.append(os.path.join(home_dir, f".{APP_NAME.lower()}"))
    candidates.append(os.path.join(BASE_PATH, "data"))
    for path in candidates:
        try:
            os.makedirs(path, exist_ok=True)
            return path
        except OSError as e:
            _logger.warning(f"데이터 디렉토리 생성 실패 ({path}): {e}")
            continue
    return BASE_PATH


USER_DATA_DIR = _resolve_user_data_dir()
USER_CONFIG_DIR = os.path.join(USER_DATA_DIR, "config")
USER_LOG_DIR = os.path.join(USER_DATA_DIR, "logs")
USER_OUTPUT_DIR = os.path.join(USER_DATA_DIR, "output")
os.makedirs(USER_CONFIG_DIR, exist_ok=True)
os.makedirs(USER_LOG_DIR, exist_ok=True)


# 리소스 경로
RESOURCES_FOLDER = os.path.join(BASE_PATH, "resources")

# 파일 경로
RECORD_FILE = os.path.join(RESOURCES_FOLDER, "배합기록.xlsx")
LOT_FILE = os.path.join(RESOURCES_FOLDER, "OUT.xlsx")

# DB 경로 (사용자 데이터 디렉토리 하위)
LEGACY_DB_PATH = os.path.join(BASE_PATH, "resources", "mixing_records.db")
DB_FILE = os.path.join(USER_DATA_DIR, "mixing_records.db")


# 엑셀 셀 매핑 정보
CELL_MAPPING = {
    'date': 'A3',
    'scale': 'A4',
    'worker': 'C3',
    'work_time': 'E3',
    'product_lot': 'A6',
    'total_amount': 'B6',
    'data_start_row': 6,
    'material_name_col': 'C',
    'material_lot_col': 'D',
    'ratio_col': 'E',
    'theory_amount_col': 'F',
    'actual_amount_col': 'G'
}


# 설정 관리자에서 값을 가져오는 함수들
def get_default_scale():
    from config.config_manager import config
    return config.default_scale


def get_tolerance():
    from config.config_manager import config
    return config.tolerance


def get_cell_mapping():
    from config.config_manager import config
    return config.get("excel.cell_mapping", CELL_MAPPING)


# 하위 호환성을 위한 상수들 (deprecation 예정)
DEFAULT_SCALE = 'M-65'
TOLERANCE = 0.05  # 허용 오차 범위

# 필요한 디렉토리가 없으면 생성
os.makedirs(RESOURCES_FOLDER, exist_ok=True)
os.makedirs(USER_OUTPUT_DIR, exist_ok=True)


# --- Robust path resolution for non-ASCII filenames ---
def _first_existing(paths, create_dir=False):
    for p in paths:
        if os.path.exists(p):
            return p
    if create_dir and paths:
        os.makedirs(paths[0], exist_ok=True)
        return paths[0]
    return paths[0] if paths else None


# Prefer the canonical Korean-named folder if present; otherwise use ASCII 'output'
_output_candidates = [
    os.path.join(USER_DATA_DIR, "실적서"),
    os.path.join(USER_DATA_DIR, "output"),
    os.path.join(BASE_PATH, "실적서"),  # legacy fallback
    os.path.join(BASE_PATH, "output"),
]
OUTPUT_FOLDER = _first_existing(_output_candidates, create_dir=True)
# MIXING_LOG_DIR 환경변수로 로그 경로를 오버라이드 가능(테스트 격리용).
# 미설정 시 프로덕션 기본 경로(USER_LOG_DIR) 사용.
LOG_FOLDER = os.environ.get("MIXING_LOG_DIR", USER_LOG_DIR)

# Resolve known Excel resource files even if the file names vary
_recipe_candidates = [
    os.path.join(RESOURCES_FOLDER, "레시피.xlsx"),
]
RECIPE_FILE = _first_existing(_recipe_candidates)
if not os.path.exists(RECIPE_FILE or "") and os.path.isdir(RESOURCES_FOLDER):
    # Fallback: scan for a likely recipe file
    for name in os.listdir(RESOURCES_FOLDER):
        lower = name.lower()
        if lower.endswith(".xlsx") and ("recipe" in lower or "레시" in lower):
            RECIPE_FILE = os.path.join(RESOURCES_FOLDER, name)
            break

_template_candidates = [
    os.path.join(RESOURCES_FOLDER, "원료배합일지_DHR.xlsx"),
]
TEMPLATE_FILE = _first_existing(_template_candidates)
if not os.path.exists(TEMPLATE_FILE or "") and os.path.isdir(RESOURCES_FOLDER):
    # Fallback: pick any *DHR.xlsx template
    for name in os.listdir(RESOURCES_FOLDER):
        lower = name.lower()
        if lower.endswith(".xlsx") and ("dhr" in lower):
            TEMPLATE_FILE = os.path.join(RESOURCES_FOLDER, name)
            break
