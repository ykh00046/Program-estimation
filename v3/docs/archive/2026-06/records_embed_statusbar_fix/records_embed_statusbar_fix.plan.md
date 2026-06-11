# 기록 조회 임베드 + 상태바 겹침 수정 — Plan (경량 사이클)

> PDCA Feature: `records_embed_statusbar_fix` (PDCA #38, 경량 — Plan+Report)
> 작성일: 2026-06-11 · 출처: 수동 QA 중 사용자 직접 요청 2건

## 1. 요구사항 (사용자 원문 기반)

| # | 요구 | 현상 |
|---|------|------|
| 1 | "기록 조회를 새 창으로 운용할 필요 없음 — 그 창을 바로 보여주면 됨" | 사이드바 "기록 조회"가 버튼 1개짜리 액션 페이지 → 클릭 시 별도 다이얼로그 |
| 2 | "배합 메뉴 바텀에 스케일·준비됨 글자가 겹침" | 상태바에서 "기본 스케일..." 안내와 "준비됨"이 포개져 표시 |

## 2. 원인 분석

1. **임베드 부재**: `builders.py`가 `build_action_page(... window._open_records)`로 구성 —
   RecordViewDialog는 exec() 전용.
2. **겹침**: 커스텀 `StatusBar`(components.py:216)는 자체 `main_label("준비됨")`을
   addWidget으로 보유하는데, `StatusController.set_message`가 `QStatusBar.showMessage()`
   호출 — **임시 메시지는 상태바 위젯 위에 겹쳐 그려지는 Qt 동작**이라 두 텍스트가 포개짐.

## 3. 해법

1. `RecordsHostPage`(builders) — showEvent마다 lazy 생성/새로고침/효과 최신화.
   `RecordViewDialog(embedded=True)`: 닫기 숨김 + reject(ESC) 무시. 종료 워커 대기 포함.
2. `set_message`가 `show_message(message, timeout=0)`(main_label 직접 갱신) 우선 사용,
   일반 QStatusBar엔 기존 showMessage 폴백.

## 4. 부수 결정 — 웹 전환 질문 (사용자 제기, 동일 시점)

데스크톱 유지 권고로 합의: 통증(창 운용·겹침)은 1~2일 수정 vs 웹은 수개월 재작성 +
Excel COM 강결합(DHR 실적서) + 단일 사용자/로컬 SQLite 운영 환경. models 계층이
UI 무관(#28)이므로 멀티유저 요구 발생 시 FastAPI 전환 문은 열려 있음.
