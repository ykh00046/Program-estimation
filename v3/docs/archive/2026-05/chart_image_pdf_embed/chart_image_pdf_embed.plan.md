# 대시보드 보고서 차트 임베드 (PDCA #26)

> **Feature**: chart_image_pdf_embed
> **Author**: AI Assistant
> **Created**: 2026-05-31
> **Status**: ✅ Plan
> **PDCA Cycle**: #26 (#25 후속 — 사용자 가치)

---

## 1. 배경

PDCA #25에서 대시보드 Excel/PDF 보고서를 추가했으나 **표/수치 중심**이고 차트가 없다(#25 비-범위). 월별 생산량을 한눈에 보려면 차트가 유용하다.

### 구현 방식 결정 — openpyxl 네이티브 차트 (이미지 래스터화보다 우수)

후보:
- **(A) openpyxl 네이티브 `BarChart`** — 월별 데이터 셀을 참조하는 실제 Excel 차트 객체. **Qt/이미지 무관, 신규 의존 없음, 단독 테스트 가능, win32com PDF 변환 시 차트 포함**. ✅ 채택
- (B) QtCharts QChart를 PNG로 래스터화해 이미지 삽입 — 대시보드 외관과 동일하나 exporter가 Qt/QtCharts에 결합, 오프스크린 렌더 필요, 테스트 어려움. 기각.

> 기능명은 명령에 맞춰 `chart_image_pdf_embed`로 유지하나, 실제 구현은 **네이티브 Excel 차트**(이미지 파일이 아닌 벡터 차트)로, Excel·PDF 양쪽에서 렌더된다. 대시보드 정확한 외관 재현(B)이 꼭 필요하면 design 단계에서 재검토.

## 2. 범위 (In Scope)

### Part A — DashboardExporter에 월별 차트 추가
- `_build_workbook`에서 "[월별 생산량]" 섹션 데이터 기록 후, 해당 데이터 셀 범위를 참조하는 `openpyxl.chart.BarChart`를 시트에 추가.
- 차트: 카테고리=연월, 값=총배합량(g), 제목 "월별 총 배합량". 데이터 0행이면 차트 생략(빈 참조 방지).
- 차트 anchor는 표 우측 또는 하단 빈 영역(겹침 방지).
- `_write_section`이 월별 섹션의 데이터 시작/끝 행을 알 수 있도록 반환값 활용(또는 헬퍼 분리).

### Part B — 테스트
- `export_excel` 결과 워크북에 차트 객체가 1개 존재(`ws._charts`) 검증.
- 데이터 0행이면 차트 미생성 검증(크래시 0).
- 기존 #25 테스트 회귀(섹션/행/빈데이터) 유지.

## 3. 비-범위 (Out of Scope)
- QtCharts 외관(앰버 막대/다크 배경) 픽셀 재현(B안).
- 자재 TOP/작업자 섹션 차트(1차는 월별 1종).
- 차트 색/스타일 정교화(기본 스타일 사용, 후속).

## 4. 성공 기준
- [ ] export_excel 워크북에 월별 BarChart 1개 포함(데이터 있을 때)
- [ ] 데이터 0행 시 차트 생략·크래시 0
- [ ] win32com PDF 변환 시 차트 포함(수동/스모크 확인)
- [ ] 전체 스위트 통과(현 154 + 신규)
- [ ] Match Rate ≥ 90%

## 5. 위험 & 완화
| 위험 | 완화 |
|---|---|
| 차트 데이터 참조 셀 범위 오류 | _write_section이 기록한 행 범위를 정확히 추적(데이터 시작행/개수) |
| 빈 데이터에서 Reference 오류 | 0행이면 차트 생성 스킵 |
| 차트가 표와 겹침 | anchor를 데이터 우측 열(예: F열) 또는 충분히 아래 |
| 네이티브 차트가 PDF에 안 나옴 | ExportAsFixedFormat은 차트 포함 — 스모크/수동 확인 |

## 6. 커밋 계획
1. `feat(models): embed monthly BarChart in dashboard report (PDCA #26)`
2. `test: dashboard report chart presence/empty-safe (PDCA #26)`
3. `docs: PDCA #26 analysis + report`

## 7. 다음 단계
`/pdca design chart_image_pdf_embed` → 차트 셀 참조/anchor/시그니처 확정 → `/pdca do`.
