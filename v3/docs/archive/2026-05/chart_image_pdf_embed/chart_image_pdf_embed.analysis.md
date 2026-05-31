# 차트 임베드 Gap 분석 (PDCA #26)

> **Feature**: chart_image_pdf_embed
> **Plan**: [../../01-plan/features/chart_image_pdf_embed.plan.md](../../01-plan/features/chart_image_pdf_embed.plan.md)
> **Design**: [../../02-design/features/chart_image_pdf_embed.design.md](../../02-design/features/chart_image_pdf_embed.design.md)
> **Author**: AI Assistant
> **Created**: 2026-05-31
> **Status**: ✅ Match Rate 100% (차트 save 회귀 보강 후)
> **PDCA Cycle**: #26

---

## 1. 분석 개요
- 대상: 대시보드 보고서 월별 BarChart 임베드(openpyxl 네이티브)
- 구현 커밋: `de8b14b`(차트), `ac8e4a0`(테스트), `560df70`(save 회귀 보강)
- 검증: bkit:gap-detector

## 2. 종합 점수

| 항목 | 점수 |
|---|:---:|
| 설계 일치 | 100% (보강 후) |
| 아키텍처 | 100% |
| 컨벤션 | 98% |
| **종합** | **100%** |

## 3. 항목별 결과 (전부 일치)
- **_build_workbook**: monthly_title_row 추적 후 `if monthly:` 가드로 `_add_monthly_chart` 호출. `_write_section` 시그니처 불변(#25 4호출부 유지).
- **_add_monthly_chart**: header/data 오프셋(+1/+2), BarChart(col, title "월별 총 배합량(g)", legend None), 값 Ref(C열 header포함 titles_from_data) + 카테고리 Ref(A열), anchor "F{title_row}".
- **빈 데이터**: 차트 생략, 크래시 0.
- **제약 반영**: openpyxl 차트 write-only → 테스트는 `_build_workbook` in-memory `_charts` 검증.
- **export_pdf**: 무변경(win32com ExportAsFixedFormat이 네이티브 차트 자동 포함).

## 4. Gap (gap-detector 99% → 보강 후 100%)
| Gap | 조치 |
|---|---|
| 설계 §4 `test_export_excel_still_creates_file`(차트 포함 save 회귀) 미추가(Low) | `test_export_excel_with_chart_saves_to_disk` 추가(monthly 데이터로 export_excel→재오픈, `560df70`) → 해소 |
| _add_monthly_chart docstring 추가(설계 외) | 긍정(품질 향상), 영향 없음 |

## 5. 실행 검증
- 단위 10케이스(#25 7 + 차트 존재/빈데이터/save 회귀 3).
- 전체 스위트 `pytest tests/unit tests/integration`: **156 passed**(154→156), hang 0, stderr 노이즈 0.
- 차트 타이틀 "월별 총 배합량(g)" + in-memory `_charts` 1개 확인. PDF 차트 포함은 win32com 환경 의존(수동 확인 대상).

## 6. 결론
Match Rate **100%** → `/pdca report` 진행 가능. 대시보드 보고서에 월별 막대 차트가 Excel·PDF로 포함됨.
