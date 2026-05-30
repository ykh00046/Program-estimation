# record_detail_dialog_fix — Completion Report (PDCA #24)

> **Feature**: record_detail_dialog_fix
> **Author**: AI Assistant
> **Created**: 2026-05-31
> **Status**: ✅ Completed
> **Match Rate**: 100%
> **Plan**: [../../01-plan/features/record_detail_dialog_fix.plan.md](../../01-plan/features/record_detail_dialog_fix.plan.md)
> **Design**: [../../02-design/features/record_detail_dialog_fix.design.md](../../02-design/features/record_detail_dialog_fix.design.md)
> **Analysis**: [../../03-analysis/features/record_detail_dialog_fix.analysis.md](../../03-analysis/features/record_detail_dialog_fix.analysis.md)

---

## 1. 요약

PDCA #23 gap-detector가 "범위 외 관찰"로 보고한 `_build_button_bar` 중복을 조사하니, **상세조회 다이얼로그가 완전히 깨져 있던 사전 결함**으로 확대됨.

`RecordDetailDialog`가 `RecordViewDialog`(목록)에서 복사된 메서드를 `init_ui`에서 호출 → 존재하지 않는 `self.load_records`에 connect → **생성 시 AttributeError 크래시**. `show_detail`의 `except Exception`이 이를 흡수해 **상세조회가 항상 "오류" 팝업**으로 실패해 왔다.

복구: `init_ui`를 본래 상세 위젯(기본정보+자재상세+수정/저장 바)으로 재배선, 복사 잔재 삭제, `edit_mode` 초기화.

## 2. 변경 (커밋)

| 커밋 | 내용 |
|---|---|
| `84fa8dc` | init_ui 재배선 + 복사 잔재 4메서드 삭제(-93 LOC) + `self.edit_mode=False` |
| `d57c21e` | 스모크 4케이스(생성/헤더/단일정의/토글) |
| `0642e56` | 버튼 variant 런타임 검증 보강 |

## 3. 검증
- **before**: `RecordDetailDialog(...)` → `AttributeError: ... has no attribute 'load_records'` 크래시 재현.
- **after**: 정상 생성, 자재상세 6열 테이블, 수정모드 토글 동작, 단일 상세 버튼바.
- 전체 스위트 통과(143→detail 스모크 포함), hang 0, stderr 노이즈 0.
- gap-detector **Match 95%→보강 후 100%**.

## 4. 성공 기준 달성 (Plan §4)
- [x] RecordDetailDialog 생성 크래시 0 (info+detail+수정/저장 바)
- [x] `_build_button_bar` 단일 정의, 죽은 목록 메서드 제거
- [x] toggle_edit_mode/save_changes 경로 크래시 0 (edit_mode 초기화)
- [x] 전체 스위트 + 시각 스모크 통과
- [x] Match Rate ≥ 90% (100%)

## 5. 교훈
1. **gap-detector "범위 외 관찰"이 실제 치명 결함을 발굴** — 단순 중복 메서드로 보고됐으나 조사 결과 다이얼로그 전체가 크래시(상세조회 무력화). 관찰 항목도 끝까지 검증할 가치.
2. **복사-붙여넣기 잔재는 connect 시점에 터진다** — `clicked.connect(self.없는메서드)`는 init 중 AttributeError. UI 빌더 복사 시 self 의존 메서드 전수 확인 필요.
3. **`except Exception`(UI 이벤트 경계)이 치명 결함을 장기 은폐** — show_detail의 광역 except가 크래시를 "오류 팝업"으로 흡수해 버그가 오래 안 보였다. 방어적 except의 양면성.
4. **StyledButton은 클래스가 아닌 팩토리 함수** — `findChildren(StyledButton)`은 TypeError. 위젯 탐색은 `QAbstractButton` 등 실제 Qt 타입으로.

## 6. 결론
PDCA #24 완료. 깨져 있던 상세조회 다이얼로그를 복구하고 회귀 가드를 추가. 코드 검토(2026-05-29) 파생 작업 라인이 #19~#24로 모두 종결됨. 다음은 `/pdca archive record_detail_dialog_fix`.
