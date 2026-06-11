# 기록 조회 임베드 + 상태바 겹침 수정 — 완료 보고서

> PDCA Feature: `records_embed_statusbar_fix` (**PDCA #38**, 경량 Plan+Report)
> 2026-06-11 · 커밋 **eaef1ff** · 테스트 **371/371** (+7, 회귀 0)

## 1. 결과

| 요구 | Before | After |
|------|--------|-------|
| 기록 조회 | 사이드바 → 버튼 → 별도 다이얼로그 | 사이드바 탭 진입 즉시 표시. 전환 때마다 기록 새로고침 + 스캔효과 최신화 |
| 상태바 겹침 | "기본 스케일..." 와 "준비됨" 포개짐 | main_label 단일 경로 — 겹침 제거 |

## 2. 구현 요점

- `builders.RecordsHostPage`: showEvent lazy 생성 — 시작 시점 비용 0, 재진입 시
  `load_records()` + `effects_params` 갱신 (배합 저장 후 탭 전환 시 최신 기록 보장)
- `RecordViewDialog(embedded=True)`: 닫기 버튼 미생성 + `reject()` 무시 (ESC가 페이지를
  숨기는 QDialog 기본 동작 차단). 다이얼로그 모드(기본값)는 비트 보존 — 기존 스모크 무수정 통과
- `StatusController.set_message`: 커스텀 StatusBar의 `show_message(timeout=0)` 우선 —
  **QStatusBar.showMessage의 임시 메시지는 위젯 위에 겹쳐 그려진다**는 Qt 동작이 겹침의 근본 원인
- `main_window`: 죽은 `_open_records` 제거, closeEvent 워커 대기 owner에 임베드 뷰 추가
  (#33/#36 종료 안전 계약 유지)

## 3. 교훈

1. **QDialog는 레이아웃에 넣으면 인라인 child가 되지만, ESC→reject→hide 기본 동작이
   따라온다** — 임베드 시 reject 무시가 필수.
2. **QStatusBar에서 위젯 라벨과 showMessage를 혼용하면 겹친다** — 임시 메시지는 위젯을
   가리는 오버레이. 한 경로만 쓸 것.

## 4. 부수 기록

웹 전환 질문은 "데스크톱 유지 + 멀티유저 요구 발생 시 models 재사용해 FastAPI 검토"로 합의.
