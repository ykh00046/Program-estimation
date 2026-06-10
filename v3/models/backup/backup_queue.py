"""백업 대기 큐 (PDCA #35 backup_hardening).

Google Sheets 백업 실패 시 기록을 로컬 JSONL 파일에 적재해 두었다가
다음 백업 시점에 자동 재시도한다. gspread 무의존 순수 모듈.

규약:
- 한 줄 = 한 record dict (ensure_ascii=False)
- 손상 줄은 스킵 + 경고 (관용 파싱) — 강제 종료 중 append 대비
- 상한(max_rows) 초과 시 가장 오래된 행부터 drop + 경고 (무한 성장 방지)
- 파일 I/O 실패는 경고 로그 + 안전값 반환 — 큐는 best-effort 보조 장치이며
  백업 본 로직을 죽이지 않는다.
- 모듈 Lock으로 워커 스레드(#33) 동시 접근을 직렬화한다.
"""
import json
import os
import threading
from typing import Dict, List

from config.settings import USER_CONFIG_DIR
from utils.logger import logger

DEFAULT_QUEUE_PATH = os.path.join(USER_CONFIG_DIR, "backup_pending.jsonl")
MAX_QUEUE_ROWS = 1000

_QUEUE_LOCK = threading.Lock()


class BackupQueue:
    """JSONL 기반 백업 대기 큐."""

    def __init__(self, path: str = DEFAULT_QUEUE_PATH,
                 max_rows: int = MAX_QUEUE_ROWS) -> None:
        self.path = path
        self.max_rows = max_rows

    def enqueue(self, records: List[Dict]) -> int:
        """records를 큐에 적재한다. 반환: 적재 후 총 대기 행 수."""
        if not records:
            return self.count()
        with _QUEUE_LOCK:
            rows = self._load_unlocked()
            rows.extend(records)
            if len(rows) > self.max_rows:
                dropped = len(rows) - self.max_rows
                rows = rows[dropped:]
                logger.warning(f"백업 대기 큐 상한 초과: 오래된 {dropped}건 폐기 "
                               f"(상한 {self.max_rows}건)")
            self._write_unlocked(rows)
            total = len(rows)
        logger.info(f"백업 대기 큐 적재: +{len(records)}건 (총 {total}건)")
        return total

    def load(self) -> List[Dict]:
        """대기 행 전부 로드 (손상 줄 스킵)."""
        with _QUEUE_LOCK:
            return self._load_unlocked()

    def clear(self) -> None:
        """큐 파일 삭제 (flush 성공 후 호출)."""
        with _QUEUE_LOCK:
            try:
                if os.path.exists(self.path):
                    os.remove(self.path)
            except OSError as e:
                logger.warning(f"백업 대기 큐 삭제 실패: {e}")

    def count(self) -> int:
        """대기 행 수."""
        return len(self.load())

    # ------------------------------------------------------------------
    # 내부 (Lock 보유 상태에서만 호출)
    # ------------------------------------------------------------------

    def _load_unlocked(self) -> List[Dict]:
        if not os.path.exists(self.path):
            return []
        rows: List[Dict] = []
        skipped = 0
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        row = json.loads(line)
                    except json.JSONDecodeError:
                        skipped += 1
                        continue
                    if isinstance(row, dict):
                        rows.append(row)
                    else:
                        skipped += 1
        except OSError as e:
            logger.warning(f"백업 대기 큐 읽기 실패: {e}")
            return []
        if skipped:
            logger.warning(f"백업 대기 큐 손상 줄 {skipped}건 스킵")
        return rows

    def _write_unlocked(self, rows: List[Dict]) -> None:
        try:
            queue_dir = os.path.dirname(self.path)
            if queue_dir:
                os.makedirs(queue_dir, exist_ok=True)
            with open(self.path, "w", encoding="utf-8") as f:
                for row in rows:
                    f.write(json.dumps(row, ensure_ascii=False) + "\n")
        except OSError as e:
            logger.warning(f"백업 대기 큐 쓰기 실패: {e}")


__all__ = ["BackupQueue", "DEFAULT_QUEUE_PATH", "MAX_QUEUE_ROWS"]
