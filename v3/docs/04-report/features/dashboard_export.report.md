# dashboard_export — Completion Report (PDCA #25)

> **Feature**: dashboard_export
> **Author**: AI Assistant
> **Created**: 2026-05-31
> **Status**: ✅ Completed
> **Match Rate**: 97%
> **Plan**: [../../01-plan/features/dashboard_export.plan.md](../../01-plan/features/dashboard_export.plan.md)
> **Design**: [../../02-design/features/dashboard_export.design.md](../../02-design/features/dashboard_export.design.md)
> **Analysis**: [../../03-analysis/features/dashboard_export.analysis.md](../../03-analysis/features/dashboard_export.analysis.md)

---

## 1. 요약

코드 검토 파생 정리(#19~#24) 완료 후 **첫 사용자 가치 기능**. #17 대시보드를 월간 보고/공유용 Excel·PDF로 내보내는 기능 추가.

- `DashboardExporter`(`models/dashboard_exporter.py`): `export_excel`(openpyxl 단일시트 4섹션, win32com 무의존), `export_pdf`(win32com 일반 변환, best-effort).
- 대시보드 기간 바에 "Excel/PDF 내보내기" 버튼 → 현재 기간으로 출력 + 결과 폴더 안내.

## 2. 변경 (커밋, origin/main 반영)

| 커밋 | 내용 |
|---|---|
| `309c0a0` | DashboardExporter(export_excel/export_pdf + _write_section/_compute_kpis/_excel_to_pdf) |
| `ac62e7c` | 대시보드 Excel/PDF 내보내기 버튼 + 핸들러 |
| `775bc09` | 단위 7 + 패널 스모크 3 테스트 |

## 3. 검증
- export_excel 단위 7케이스(생성/섹션헤더/행/빈데이터/KPI수/period_label/파일명) + 패널 스모크 3(버튼/위임/실패경고).
- 전체 스위트 **154 passed**(144→154), hang 0, stderr 노이즈 0.
- gap-detector **Match 97%**(유일 차이=버튼 클래스 표기, 설계 정정 완료).

## 4. 성공 기준 달성 (Plan §4)
- [x] export_excel 4섹션 워크북, 빈 데이터 크래시 0
- [x] 대시보드 Excel/PDF 버튼 → 파일 생성 + 폴더 안내
- [x] export_excel 단독 단위 테스트(win32com 무의존)
- [x] 전체 스위트 + 패널 스모크 통과
- [x] Match Rate ≥ 90% (97%)

## 5. 교훈
1. **테스트성을 위해 무거운 의존(win32com)을 메서드 경계로 격리** — export_excel(openpyxl)과 export_pdf(win32com)를 분리, win32com은 _excel_to_pdf 내부 지연 import → Excel 로직 단독 검증 가능.
2. **KPI 로직 중복은 동치성으로 관리** — 대시보드 _refresh_kpis와 exporter _compute_kpis가 같은 규칙(당월 매칭/len). 향후 공통화 후보지만 현재는 명시 동치 + 테스트로 안전.
3. **기존 패널 컨벤션 우선** — 설계 예시는 StyledButton이었으나 패널이 QPushButton+UIStyles를 쓰므로 그에 맞춤(일관성).
4. **win32com/os.startfile은 스모크에서 patch** — 환경 의존 호출을 mock해 UI 위임 경로만 검증.

## 6. 후속 후보
- 차트 이미지의 PDF 임베드(현재는 표/수치 중심).
- 레시피 빈도 섹션 추가.
- _compute_kpis 공통화(대시보드 패널 ↔ exporter).

## 7. 결론
PDCA #25 완료. 대시보드 데이터를 파일로 내보내는 사용자 가치 기능을 무회귀로 추가. 다음은 `/pdca archive dashboard_export`.
