"""
Simple configuration manager for loading config/config.json with UTF-8 encoding.

Provides dotted-key access via Config.get("a.b.c", default) and common
properties like default_scale and tolerance. Designed to avoid crashes if the
JSON file is missing or malformed by falling back to safe defaults.
"""
from __future__ import annotations

import base64
import copy
import hashlib
import hmac
import json
import logging
import os
from typing import Any, Dict, Optional, Tuple

from config.settings import BASE_PATH, USER_DATA_DIR

_logger = logging.getLogger(__name__)


class Config:
    def __init__(self) -> None:
        self._base_path = BASE_PATH
        self._user_data_dir = USER_DATA_DIR
        self._config_path = os.path.join(self._user_data_dir, "config", "config.json")
        self._legacy_config_path = os.path.join(self._base_path, "config", "config.json")
        os.makedirs(os.path.dirname(self._config_path), exist_ok=True)
        self._data: Dict[str, Any] = {}
        self._load()

    def _load(self) -> None:
        try:
            target_path = None
            if os.path.exists(self._config_path):
                target_path = self._config_path
            elif os.path.exists(self._legacy_config_path):
                target_path = self._legacy_config_path

            if target_path:
                with open(target_path, "r", encoding="utf-8") as f:
                    self._data = json.load(f)
            else:
                self._data = {}
        except (OSError, json.JSONDecodeError, UnicodeDecodeError) as e:
            _logger.warning(f"설정 파일 로드 실패 (기본값 사용): {e}")
            self._data = {}

    def get(self, dotted_key: str, default: Any = None) -> Any:
        """Get a value by dotted key path, e.g. "excel.cell_mapping"."""
        try:
            node: Any = self._data
            for part in dotted_key.split("."):
                if isinstance(node, dict) and part in node:
                    node = node[part]
                else:
                    return default
            if isinstance(node, (dict, list)):
                return copy.deepcopy(node)
            return node
        except (KeyError, TypeError, AttributeError) as e:
            _logger.warning(f"설정값 조회 실패 ({dotted_key}): {e}")
            return default

    # Convenience properties used in settings
    @property
    def default_scale(self) -> str:
        return self.get("mixing.default_scale", "M-65")

    @property
    def tolerance(self) -> float:
        try:
            return float(self.get("mixing.tolerance", 0.05))
        except (ValueError, TypeError) as e:
            _logger.warning(f"tolerance 변환 실패: {e}")
            return 0.05

    @property
    def workers(self) -> list:
        """Get the list of workers from config."""
        return self.get("mixing.workers", ["김민호", "김민호3", "문동식"])

    @property
    def last_worker(self) -> str:
        """Get the last selected worker."""
        return self.get("mixing.last_worker", "")

    @property
    def scan_effects(self) -> dict:
        """Get the scan effects settings."""
        return self.get("scan_effects", {
            "blur_radius": 0.3,
            "noise_range": 25,
            "contrast_factor": 1.4,
            "brightness_factor": 1.10
        })


    def save_scan_effects(self, effects_data: dict) -> bool:
        """Save the scan effects settings to the config file."""
        try:
            if 'scan_effects' not in self._data:
                self._data['scan_effects'] = {}
            self._data['scan_effects'].update(effects_data)
            return self._save_config()
        except (OSError, TypeError, ValueError) as e:
            _logger.warning(f"스캔 효과 저장 실패: {e}")
            return False

    def save_workers(self, workers: list) -> bool:
        """Save the workers list to the config file."""
        try:
            if 'mixing' not in self._data:
                self._data['mixing'] = {}
            self._data['mixing']['workers'] = workers
            return self._save_config()
        except (OSError, TypeError, ValueError) as e:
            _logger.warning(f"작업자 목록 저장 실패: {e}")
            return False

    def save_last_worker(self, worker_name: str) -> bool:
        """Save the last selected worker to the config file."""
        try:
            if 'mixing' not in self._data:
                self._data['mixing'] = {}
            self._data['mixing']['last_worker'] = worker_name
            return self._save_config()
        except (OSError, TypeError, ValueError) as e:
            _logger.warning(f"마지막 작업자 저장 실패: {e}")
            return False

    @property
    def sidebar_hover_expand(self) -> bool:
        """Return whether sidebar hover auto-expand is enabled."""
        return bool(self.get("ui.sidebar_hover_expand", False))

    def save_sidebar_hover_expand(self, enabled: bool) -> bool:
        """Save sidebar hover auto-expand setting."""
        try:
            if "ui" not in self._data or not isinstance(self._data.get("ui"), dict):
                self._data["ui"] = {}
            self._data["ui"]["sidebar_hover_expand"] = bool(enabled)
            return self._save_config()
        except (OSError, TypeError, ValueError) as e:
            _logger.warning(f"sidebar hover expand save failed: {e}")
            return False

    def _get_admin_password(self) -> str:
        """Get the legacy admin password from config (internal use only)."""
        return self.get("admin.password", "")

    def verify_admin_password(self, password: str) -> bool:
        """Verify the admin password."""
        admin = self._data.get("admin", {})
        if not isinstance(admin, dict):
            admin = {}

        salt_b64 = admin.get("password_salt")
        hash_b64 = admin.get("password_hash")
        if salt_b64 and hash_b64:
            return self._verify_password(password, salt_b64, hash_b64)

        legacy_password = admin.get("password") or self._get_admin_password()
        if legacy_password and password == legacy_password:
            self.set_admin_password(password, remove_legacy=True)
            return True

        return False

    def is_admin_password_set(self) -> bool:
        """Return True if an admin password (hash or legacy) exists."""
        admin = self._data.get("admin", {})
        if not isinstance(admin, dict):
            admin = {}
        if admin.get("password_salt") and admin.get("password_hash"):
            return True
        legacy_password = admin.get("password") or self._get_admin_password()
        return bool(legacy_password)

    def set_admin_password(self, password: str, remove_legacy: bool = True) -> bool:
        """Set and store the admin password as a salted hash."""
        if not password:
            return False
        salt_b64, hash_b64 = self._hash_password(password)
        admin = self._data.setdefault("admin", {})
        if not isinstance(admin, dict):
            admin = {}
            self._data["admin"] = admin
        admin["password_salt"] = salt_b64
        admin["password_hash"] = hash_b64
        if remove_legacy and "password" in admin:
            del admin["password"]
        return self._save_config()

    def _hash_password(self, password: str, salt: Optional[bytes] = None) -> Tuple[str, str]:
        if salt is None:
            salt = os.urandom(16)
        dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 200000)
        return (
            base64.b64encode(salt).decode("utf-8"),
            base64.b64encode(dk).decode("utf-8"),
        )

    def _verify_password(self, password: str, salt_b64: str, hash_b64: str) -> bool:
        try:
            salt = base64.b64decode(salt_b64.encode("utf-8"))
            expected = base64.b64decode(hash_b64.encode("utf-8"))
        except (ValueError, TypeError) as e:
            _logger.warning(f"비밀번호 검증 디코딩 실패: {e}")
            return False
        dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 200000)
        return hmac.compare_digest(dk, expected)

    def _save_config(self) -> bool:
        """Save the config data to file."""
        try:
            os.makedirs(os.path.dirname(self._config_path), exist_ok=True)
            with open(self._config_path, "w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=2, ensure_ascii=False)
            return True
        except (OSError, TypeError, ValueError) as e:
            _logger.error(f"설정 파일 저장 실패 ({self._config_path}): {e}")
            return False


# Global singleton-like instance
config = Config()
