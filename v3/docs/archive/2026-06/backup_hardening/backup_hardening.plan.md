# Google Sheets 백업 견고화 (Backup Hardening) — Plan

> PDCA Feature: `backup_hardening` (PDCA #35)
> 작성일: 2026-06-10 · Level: Starter (Desktop / PySide6)

## 1. 배경 / 문제 정의

전체 검토(2026-06-10)의 High 이슈 잔여분. `models/backup/google_sheets_backup.py` 분석으로
확인한 취약점 3가지:

| # | 취약점 | 위치 | 영향 |
|---|--------|------|------|
| V1 | **dict 순서 의존 행 변환**: `headers = list(records[0].keys())`, `data = [list(r.values())...]` | `backup_records:112,125` | 페이로드 빌더의 키 순서 변경(코드 수정)만으로 시트 데이터가 어긋남 |
| V2 | **헤더 불일치 = 영구 실패**: `existing_headers != headers` 엄격 비교 → 순서만 달라도 매 저장마다 실패 | `:118-122` | 사용자가 시트 컬럼을 옮기면 백업이 조용히(상태 라벨로만) 영구 중단 |
| V3 | **실패 기록 유실**: 네트워크/헤더 실패 시 실패 카운터만 증가, 기록은 사라짐 | `:135-146` | 일시 네트워크 장애 동안 저장된 배합 기록이 시트에서 누락 — 복구 수단 없음 |

#33에서 백업이 워커 스레드로 분리되어 UI는 안 멈추지만, **실패가 곧 데이터 누락**인 구조는 그대로다.

## 2. 목표 (Goals)

백업 실패가 데이터 누락으로 이어지지 않게 하고(재시도 큐), 헤더/순서 변화에 관용적으로 동작하게 한다.

### 요구사항 매핑

| # | 요구사항 | 충족 방법 |
|---|----------|-----------|
| 1 | 컬럼 순서가 코드 dict 순서에 의존하지 않음 | `BACKUP_COLUMNS` 명시 상수(14컬럼 SSOT) + `record.get(col, "")` 변환 (V1) |
| 2 | 시트 헤더 순서가 달라도 백업 동작 | 컬럼 **집합** 동일 + 순서만 다름 → 시트 헤더 순서로 값 재매핑 (V2) |
| 3 | 컬럼 집합 자체가 다르면 명확한 실패 | 누락/초과 컬럼 명시한 메시지 + 큐 적재 (V2) |
| 4 | 실패한 백업 기록이 유실되지 않음 | 로컬 JSONL 대기 큐(`backup_pending.jsonl`)에 적재 (V3) |
| 5 | 다음 성공 기회에 자동 재시도 | 다음 백업 시점에 **대기분 먼저 flush** 후 신규분 전송 (시간순 보존) |
| 6 | 페이로드 빌더와 컬럼 스키마의 정합 보장 | parity 테스트: `_build_backup_records` 키 == `BACKUP_COLUMNS` (#27 교훈) |

## 3. 범위 (Scope)

### In Scope
- `models/backup/backup_queue.py` **신규**: JSONL 대기 큐 (enqueue/load/clear, 상한 cap,
  프로세스 내 Lock — gspread 무의존 순수 모듈)
- `models/backup/google_sheets_backup.py`:
  - `BACKUP_COLUMNS` 상수 (14컬럼 SSOT) + 명시적 행 변환
  - 헤더 비교를 집합/순서 2단계로: 빈 시트→헤더 삽입(기존), 순서만 다름→재매핑, 집합 다름→실패
  - 실패 경로(인증 제외한 전송/헤더 실패)에서 큐 적재, 성공 경로에서 대기분 선(先)flush
  - 반환 메시지에 큐 상태 반영 ("실패 — N건 대기 적재" / "대기 N건 포함 M건 백업")
- parity 테스트 + 큐/백업 단위 테스트 (gspread mock)
- 기존 321개 회귀 없음

### Out of Scope (후속)
- 주기적 백그라운드 재시도 스케줄러 — 재시도는 "다음 백업 시점"으로 충분 (저장은 빈번)
- 수동 "지금 재시도" 버튼 UI — 큐 flush가 자동이므로 보류
- 다른 백업 제공자(BackupProvider 구현체 추가), 다중 워크시트
- 인증 실패의 큐 적재 — 설정 문제는 재시도 무의미(설정 수정 후 다음 백업에서 자연 flush)

## 4. 핵심 설계 결정 (요약 — 상세는 Design)

1. **컬럼 스키마 SSOT**: `BACKUP_COLUMNS`를 backup 모듈에 정의, DataManager 페이로드와는
   parity 테스트로 정합 강제 (런타임 import 순환 회피).
2. **헤더 관용 정책**: 집합 같음+순서 다름은 사용자의 시트 정리로 흔함 → 시트 순서를 존중해
   재매핑(시트가 진실). 집합 다름은 데이터 정렬 불가 → 명확 실패+큐.
3. **큐는 JSONL append-only**: 한 줄=한 행(dict), 손상 줄은 건너뜀(관용 파싱),
   상한(기본 1,000행) 초과 시 가장 오래된 것부터 drop+경고 (무한 성장 방지).
4. **flush 순서**: 대기분 → 신규분 (시간순 보존). flush 실패 시 신규분도 큐 뒤에 적재.
5. **스레드 안전**: 백업은 #33 워커에서 실행 — 모듈 Lock으로 큐 파일 동시 접근 직렬화.

## 5. 영향 범위 (변경 파일 예상)

| 파일 | 변경 |
|------|------|
| `v3/models/backup/backup_queue.py` | **신규** |
| `v3/models/backup/google_sheets_backup.py` | 컬럼 SSOT + 헤더 관용 + 큐 통합 |
| `v3/tests/unit/test_backup_queue.py` | **신규** |
| `v3/tests/unit/test_google_sheets_backup.py` | **신규** (gspread mock) |

> DataManager/UI 변경 없음 — backup_records 시그니처·반환 계약 유지.

## 6. 리스크 / 완화

| 리스크 | 영향 | 완화 |
|--------|------|------|
| 큐 파일 손상(강제 종료 중 append) | 중 | JSONL 줄 단위 관용 파싱 — 손상 줄 스킵+경고 |
| 큐 무한 성장(장기 네트워크 단절) | 중 | cap 1,000행, 초과 시 오래된 것 drop + 경고 로그 |
| 재매핑 버그로 컬럼 어긋남 | 높음 | 재매핑은 컬럼명 기준 `record.get(col)` — 위치 기반 매핑 금지 + 단위 테스트 |
| flush 중 부분 성공(append_rows는 원자적) | 저 | gspread append_rows 단일 호출 = 전부/전무. 성공 시에만 큐 clear |
| gspread 미설치 환경 테스트 | 중 | 큐 모듈은 gspread 무의존, 백업 테스트는 클라이언트/워크시트 mock 주입 |

## 7. 완료 기준 (Definition of Done)

- [ ] 요구사항 1~6 구현
- [ ] gap-detector 일치율 ≥ 90%
- [ ] 신규 테스트 통과 + 기존 321개 회귀 없음
- [ ] backup_records 공개 계약(시그니처/반환 튜플) 불변
- [ ] 완료 보고서 작성

## 8. 다음 단계

→ `/pdca design backup_hardening`
