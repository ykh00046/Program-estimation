# chart_image_pdf_embed — Completion Report (PDCA #26)

> **Feature**: chart_image_pdf_embed
> **Author**: AI Assistant
> **Created**: 2026-05-31
> **Status**: ✅ Completed
> **Match Rate**: 100%
> **Plan**: [../../01-plan/features/chart_image_pdf_embed.plan.md](../../01-plan/features/chart_image_pdf_embed.plan.md)
> **Design**: [../../02-design/features/chart_image_pdf_embed.design.md](../../02-design/features/chart_image_pdf_embed.design.md)
> **Analysis**: [../../03-analysis/features/chart_image_pdf_embed.analysis.md](../../03-analysis/features/chart_image_pdf_embed.analysis.md)

---

## 1. 요약

PDCA #25 대시보드 보고서(표/수치 중심)에 **월별 생산량 막대 차트**를 추가. 기능명은 "image embed"였으나, 구현은 더 우수한 **openpyxl 네이티브 `BarChart`**(벡터, Qt/이미지/신규의존 없음)를 채택해 Excel·PDF 양쪽에 차트가 렌더된다.

## 2. 변경 (커밋, origin/main 반영)

| 커밋 | 내용 |
|---|---|
| `de8b14b` | `_add_monthly_chart` — 월별 섹션 데이터(C열 값/A열 카테고리) 참조 BarChart, anchor F열, 빈데이터 생략 |
| `ac8e4a0` | 차트 존재(+타이틀)/빈데이터 미생성 테스트 |
| `560df70` | 차트 포함 save 회귀 테스트(직렬화 경로) |

## 3. 검증
- 단위 10케이스(#25 7 + 차트 3) 통과.
- 전체 스위트 **156 passed**(154→156), hang 0, stderr 노이즈 0.
- gap-detector **Match 99%→보강 후 100%**.

## 4. 성공 기준 달성 (Plan §4)
- [x] export_excel 워크북에 월별 BarChart 1개(데이터 있을 때)
- [x] 데이터 0행 시 차트 생략·크래시 0
- [x] win32com PDF 변환 시 차트 포함(네이티브 차트 → ExportAsFixedFormat 자동 반영)
- [x] 전체 스위트 통과
- [x] Match Rate ≥ 90% (100%)

## 5. 교훈
1. **"이미지 임베드" 요구 ≠ 래스터화** — openpyxl 네이티브 차트가 Qt 래스터화보다 우수(벡터, 무의존, 테스트 가능, PDF 자동 포함). 요구의 의도(보고서에 차트)를 더 나은 수단으로 충족.
2. **openpyxl 차트는 write-only** — `load_workbook`이 차트를 재읽지 않으므로, 테스트는 `_build_workbook` in-memory `_charts`로 검증. 더해 차트 포함 워크북의 디스크 save/재오픈 무오류로 직렬화 경로를 별도 보증.
3. **최소 결합 추가** — `_write_section` 시그니처를 건드리지 않고 `title_row`만 추적해 차트를 얹어 #25 회귀 위험 0.

## 6. 후속 후보
- 자재 TOP/작업자 섹션 차트.
- 차트 색/스타일을 UITheme 앰버에 맞춤.
- 자재 재고 임계값 알림(사용자 가치).

## 7. 결론
PDCA #26 완료. 대시보드 보고서가 차트까지 포함하는 완성도 높은 산출물이 됨. 다음은 `/pdca archive chart_image_pdf_embed`.
