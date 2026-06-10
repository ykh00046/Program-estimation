# Google Sheets 백업 견고화 (Backup Hardening) — 완료 보고서

> PDCA Feature: `backup_hardening` (**PDCA #35**)
> 기간: 2026-06-10 (1일) · 최종 Match Rate: **100%** (1차 통과) · 테스트: **341/341**

## 1. 무엇을 해결했나

전체 검토(2026-06-10) High 이슈의 마지막 잔여분 — **백업 실패가 곧 데이터 누락**인 구조를 해소했다.

| 취약점 | Before | After |
|--------|--------|-------|
| V1 dict 순서 의존 | `list(record.values())` — 코드의 키 순서가 시트 데이터 정렬을 좌우 | `BACKUP_COLUMNS` 14컬럼 SSOT + `record.get(col)` 명시 변환 |
| V2 헤더 불일치 = 영구 실패 | 순서만 달라도 매 저장 실패 | 3분기: 빈 시트→헤더 삽입 / 순서만 다름→**시트 순서로 재매핑** / 집합 다름→누락·초과 명시 실패 |
| V3 실패 기록 유실 | 실패 카운터만 증가, 기록 소실 | **JSONL 대기 큐** 적재 → 다음 백업 시 대기분 먼저 자동 flush (시간순 보존) |

## 2. 구현 내역

- **`models/backup/backup_queue.py` (신규)**: gspread 무의존 JSONL 큐.
  손상 줄 관용 파싱, cap 1,000행(오래된 것부터 drop), 모듈 Lock(#33 워커 직렬화),
  파일 I/O 실패는 경고만(큐는 best-effort 보조 — 백업 본 로직 불간섭)
- **`google_sheets_backup.py`**: `_resolve_header_order`(3분기), `_fail_and_enqueue`(실패 공통),
  성공 시에만 `queue.clear()` (append_rows 단일 호출 = 전부/전무)
- **정책 경계**: 설정 문제(비활성/미설정/인증 실패)는 큐 미적재 — 재시도 무의미,
  설정 수정 후 다음 백업에서 자연 재개. 전송/헤더 실패만 적재
- **공개 계약 불변**: `backup_records(records) -> (bool, str)` — DataManager/#33 워커 무변경
- **parity 테스트**: `DataManager._build_backup_records` 키 == `BACKUP_COLUMNS` (#27 교훈 —
  두 모듈에 분산된 스키마의 어긋남을 테스트로 강제 차단)

## 3. PDCA 사이클 기록

| 단계 | 결과 |
|------|------|
| Plan | 코드 분석으로 V1~V3 취약점 위치 특정, 범위 확정 (주기 스케줄러·수동 재시도 버튼은 후속) |
| Design | 흐름도 + 오류 정책 표 + BackupQueue 계약 |
| Do | 큐 모듈 신규 + 백업 모듈 견고화 + 테스트 20개 (큐 8 + 백업 12) |
| Check | **100% 1차 통과** — 미구현 0, iterate 불필요 |

## 4. 교훈 (Lessons Learned)

1. **"시트가 진실" 관용 정책**: 사용자가 만지는 외부 자원(스프레드시트)의 컬럼 순서를
   코드가 강제하면 영구 실패 루프가 된다. 집합이 같으면 외부 순서를 존중해 재매핑하고,
   집합이 다를 때만 명확히 실패하는 2단계 비교가 옳다.
2. **재시도 큐는 "다음 자연 기회"면 충분**: 저장이 빈번한 앱에서는 별도 스케줄러 없이
   다음 백업 시점에 pending 선(先)flush만으로 자동 복구된다 — 복잡도 대비 효과 최적.
3. **분산 스키마는 parity 테스트로 봉인**: SSOT 상수와 페이로드 빌더가 다른 모듈에 있으면
   (import 순환 회피) 정합은 테스트로 강제 — #27 교훈의 재적용.

## 5. 후속 과제

- 수동 "지금 재시도" 버튼 + 대기 건수 상태 표시 (선택 — 현재는 자동 flush로 충분)
- **2026-06-10 전체 검토 High 3건 모두 종결** (#33 UI 스레드, #34 재고 정합성, #35 백업)
- 다음 혁신 후보: 바코드 LOT 입력, SPC 배합 편차 분석, Excel COM 탈피(reportlab)

## 6. 산출물

- 코드: `backup_queue.py`(신규), `google_sheets_backup.py`
- 테스트: `test_backup_queue.py`(8) + `test_google_sheets_backup.py`(12) — 총 341 통과
- 문서: plan / design / analysis / report
