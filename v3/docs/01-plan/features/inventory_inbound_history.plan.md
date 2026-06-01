# PDCA #30 Plan — inventory_inbound_history (재고 입고/매입 등록 + 입출고 이력 추적)

> 작성일: 2026-06-02 · Level: Starter (PySide6 데스크톱) · 선행: PDCA #27(임계값 알림) · #29(자동 차감)

## 1. 배경 / 문제 정의

PDCA #27에서 재고 임계값 알림, #29에서 배합 저장 시 자동 차감(CONSUME)을 구현했다.
그러나 현재 재고 시스템에는 두 가지 결정적 공백이 있다.

1. **입고(증가) 경로 부재** — 재고를 *늘리는* 방법이 `StockSettingsDialog`에서 현재고 칸을
   직접 절대값으로 덮어쓰는 것뿐이다. "오늘 ○○자재 50kg 매입"처럼 **기존 재고에 더하는**
   자연스러운 입고 업무 흐름이 없다. 절대값 덮어쓰기는 실수(이전 값 망각)와 동시 편집 충돌에 취약하다.
2. **이동 이력(감사 로그) 부재** — 재고가 언제·왜·얼마나 바뀌었는지 추적이 불가능하다.
   자동 차감이 일어나도(✓ #29) 흔적이 남지 않아, "재고가 왜 이 숫자지?"에 답할 수 없다.
   제조 현장의 자재 관리는 **입출고 내역 추적**이 사실상 필수다.

→ 메모리 `project_pdca_stock_alert`에 명시된 남은 후속 후보 **"입고/발주 관리 + 차감 이력 감사 로그"** 를 해소한다.

## 2. 목표 (이번 사이클 범위)

| # | 요구사항 | 수용 기준 |
|---|---|---|
| R1 | 입고(매입) 등록 | 자재코드·수량·(선택)단위·메모로 입고 시 `current_stock += 수량`. 마스터에 없으면 신규 생성. |
| R2 | 입출고 이력 영속화 | 모든 재고 이동(INBOUND/CONSUME)을 `material_stock_history`에 기록(자재코드, 유형, 증감량(부호), 이동 후 재고, 메모, 시각). |
| R3 | 자동 차감 이력 연동 | #29 `apply_consumption` 차감 시 동일 트랜잭션에서 CONSUME 이력 기록(차감과 원자적). |
| R4 | 입고 등록 UI | `재고 설정` 다이얼로그에서 "입고 등록" → 자재 선택/신규 입력·수량·메모 입력 다이얼로그. |
| R5 | 이력 조회 UI | `재고 설정` 다이얼로그에서 "입출고 이력" → 이동 내역 테이블(자재/유형/증감/이동후재고/메모/일시), 자재별 필터. |
| R6 | 무회귀 | 기존 214 테스트 통과 유지. #27/#29 공개 동작·시그니처 불변. |

## 3. 비범위 (이번 사이클 제외)

- 발주(PO)·매입처 마스터·단가/금액 관리 (입고 메모에 자유 텍스트로만 허용).
- 배합 기록 수정/삭제 시 재고 원복 (별도 후속 후보 유지).
- 수동 편집(`upsert_material_stock` 절대값 설정)의 ADJUST 이력화 — #27의 검증된 upsert 경로 보존을 위해 이번엔 제외(델타 미상). 입고는 신규 add_inbound 경로로만 이력화.
- 이력 Excel/PDF 내보내기 (대시보드 export는 #25/#26에서 별도 처리).

## 4. 접근 방식 (기존 자산 재사용)

- **신규 테이블 `material_stock_history`** — PDCA #18 교훈(기존 자산 재사용)에 따라 `material_stock`은 그대로 두고 이동 이력만 별도 테이블로 추가. 마스터=현재 상태(SSOT), 이력=불변 로그(append-only).
- **`MaterialStockRepository` 확장** — 신규 클래스 만들지 않고 기존 Repo에 `add_inbound` / `get_stock_history` 추가 + `apply_consumption`에 CONSUME 이력 기록(부호 보존, 반환값 불변). `SqliteManagerBase.get_connection()` 단발 트랜잭션 패턴 유지(PDCA #18/#28).
- **Facade(`database.py`) / `DataManager` 위임** — #28 위임 패턴 그대로(무데코 passthrough).
- **UI는 `StockSettingsDialog`를 재고 허브로 확장** — 버튼 2개("입고 등록", "입출고 이력") 추가. 신규 모달 `InboundDialog`, `StockHistoryDialog`. 기존 패널/대시보드는 무변경(알림 카드는 입고 후 재고 증가로 자동 반영).
- **이동 유형 상수** — `INBOUND` / `CONSUME` / (예약) `ADJUST`. quantity는 **부호 있는 델타**(입고 +, 차감 −)로 저장 → 합산·집계 단순.

## 5. 리스크 / 완화

| 리스크 | 완화 |
|---|---|
| `apply_consumption` 변경이 #29 회귀 유발 | 이력 INSERT는 **순수 추가**(반환값·UPDATE 로직 불변), 동일 트랜잭션. 전체 테스트로 검증. |
| 헤드리스 테스트에서 모달 hang (#20/#23 교훈) | 신규 다이얼로그 스모크는 offscreen + QMessageBox patch. |
| fake db_manager 테스트 호환 | DataManager 위임은 getattr 가드 불필요(실 db_manager 메서드 추가). 단위는 실 Repo(tmp DB)로. |
| 입고 키 해석 불일치(데드 매칭, #27/#29 교훈) | 코드 해석 규칙 `TRIM(code) or name`을 seed/upsert/consume과 동일하게 통일. |

## 6. 산출물

- 코드: `material_stock_repository.py`(+테이블 생성 `database.py`), `data_manager.py`, `database.py`(위임), `ui/dialogs/inbound_dialog.py`(신규), `ui/dialogs/stock_history_dialog.py`(신규), `stock_settings_dialog.py`(버튼 2개).
- 테스트: Repo 단위(입고/이력/차감이력) + DataManager 위임 + 다이얼로그 스모크.
- 문서: design / analysis / report.

## 7. 완료 정의 (DoD)

R1~R6 모두 충족 · 전체 테스트 그린(214 → 증가, 회귀 0) · gap-detector Match ≥ 90%.
