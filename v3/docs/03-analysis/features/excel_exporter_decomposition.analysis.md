# ExcelExporter 책임 분해 Gap 분석 (PDCA #22)

> **Feature**: excel_exporter_decomposition
> **Plan**: [../../01-plan/features/excel_exporter_decomposition.plan.md](../../01-plan/features/excel_exporter_decomposition.plan.md)
> **Design**: [../../02-design/features/excel_exporter_decomposition.design.md](../../02-design/features/excel_exporter_decomposition.design.md)
> **Author**: AI Assistant
> **Created**: 2026-05-31
> **Status**: ✅ Match Rate 98%
> **PDCA Cycle**: #22

---

## 1. 분석 개요
- 대상: `ExcelExporter` 4책임을 `ExcelWriter`+`PdfScanRenderer`로 분해, facade 위임
- 구현 커밋: `0e647bf`(분해), `c974133`(테스트)
- 검증: bkit:gap-detector

## 2. 종합 점수

| 항목 | 점수 |
|---|:---:|
| 설계 일치 | 99% |
| 아키텍처/SRP | 100% |
| 컨벤션 | 100% |
| **종합** | **98%** |

## 3. 항목별 결과 (전부 일치)
- **ExcelWriter**(`excel_writer.py`): 생성자 `(excel_folder, template_file, cell_mapping)` + export_to_excel + 6 private 이전, 로직(`/100`, data_start_row=7, G2/228x65, 셀병합, 경계선) 보존.
- **PdfScanRenderer**(`pdf_scan_renderer.py`): 생성자 `(pdf_folder, excel_folder)` + export_to_pdf + 5 private 이전, 스캔 기본값(dpi 250/blur 0.3/noise 25/contrast 1.4/brightness 1.1)·경로 계산 보존.
- **facade**(`excel_exporter.py`): 동일 위치/무인자 생성자/시그니처 보존, 공개 속성 유지, 두 협력자 위임.
- **무동작변경**: makedirs는 facade 단일 책임(헬퍼 미생성), 로그 메시지·예외 타입 보존.
- **모킹 호환**: `patch("models.excel_exporter.ExcelExporter")` 5곳 + `patch(...config)` 유효.
- **테스트**: ExcelWriter 2 + PdfScanRenderer 3 케이스 존재(+의존성 가드).

## 4. Gap 목록
### 🔵 정보성 (설계 미명시 → 정당한 보강, 영향 없음)
| 항목 | 처리 |
|---|---|
| facade가 위임 직전 협력자 속성 재동기화(`excel_exporter.py:42-44,49-50`) | 공개 속성 사후 변경(test_excel_exporter:116) 존중용. 설계 §2.3 산문 의도를 구현한 것. **설계 코드블록에 4줄 추가 반영 완료**. |

- 누락/변경 Gap: 없음.

## 5. 실행 검증
- 관련 테스트(excel_exporter 회귀 + 모킹 dhr_bulk/manual + 신규 writer/renderer): **27 passed**.
- 전체 스위트 `pytest tests/unit tests/integration`: **128 passed**(123→128), hang 0, stderr 노이즈 0 (13.65s).

## 6. 결론
Match Rate **98%** (≥90%) → `/pdca report` 진행 가능. 즉시 조치 없음. 설계 코드블록 정합 반영 완료.
