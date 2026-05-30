# excel_exporter_decomposition — Completion Report (PDCA #22)

> **Feature**: excel_exporter_decomposition
> **Author**: AI Assistant
> **Created**: 2026-05-31
> **Status**: ✅ Completed
> **Match Rate**: 98%
> **Plan**: [../../01-plan/features/excel_exporter_decomposition.plan.md](../../01-plan/features/excel_exporter_decomposition.plan.md)
> **Design**: [../../02-design/features/excel_exporter_decomposition.design.md](../../02-design/features/excel_exporter_decomposition.design.md)
> **Analysis**: [../../03-analysis/features/excel_exporter_decomposition.analysis.md](../../03-analysis/features/excel_exporter_decomposition.analysis.md)

---

## 1. 요약

코드 검토(2026-05-29) SRP 후보 중 `excel_exporter.py`(단일 클래스 4책임)를 분해.

- `ExcelWriter`(`models/excel_writer.py`): Excel 작성/서식 — openpyxl만 의존, win32com/fitz 무의존 → 단독 테스트 가능.
- `PdfScanRenderer`(`models/pdf_scan_renderer.py`): Excel→PDF 변환 + 스캔효과 — win32com/fitz/PIL/numpy.
- `ExcelExporter`(`models/excel_exporter.py`): **facade**로 축소, 두 협력자에 위임.

공개 API(위치/무인자 생성자/`export_to_excel`/`export_to_pdf`)를 비트 보존 → 호출자·모킹 무영향.

> record_view_dialog 책임 분해는 PDCA #23으로 분리(이번 비-범위).

## 2. 변경 (커밋, origin/main 반영)

| 커밋 | 내용 |
|---|---|
| `0e647bf` | ExcelWriter/PdfScanRenderer 추출 + ExcelExporter facade(위임 직전 공개속성 재동기화) |
| `c974133` | ExcelWriter 2 + PdfScanRenderer 3 단독 테스트 |

## 3. 검증
- 관련 테스트(회귀 test_excel_exporter + 모킹 dhr_bulk/manual + 신규): **27 passed**.
- 전체 스위트 **128 passed**(123→128), hang 0, stderr 노이즈 0.
- gap-detector **Match Rate 98%** (유일 Gap = 정당한 facade 재동기화 보강, 설계 반영 완료).

## 4. 성공 기준 달성 (Plan §5)
- [x] ExcelExporter 공개 API/위치/생성자 불변, 동작 동일
- [x] Excel/PDF 책임이 별도 모듈 2개로 분리, 각자 단독 테스트 가능
- [x] test_excel_exporter/모킹 테스트 회귀 0
- [x] 전체 스위트 통과(128)
- [x] Match Rate ≥ 90% (98%)

## 5. 교훈
1. **facade는 공개 속성의 사후 변경을 존중해야** — 협력자가 __init__에서 상태를 캡처하면, 호출자가 `exporter.template_file`을 사후 변경해도 반영 안 됨. 위임 직전 재동기화로 해결(test_excel_exporter:116이 이 패턴에 의존).
2. **모킹 경로 보존이 facade 분해의 핵심 제약** — `patch("models.excel_exporter.ExcelExporter")`가 다수 테스트에 박혀 있어, 분해해도 클래스 위치/이름/시그니처를 비트 보존해야 회귀 0.
3. **win32com/fitz 무의존 분리로 테스트성 향상** — Excel 작성 로직을 COM/PDF 의존 없이 단독 검증 가능해짐.

## 6. 결론
PDCA #22 완료. 271 LOC 단일 클래스를 책임별 3모듈(facade + 2협력자)로 분해, 무동작변경·회귀 0으로 SRP 개선. 다음은 `/pdca archive excel_exporter_decomposition`. 남은 SRP 후보: record_view_dialog 분해(#23).
