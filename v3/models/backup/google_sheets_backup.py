"""
Google Sheets 백업 로직을 담당하는 모듈.
BackupProvider 프로토콜을 구현합니다.
"""

import os
from typing import Protocol, List, Dict, Any, Tuple
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials
from google.auth.exceptions import DefaultCredentialsError, TransportError

from config.google_sheets_config import GoogleSheetsConfig
from utils.logger import logger

# Google Sheets API 스코프
SCOPES = [
    'https://spreadsheets.google.com/feeds',
    'https://www.googleapis.com/auth/drive',
]

class BackupProvider(Protocol):
    """
    백업 제공자 프로토콜.
    모든 백업 구현체는 이 프로토콜을 따라야 합니다.
    """
    def backup_records(self, records: List[Dict[str, Any]]) -> Tuple[bool, str]:
        """
        주어진 기록들을 백업 저장소에 저장합니다.
        :param records: 백업할 기록들의 리스트 (예: [{"제품LOT": "LOT123", ...}])
        :return: 백업 성공 여부 (bool)와 메시지 (str) 튜플
        """
        ...

class GoogleSheetsBackup:
    """Google Sheets를 이용한 백업 구현체"""

    def __init__(self, google_sheets_config: GoogleSheetsConfig):
        self.config = google_sheets_config
        self.gc = None # gspread 클라이언트

    def _authenticate(self) -> bool:
        """Google Sheets API 인증을 수행합니다."""
        if self.gc:
            return True # 이미 인증됨

        creds_file = self.config.get_credentials_file()
        if not creds_file or not os.path.exists(creds_file):
            logger.error(f"Google Sheets 인증 파일이 없거나 찾을 수 없습니다: {creds_file}")
            return False

        try:
            # 서비스 계정 인증
            creds = Credentials.from_service_account_file(creds_file, scopes=SCOPES)
            self.gc = gspread.authorize(creds)
            logger.info("Google Sheets API 인증 성공.")
            return True
        except DefaultCredentialsError as e:
            logger.error(f"Google Sheets 인증 실패 (DefaultCredentialsError): {e}")
            return False
        except TransportError as e:
            logger.error(f"Google Sheets 인증 실패 (네트워크/전송 오류): {e}")
            return False
        except (OSError, IOError) as e:
            logger.error(f"Google Sheets 인증 중 알 수 없는 오류 발생: {e}")
            return False

    def backup_records(self, records: List[Dict[str, Any]]) -> Tuple[bool, str]:
        """
        주어진 기록들을 Google Sheets에 백업합니다.
        
        :param records: 백업할 기록들의 리스트. 각 딕셔너리는 스프레드시트의 한 행을 나타냅니다.
                        키는 헤더가 되고, 값은 해당 셀의 내용이 됩니다.
        :return: 백업 성공 여부 (bool)와 메시지 (str) 튜플
        """
        if not self.config.is_backup_enabled():
            return False, "Google Sheets 백업이 비활성화되어 있습니다."
        
        if not self.config.is_configured():
            return False, "Google Sheets 설정이 완료되지 않았습니다 (인증 파일 또는 스프레드시트 URL 누락)."

        if not self._authenticate():
            return False, "Google Sheets API 인증에 실패했습니다."

        spreadsheet_url = self.config.get_spreadsheet_url()
        try:
            # 스프레드시트 열기
            spreadsheet = self.gc.open_by_url(spreadsheet_url)
            
            # 첫 번째 워크시트 선택 (혹은 이름으로 특정 워크시트 선택)
            worksheet = spreadsheet.worksheet("배합 기록") # 워크시트 이름을 '배합 기록'으로 가정
            
            if not records:
                logger.info("백업할 기록이 없습니다.")
                return True, "백업할 기록이 없습니다."

            # 헤더 추출 (첫 번째 기록의 키들을 사용)
            headers = list(records[0].keys())
            
            # 기존 헤더 확인 및 업데이트 (선택 사항: 필요한 경우)
            existing_headers = worksheet.row_values(1)
            if not existing_headers:
                worksheet.insert_row(headers, 1)
            elif existing_headers != headers:
                msg = "Google Sheets 헤더가 백업 데이터와 다릅니다. 헤더를 맞춘 후 다시 시도하세요."
                logger.error(f"{msg} 기존: {existing_headers}, 기대: {headers}")
                self.config.increment_backup_failure()
                return False, msg
            
            # 데이터를 gspread에 맞는 형식으로 변환 (리스트의 리스트)
            data_to_append = [list(record.values()) for record in records]
            
            # 스프레드시트에 행 추가
            worksheet.append_rows(data_to_append)
            
            self.config.increment_backup_success()
            self.config.set_last_backup_time()
            logger.info(f"{len(records)}개의 기록을 Google Sheets에 성공적으로 백업했습니다.")
            return True, f"{len(records)}개의 기록을 Google Sheets에 성공적으로 백업했습니다."

        except gspread.exceptions.SpreadsheetNotFound:
            logger.error(f"지정된 Google 스프레드시트 '{spreadsheet_url}'를 찾을 수 없습니다.")
            self.config.increment_backup_failure()
            return False, f"Google 스프레드시트 '{spreadsheet_url}'를 찾을 수 없습니다."
        except gspread.exceptions.WorksheetNotFound:
            logger.error(f"스프레드시트 내에 '배합 기록' 워크시트를 찾을 수 없습니다.")
            self.config.increment_backup_failure()
            return False, f"'배합 기록' 워크시트를 찾을 수 없습니다."
        except Exception as e:
            logger.error(f"Google Sheets 백업 중 오류 발생: {e}")
            self.config.increment_backup_failure()
            return False, f"Google Sheets 백업 중 오류 발생: {e}"
