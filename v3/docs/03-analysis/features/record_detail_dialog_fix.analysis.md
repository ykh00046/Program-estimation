# RecordDetailDialog 복구 Gap 분석 (PDCA #24)

> **Feature**: record_detail_dialog_fix
> **Plan**: [../../01-plan/features/record_detail_dialog_fix.plan.md](../../01-plan/features/record_detail_dialog_fix.plan.md)
> **Design**: [../../02-design/features/record_detail_dialog_fix.design.md](../../02-design/features/record_detail_dialog_fix.design.md)
> **Author**: AI Assistant
> **Created**: 2026-05-31
> **Status**: ✅ Match Rate 100% (테스트 보강 후)
> **PDCA Cycle**: #24

---

## 1. 분석 개요
- 대상: 크래시하던 RecordDetailDialog를 본래 상세 위젯으로 복구
- 구현 커밋: `84fa8dc`(수정), `d57c21e`(스모크), `0642e56`(버튼 variant 검증 보강)
- 검증: bkit:gap-detector

## 2. 종합 점수

| 항목 | 점수 |
|---|:---:|
| 설계 일치 | 100% (보강 후) |
| 구조/배선 정합 | 100% |
| 테스트 일치 | 100% (보강 후) |
| **종합** | **100%** |

## 3. 항목별 결과 (전부 일치)
- **§2.1** `__init__`에 `self.edit_mode=False` 초기화.
- **§2.2** `init_ui`가 `_build_info_group + _build_detail_group + _build_button_bar` 호출로 재배선.
- **§2.3** RecordDetailDialog에서 복사 잔재(_build_filter_group/_build_records_table/_build_aggregation_group/중복 _build_button_bar) 삭제, `_build_button_bar` 단일(수정/저장/실적서/닫기).
- **§3** RecordViewDialog(목록)는 자체 메서드·load_records 보존, 무변경.
- **§2.3 정합** self.table=자재상세 6열 → `_collect_material_updates_from_rows` 인덱스(0/2/3/4/5) 정합.
- **§4** 테스트 5케이스(생성/테이블헤더/단일정의/토글/버튼 variant).

## 4. Gap (gap-detector 1차 95% → 보강 후 100%)
| Gap | 조치 |
|---|---|
| 단일 버튼바 테스트가 정적 정의수 검증(설계는 런타임 variant) | `test_button_bar_is_detail_variant` 추가(수정/저장/실적서/닫기 존재 + 전체선택/삭제 부재, `0642e56`) → 해소 |

## 5. 실행 검증
- before: `RecordDetailDialog(...)` → `AttributeError: 'RecordDetailDialog' object has no attribute 'load_records'` (크래시 재현).
- after: 정상 생성 + 자재상세 테이블 + 수정모드 토글 동작 + 단일 상세 버튼바.
- 전체 스위트 `pytest tests/unit tests/integration`: **143 passed**(이후 detail 스모크 +1=144 케이스), hang 0, stderr 노이즈 0.

## 6. 결론
Match Rate **100%** → `/pdca report` 진행 가능. 깨져 있던 상세조회가 복구됨.
