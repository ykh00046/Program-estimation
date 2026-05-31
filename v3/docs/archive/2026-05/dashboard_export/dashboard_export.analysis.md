# 대시보드 출력 Gap 분석 (PDCA #25)

> **Feature**: dashboard_export
> **Plan**: [../../01-plan/features/dashboard_export.plan.md](../../01-plan/features/dashboard_export.plan.md)
> **Design**: [../../02-design/features/dashboard_export.design.md](../../02-design/features/dashboard_export.design.md)
> **Author**: AI Assistant
> **Created**: 2026-05-31
> **Status**: ✅ Match Rate 97%
> **PDCA Cycle**: #25

---

## 1. 분석 개요
- 대상: DashboardExporter(excel/pdf) + 대시보드 내보내기 UI
- 구현 커밋: `309c0a0`(exporter), `ac62e7c`(UI), `775bc09`(테스트)
- 검증: bkit:gap-detector

## 2. 종합 점수

| 항목 | 점수 |
|---|:---:|
| 설계 일치 | 97% |
| 아키텍처(집계 위임/계층) | 100% |
| 컨벤션 | 100% |
| **종합** | **97%** |

## 3. 항목별 결과 (전부 일치)
- **DashboardExporter**: export_excel(start,end,filename)/export_pdf 시그니처, 생성자(data_manager, output_folder=None→config), _write_section/_compute_kpis/_period_label/_excel_to_pdf. export_excel은 openpyxl만 의존(win32com은 _excel_to_pdf 내부 지연 import).
- **워크시트**: 제목+기간행 + 4섹션(요약/월별/자재TOP/작업자) 머리글·헤더(테두리/굵게)·원시숫자, 빈데이터 "기록 없음".
- **경로/파일명**: config paths.output/dashboard, `대시보드_{전체|start_end}.xlsx`.
- **UI**: __init__ self._exporter, period bar Excel/PDF 버튼, _export_excel/_export_pdf/_notify_export(성공 폴더열기/실패 경고).
- **KPI**: _compute_kpis가 대시보드 _refresh_kpis(당월 매칭/worker len/recipe len)와 동치.
- **테스트**: 단위 7종(설계 5 + KPI수/파일명 보강) + 패널 스모크 3종.

## 4. Gap (gap-detector 97%)
| Gap | 처리 |
|---|---|
| 설계 §4.1 버튼 예시 `StyledButton` vs 구현 `QPushButton+UIStyles`(기존 패널 컨벤션) | 표기 차이, 동작 동일. **설계를 구현에 맞춰 정정**(Code is truth) 완료 |
| 단위 테스트 5→7 (KPI len/파일명 보강) | 설계 §6 위험을 테스트로 강화(긍정) |

- 누락/실질 변경 Gap: 없음.

## 5. 실행 검증
- export_excel 단위 7 + 패널 스모크 3 + 기존 dashboard 테스트 통과(20).
- 전체 스위트 `pytest tests/unit tests/integration`: **154 passed**(144→154), hang 0, stderr 노이즈 0.

## 6. 결론
Match Rate **97%** (≥90%) → `/pdca report` 진행 가능. 대시보드에 월간 보고/공유용 Excel·PDF 출력이 추가됨.
