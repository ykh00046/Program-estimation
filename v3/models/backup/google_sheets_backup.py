"""
Google Sheets 백업 로직을 담당하는 모듈.
BackupProvider 프로토콜을 구현합니다.
"""

import os
from typing import Protocol, List, Dict, Any, Optional, Tuple

# Google Sheets 백업은 선택 기능이다. 관련 의존성(gspread/google-auth)이 없거나
# 손상된 환경에서도 앱 전체(데이터 계층) 임포트가 실패하지 않도록 지연/안전 임포트한다.
try:
    import gspread
    from google.oauth2.service_account import Credentials
    from google.auth.exceptions import DefaultCredentialsError, TransportError
    GSPREAD_AVAILABLE = True
except ImportError:  # pragma: no cover - 의존성 미설치 환경 방어
    gspread = None
    Credentials = None
    DefaultCredentialsError = TransportError = Exception  # 미사용 경로의 NameError 방지용 별칭
    GSPREAD_AVAILABLE = False

from config.google_sheets_config import GoogleSheetsConfig
from models.backup.backup_queue import BackupQueue
from utils.logger import logger

# Google Sheets API 스코프
SCOPES = [
    'https://spreadsheets.google.com/feeds',
    'https://www.googleapis.com/auth/drive',
]

# 백업 컬럼 스키마 SSOT (PDCA #35) — 행 변환은 항상 이 순서를 따른다.
# DataManager._build_backup_records의 키와 parity 테스트로 정합을 강제한다.
BACKUP_COLUMNS = [
    '제품LOT', '레시피명', '작업자', '작업일자', '작업시간', '총배합량', '스케일',
    '품목코드', '품목명', '자재LOT', '배합비율', '이론량', '실제량', '순서',
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

    def __init__(self, google_sheets_config: GoogleSheetsConfig,
                 queue: Optional[BackupQueue] = None):
        self.config = google_sheets_config
        self.gc = None # gspread 클라이언트
        # 실패 시 재시도용 로컬 대기 큐 (PDCA #35). 테스트는 임시 경로 큐 주입.
        self.queue = queue if queue is not None else BackupQueue()

    def _authenticate(self) -> bool:
        """Google Sheets API 인증을 수행합니다."""
        if not GSPREAD_AVAILABLE:
            logger.error("gspread/google-auth 미설치로 Google Sheets 백업을 사용할 수 없습니다.")
            return False

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

        # 대기분 먼저 합쳐 시간순 보존 (PDCA #35) — pending은 이미 큐에 있으므로
        # 실패 시에는 이번 신규분만 추가 적재한다.
        pending = self.queue.load()
        all_records = pending + list(records or [])
        if not all_records:
            logger.info("백업할 기록이 없습니다.")
            return True, "백업할 기록이 없습니다."

        spreadsheet_url = self.config.get_spreadsheet_url()
        try:
            # 스프레드시트 열기
            spreadsheet = self.gc.open_by_url(spreadsheet_url)

            # 첫 번째 워크시트 선택 (혹은 이름으로 특정 워크시트 선택)
            worksheet = spreadsheet.worksheet("배합 기록") # 워크시트 이름을 '배합 기록'으로 가정

            header_order, note = self._resolve_header_order(worksheet)
            if header_order is None:
                return self._fail_and_enqueue(records, note)
            if note:
                logger.warning(note)

            # 컬럼명 기준 변환 — dict 순서/위치 무관 (PDCA #35 V1)
            data_to_append = [
                [record.get(col, "") for col in header_order]
                for record in all_records
            ]

            # 스프레드시트에 행 추가 (단일 호출 = 전부/전무)
            worksheet.append_rows(data_to_append)

            self.queue.clear()
            self.config.increment_backup_success()
            self.config.set_last_backup_time()
            msg = f"{len(all_records)}개의 기록을 Google Sheets에 성공적으로 백업했습니다."
            if pending:
                msg += f" (대기 {len(pending)}건 포함)"
            logger.info(msg)
            return True, msg

        except gspread.exceptions.SpreadsheetNotFound:
            return self._fail_and_enqueue(
                records, f"Google 스프레드시트 '{spreadsheet_url}'를 찾을 수 없습니다.")
        except gspread.exceptions.WorksheetNotFound:
            return self._fail_and_enqueue(
                records, "'배합 기록' 워크시트를 찾을 수 없습니다.")
        except Exception as e:
            return self._fail_and_enqueue(
                records, f"Google Sheets 백업 중 오류 발생: {e}")

    def _resolve_header_order(self, worksheet) -> Tuple[Optional[List[str]], str]:
        """시트 헤더를 검사해 행 변환에 사용할 컬럼 순서를 결정한다 (PDCA #35 V2).

        - 빈 시트: 표준 헤더 삽입 후 표준 순서
        - 완전 일치: 표준 순서
        - 집합 같음 + 순서 다름: 시트가 진실 — 시트 헤더 순서로 재매핑
        - 집합 다름: (None, 누락/초과 명시 메시지) — 호출자가 실패+큐 처리
        """
        existing = worksheet.row_values(1)
        if not existing:
            worksheet.insert_row(BACKUP_COLUMNS, 1)
            return BACKUP_COLUMNS, ""
        if existing == BACKUP_COLUMNS:
            return BACKUP_COLUMNS, ""
        if set(existing) == set(BACKUP_COLUMNS):
            return existing, ("Google Sheets 헤더 순서가 표준과 달라 시트 순서로 재매핑합니다. "
                              f"시트: {existing}")
        missing = [c for c in BACKUP_COLUMNS if c not in existing]
        extra = [c for c in existing if c not in BACKUP_COLUMNS]
        return None, (f"Google Sheets 헤더 컬럼이 백업 스키마와 다릅니다 "
                      f"(누락: {missing}, 초과: {extra}). 시트 헤더를 수정하세요.")

    def _fail_and_enqueue(self, records: List[Dict[str, Any]], reason: str) -> Tuple[bool, str]:
        """전송/헤더 실패 공통 처리: 신규분 큐 적재 + 실패 카운터 (PDCA #35 V3)."""
        logger.error(f"Google Sheets 백업 실패: {reason}")
        self.config.increment_backup_failure()
        total = self.queue.enqueue(list(records or []))
        if records:
            return False, f"{reason} — 신규 {len(records)}건 대기 적재 (총 {total}건, 다음 백업 시 자동 재시도)"
        return False, reason
