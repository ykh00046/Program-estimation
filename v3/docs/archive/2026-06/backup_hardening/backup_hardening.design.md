# Google Sheets 백업 견고화 (Backup Hardening) — Design

> PDCA Feature: `backup_hardening` (PDCA #35)
> 작성일: 2026-06-10 · Plan: `docs/01-plan/features/backup_hardening.plan.md`

## 1. 아키텍처 개요

```
DataManager.backup_lot_to_sheets (#33 워커 스레드)
        │ records: List[Dict] (14키)
        ▼
GoogleSheetsBackup.backup_records
        │ 1. 설정/인증 가드 (기존 그대로 — 실패해도 큐 미적재)
        │ 2. pending = BackupQueue.load()  ← 대기분 먼저 (시간순 보존)
        │ 3. rows = pending + records → BACKUP_COLUMNS 기준 변환
        │ 4. 헤더 검사: 빈 시트→삽입 / 순서만 다름→시트 순서로 재매핑 / 집합 다름→실패
        │ 5. append_rows (단일 호출 = 전부/전무)
        ├─ 성공 → BackupQueue.clear() + 성공 카운터/시각
        └─ 전송/헤더 실패 → BackupQueue.enqueue(records) (이번 신규분만 —
                            pending은 이미 큐에 있음) + 실패 카운터
```

**공개 계약 불변**: `backup_records(records) -> Tuple[bool, str]` 시그니처·반환 유지.
DataManager/UI 변경 없음 — 메시지 문자열만 큐 상태를 반영해 풍부해짐.

## 2. 컴포넌트 설계

### 2.1 `models/backup/backup_queue.py` (신규 — gspread 무의존 순수 모듈)

```python
# 모듈 상수
DEFAULT_QUEUE_PATH = os.path.join(USER_CONFIG_DIR, "backup_pending.jsonl")
MAX_QUEUE_ROWS = 1000
_QUEUE_LOCK = threading.Lock()   # 프로세스 내 워커 동시 접근 직렬화 (#33)

class BackupQueue:
    def __init__(self, path: str = DEFAULT_QUEUE_PATH,
                 max_rows: int = MAX_QUEUE_ROWS) -> None: ...

    def enqueue(self, records: List[Dict]) -> int:
        """records를 JSONL로 append. cap 초과 시 오래된 줄부터 drop + 경고.
        Returns: 적재 후 총 대기 행 수."""

    def load(self) -> List[Dict]:
        """대기 행 전부 로드. 손상 줄은 스킵 + 경고 (관용 파싱)."""

    def clear(self) -> None:
        """큐 파일 삭제 (flush 성공 후)."""

    def count(self) -> int:
        """대기 행 수 (상태 표시/테스트용)."""
```

- 파일 I/O 실패는 모두 `try/except OSError` → 경고 로그 + 안전값 반환 (백업 로직을 죽이지 않음)
- JSON 직렬화: `ensure_ascii=False`, 한 줄 = 한 record dict
- cap 적용: `enqueue` 시 기존+신규가 max 초과면 앞(오래된)에서 자르고 `dropped` 경고

### 2.2 `google_sheets_backup.py`

**(a) 컬럼 스키마 SSOT**:
```python
BACKUP_COLUMNS = [
    '제품LOT', '레시피명', '작업자', '작업일자', '작업시간', '총배합량', '스케일',
    '품목코드', '품목명', '자재LOT', '배합비율', '이론량', '실제량', '순서',
]
```
- 행 변환: `[record.get(col, "") for col in BACKUP_COLUMNS]` — dict 순서 무관 (V1 해소)
- DataManager `_build_backup_records`와의 정합은 **parity 테스트**로 강제 (런타임 import 순환 회피)

**(b) 헤더 검사 3분기** (`_resolve_header_order(worksheet) -> Tuple[Optional[List[str]], str]`):
```python
existing = worksheet.row_values(1)
if not existing:
    worksheet.insert_row(BACKUP_COLUMNS, 1)
    return BACKUP_COLUMNS, ""                       # 빈 시트 → 표준 헤더 삽입 (기존 동작)
if existing == BACKUP_COLUMNS:
    return BACKUP_COLUMNS, ""                       # 완전 일치
if set(existing) == set(BACKUP_COLUMNS):
    return existing, "헤더 순서가 달라 시트 순서로 재매핑"   # 순서만 다름 → 시트가 진실 (V2)
missing = [c for c in BACKUP_COLUMNS if c not in existing]
extra = [c for c in existing if c not in BACKUP_COLUMNS]
return None, f"헤더 컬럼 불일치 (누락: {missing}, 초과: {extra})"   # 집합 다름 → 실패
```
- 재매핑은 **컬럼명 기준** `record.get(col, "")` — 위치 기반 매핑 금지 (Plan 리스크 3)

**(c) `backup_records` 큐 통합 흐름**:
```python
# 가드 3종(비활성/미설정/인증 실패)은 기존 그대로 — 큐 미적재 (설정 문제는 재시도 무의미)
pending = self.queue.load()
all_records = pending + (records or [])
if not all_records: return True, "백업할 기록이 없습니다."
header_order, note = self._resolve_header_order(worksheet)
if header_order is None:
    total = self.queue.enqueue(records or [])
    실패 카운터; return False, f"{note} — 신규 {len(records)}건 대기 적재 (총 {total}건)"
rows = [[r.get(col, "") for col in header_order] for r in all_records]
try:
    worksheet.append_rows(rows)
except (전송 예외):
    total = self.queue.enqueue(records or [])
    실패 카운터; return False, f"... — 신규 {len(records)}건 대기 적재 (총 {total}건)"
self.queue.clear()                                  # 단일 append = 전부/전무 → 성공 시에만 clear
성공 카운터/시각
msg = f"{len(all_records)}건 백업 완료" + (f" (대기 {len(pending)}건 포함)" if pending else "")
```
- `GoogleSheetsBackup.__init__(config, queue: Optional[BackupQueue] = None)` —
  기본 생성, 테스트는 임시 경로 큐 주입
- `gc`/worksheet 접근은 기존 구조 유지. 예외 분기(SpreadsheetNotFound/WorksheetNotFound/Exception)도
  유지하되 각 분기에서 enqueue 추가

## 3. 오류 처리 정책

| 상황 | 큐 | 반환 | 근거 |
|------|:--:|------|------|
| 백업 비활성/미설정/인증 실패 | 적재 안 함 | False + 기존 메시지 | 설정 문제 — 수정 후 다음 백업에서 자연스럽게 신규분부터 재개 |
| 헤더 집합 불일치 | **적재** | False + 누락/초과 명시 | 시트 수정 후 다음 백업에서 대기분 자동 flush |
| 전송 실패 (네트워크 등) | **적재** | False + 대기 건수 | 일시 장애 — 다음 백업에서 자동 재시도 |
| 성공 | clear | True + 대기 포함 건수 | |
| 큐 파일 I/O 실패 | — | 경고 로그, 백업 결과에는 영향 없음 | 큐는 best-effort 보조 장치 |

## 4. 테스트 계획

| 테스트 | 파일 | 검증 |
|--------|------|------|
| 큐 기본 | `tests/unit/test_backup_queue.py` (신규, tmp 경로) | enqueue→load 왕복, clear, count, 빈 파일 |
| 큐 관용 파싱 | 〃 | 손상 줄(비JSON) 스킵 + 정상 줄 유지 |
| 큐 cap | 〃 | max 초과 시 오래된 행 drop, 총량 유지 |
| parity | `tests/unit/test_google_sheets_backup.py` (신규) | `DataManager._build_backup_records` 산출 키 == `BACKUP_COLUMNS` (#27 교훈) |
| 행 변환 | 〃 | dict 키 순서 뒤섞인 record → BACKUP_COLUMNS 순서로 변환 |
| 헤더 3분기 | 〃 (worksheet mock) | 빈 시트 insert_row / 완전 일치 / 순서 다름 재매핑(값이 시트 헤더 순서) / 집합 다름 실패 메시지 |
| 실패→큐 적재 | 〃 (append_rows 예외 mock) | 신규분 enqueue + False + 메시지에 대기 건수 |
| 성공→pending flush | 〃 | 큐에 대기분 있는 상태에서 성공 → append_rows에 대기+신규 모두 전달 + clear |
| 가드 경로 큐 미적재 | 〃 | 비활성/인증 실패 시 enqueue 미호출 |
| 회귀 | `run_tests.py` | 기존 321개 통과 |

> gspread 미설치 환경 대비: 백업 테스트는 `GoogleSheetsBackup`의 `gc`/`_authenticate`를
> mock 주입하고 worksheet는 MagicMock — gspread 실모듈 불필요.
> `gspread.exceptions` 참조 경로는 모듈 가용 여부에 따라 동작하므로 테스트에서 일반 Exception 사용.

## 5. 구현 순서

1. `backup_queue.py` + 큐 단위 테스트
2. `google_sheets_backup.py`: BACKUP_COLUMNS + 헤더 3분기 + 큐 통합
3. 백업 단위 테스트 (mock) + parity 테스트
4. 전체 회귀 + 보고

## 6. 호환성 체크리스트

- [ ] `backup_records` 시그니처/반환 튜플 계약 불변 (DataManager/#33 워커 무변경)
- [ ] Python 3.9 typing
- [ ] gspread 미설치 환경에서 모듈 임포트 안전 (기존 지연 임포트 구조 유지)
- [ ] 빈 시트 헤더 삽입 등 기존 동작 보존
- [ ] 함수 20줄 이내 / 타입 힌트

## 7. 다음 단계

→ `/pdca do backup_hardening`
