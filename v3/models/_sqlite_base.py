"""SQLite 매니저 공통 베이스 (PDCA #18).

이 모듈은 v3의 SQLite 매니저 클래스(MixingDatabaseManager, DhrDatabaseManager)가
공유하는 인프라(연결 컨텍스트, 디렉토리 생성, 표준 PRAGMA, 에러 변환)를 제공한다.

도메인 로직(테이블 스키마, 도메인 메서드)은 상속 클래스가 보유한다.

규약:
- 하위 클래스는 __init__에서 super().__init__(db_path, log_prefix=...) 호출 후
  자신만의 _create_tables() 등을 호출한다.
- 로그 prefix는 운영 알람 매칭과의 호환을 위해 기존 메시지("데이터베이스 오류",
  "DHR 데이터베이스 오류")와 비트-동일하게 유지된다.
"""
import os
import sqlite3
from contextlib import contextmanager
from typing import Iterator, Optional

from utils.logger import logger
from utils.error_handler import DatabaseError


class SqliteManagerBase:
    """SQLite 파일 기반 매니저 공통 베이스."""

    def __init__(self, db_path: str, log_prefix: str = "데이터베이스") -> None:
        self.db_path = db_path
        self._log_prefix = log_prefix
        self._ensure_database_exists()

    def _ensure_database_exists(self) -> None:
        """DB 파일이 놓일 디렉토리를 확보한다."""
        db_dir = os.path.dirname(self.db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)

    @contextmanager
    def get_connection(self) -> Iterator[sqlite3.Connection]:
        """표준 PRAGMA가 적용된 SQLite 연결 컨텍스트.

        - foreign_keys = ON
        - row_factory = sqlite3.Row
        - 예외 시 rollback + DatabaseError로 변환
        """
        conn: Optional[sqlite3.Connection] = None
        try:
            conn = sqlite3.connect(self.db_path)
            conn.execute("PRAGMA foreign_keys = ON")
            conn.row_factory = sqlite3.Row
            yield conn
        except sqlite3.Error as e:
            if conn is not None:
                conn.rollback()
            logger.error(f"{self._log_prefix} 오류: {e}")
            raise DatabaseError(f"{self._log_prefix} 연결 오류: {e}")
        finally:
            if conn is not None:
                conn.close()
