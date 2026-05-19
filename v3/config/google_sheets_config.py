"""
구글 시트 설정 관리
"""
import os
import json
from datetime import datetime
from typing import Any, Dict, Optional

from config.settings import USER_CONFIG_DIR
from utils.logger import logger  # v3/main 환경에 맞춰 수정


class GoogleSheetsConfig:
    """구글 시트 설정 관리 클래스"""
    
    def __init__(self):
        self.config_file = os.path.join(USER_CONFIG_DIR, 'google_sheets_settings.json')
        self.legacy_config_file = os.path.join(os.path.dirname(__file__), 'google_sheets_settings.json')
        self.config = self._load_config()
    
    def _load_config(self) -> Dict[str, Any]:
        """설정 파일 로드"""
        default_config = {
            'credentials_file': '',
            'spreadsheet_url': '',
            'last_backup_time': None,
            'backup_enabled': False,
            'auto_backup_on_save': True,
            'backup_success_count': 0,
            'backup_failure_count': 0
        }
        
        try:
            target_path = None
            if os.path.exists(self.config_file):
                target_path = self.config_file
            elif os.path.exists(self.legacy_config_file):
                target_path = self.legacy_config_file

            if target_path:
                with open(target_path, 'r', encoding='utf-8') as f:
                    loaded_config = json.load(f)
                    # 기본값과 병합
                    default_config.update(loaded_config)
                    logger.info("구글 시트 설정 로드 완료")
            else:
                logger.info("구글 시트 설정 파일이 없습니다. 기본 설정을 사용합니다.")
        except (OSError, json.JSONDecodeError, UnicodeDecodeError) as e:
            logger.error(f"구글 시트 설정 로드 실패: {e}")
        
        return default_config
    
    def save_config(self) -> bool:
        """설정 파일 저장"""
        try:
            os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, ensure_ascii=False, indent=2)
            logger.info("구글 시트 설정 저장 완료")
            return True
        except (OSError, TypeError, ValueError) as e:
            logger.error(f"구글 시트 설정 저장 실패: {e}")
            return False
    
    def get_credentials_file(self) -> str:
        """인증 파일 경로 반환 (휴대용 실행파일 지원)"""
        file_path = self.config.get('credentials_file', '')
        
        if not file_path:
            return ''
        
        # 절대 경로가 존재하면 그대로 반환
        if os.path.isabs(file_path) and os.path.exists(file_path):
            return file_path
        
        # 절대 경로가 존재하지 않으면 상대 경로로 시도
        # 1. 현재 config 폴더에서 찾기
        config_dir = os.path.dirname(self.config_file)
        relative_path = os.path.join(config_dir, os.path.basename(file_path))
        if os.path.exists(relative_path):
            logger.info(f"JSON 파일을 상대 경로에서 찾음: {relative_path}")
            return relative_path
        
        # 2. 실행파일과 같은 디렉토리의 config 폴더에서 찾기
        import sys
        if getattr(sys, 'frozen', False):
            # 실행파일인 경우
            exe_dir = os.path.dirname(sys.executable)
            exe_config_path = os.path.join(exe_dir, 'config', os.path.basename(file_path))
            if os.path.exists(exe_config_path):
                logger.info(f"JSON 파일을 실행파일 경로에서 찾음: {exe_config_path}")
                return exe_config_path
        
        # 3. 원본 경로 반환 (존재하지 않더라도)
        logger.warning(f"JSON 파일을 찾을 수 없음: {file_path}")
        return file_path
    
    def set_credentials_file(self, file_path: str) -> None:
        """인증 파일 경로 설정"""
        self.config['credentials_file'] = file_path
        self.save_config()
    
    def get_spreadsheet_url(self) -> str:
        """스프레드시트 URL 반환"""
        return self.config.get('spreadsheet_url', '')
    
    def set_spreadsheet_url(self, url: str) -> None:
        """스프레드시트 URL 설정"""
        self.config['spreadsheet_url'] = url
        self.save_config()
    
    def is_backup_enabled(self) -> bool:
        """백업 활성화 상태 반환"""
        return self.config.get('backup_enabled', False)
    
    def set_backup_enabled(self, enabled: bool) -> None:
        """백업 활성화 상태 설정"""
        self.config['backup_enabled'] = enabled
        self.save_config()
    
    def is_auto_backup_on_save(self) -> bool:
        """저장 시 자동 백업 상태 반환"""
        return self.config.get('auto_backup_on_save', True)
    
    def set_auto_backup_on_save(self, enabled: bool) -> None:
        """저장 시 자동 백업 상태 설정"""
        self.config['auto_backup_on_save'] = enabled
        self.save_config()
    
    def get_last_backup_time(self) -> Optional[str]:
        """마지막 백업 시간 반환"""
        return self.config.get('last_backup_time')
    
    def set_last_backup_time(self, backup_time: Optional[str] = None) -> None:
        """마지막 백업 시간 설정"""
        if backup_time is None:
            backup_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        self.config['last_backup_time'] = backup_time
        self.save_config()
    
    def get_backup_success_count(self) -> int:
        """백업 성공 횟수 반환"""
        return self.config.get('backup_success_count', 0)
    
    def increment_backup_success(self) -> None:
        """백업 성공 횟수 증가"""
        self.config['backup_success_count'] = self.config.get('backup_success_count', 0) + 1
        self.save_config()
    
    def get_backup_failure_count(self) -> int:
        """백업 실패 횟수 반환"""
        return self.config.get('backup_failure_count', 0)
    
    def increment_backup_failure(self) -> None:
        """백업 실패 횟수 증가"""
        self.config['backup_failure_count'] = self.config.get('backup_failure_count', 0) + 1
        self.save_config()
    
    def has_valid_settings(self) -> bool:
        """필수 설정값(인증파일, URL) 유효성 확인"""
        credentials_file = self.get_credentials_file()
        return (bool(credentials_file) and 
                os.path.exists(credentials_file) and 
                bool(self.get_spreadsheet_url()))

    def is_configured(self) -> bool:
        """설정 완료 및 활성화 여부 확인"""
        return self.has_valid_settings() and self.is_backup_enabled()
    
    def get_backup_status_text(self) -> str:
        """백업 상태 텍스트 반환"""
        if not self.has_valid_settings():
            return "백업 설정 필요"
            
        if not self.is_backup_enabled():
            return "백업 비활성화"
        
        last_backup = self.get_last_backup_time()
        if last_backup:
            success_count = self.get_backup_success_count()
            failure_count = self.get_backup_failure_count()
            return f"마지막 백업: {last_backup} (성공:{success_count}, 실패:{failure_count})"
        else:
            return "백업 대기중 (기록 없음)"
