# 2026-06 Archive Index

> 2026년 6월 아카이브 문서 목록

## PDCA #27 (Inventory Threshold Alert — 자재 재고 임계값 알림)

| 문서 | 원래 위치 | 단계 |
| --- | --- | --- |
| [inventory_threshold_alert.plan.md](./inventory_threshold_alert/inventory_threshold_alert.plan.md) | 01-plan/features/ | Plan |
| [inventory_threshold_alert.design.md](./inventory_threshold_alert/inventory_threshold_alert.design.md) | 02-design/features/ | Design |
| [inventory_threshold_alert.analysis.md](./inventory_threshold_alert/inventory_threshold_alert.analysis.md) | 03-analysis/features/ | Analysis (Match Rate **100%**) |
| [inventory_threshold_alert.report.md](./inventory_threshold_alert/inventory_threshold_alert.report.md) | 04-report/features/ | Report |

## PDCA #33 (Async Worker Offload — UI 스레드 분리)

| 문서 | 원래 위치 | 단계 |
| --- | --- | --- |
| [async_worker_offload.plan.md](./async_worker_offload/async_worker_offload.plan.md) | docs/01-plan/features/ (루트) | Plan |
| [async_worker_offload.design.md](./async_worker_offload/async_worker_offload.design.md) | docs/02-design/features/ (루트) | Design |
| [async_worker_offload.analysis.md](./async_worker_offload/async_worker_offload.analysis.md) | docs/03-analysis/ (루트) | Analysis (Match 89% → Act → **~99%**) |
| [async_worker_offload.report.md](./async_worker_offload/async_worker_offload.report.md) | docs/04-report/ (루트) | Report |

## PDCA #34 (Inventory Reconcile — 재고 정합성 검사·보정)

| 문서 | 원래 위치 | 단계 |
| --- | --- | --- |
| [inventory_reconcile.plan.md](./inventory_reconcile/inventory_reconcile.plan.md) | docs/01-plan/features/ (루트) | Plan |
| [inventory_reconcile.design.md](./inventory_reconcile/inventory_reconcile.design.md) | docs/02-design/features/ (루트) | Design |
| [inventory_reconcile.analysis.md](./inventory_reconcile/inventory_reconcile.analysis.md) | docs/03-analysis/ (루트) | Analysis (Match **~99.5%** 1차 통과) |
| [inventory_reconcile.report.md](./inventory_reconcile/inventory_reconcile.report.md) | docs/04-report/ (루트) | Report |

## PDCA #35 (Backup Hardening — Google Sheets 백업 견고화)

| 문서 | 원래 위치 | 단계 |
| --- | --- | --- |
| [backup_hardening.plan.md](./backup_hardening/backup_hardening.plan.md) | docs/01-plan/features/ (루트) | Plan |
| [backup_hardening.design.md](./backup_hardening/backup_hardening.design.md) | docs/02-design/features/ (루트) | Design |
| [backup_hardening.analysis.md](./backup_hardening/backup_hardening.analysis.md) | docs/03-analysis/ (루트) | Analysis (Match **100%** 1차 통과) |
| [backup_hardening.report.md](./backup_hardening/backup_hardening.report.md) | docs/04-report/ (루트) | Report |

## PDCA #36 (DHR Export Async — 수기입력·대량생성 출력 비동기화)

| 문서 | 원래 위치 | 단계 |
| --- | --- | --- |
| [dhr_export_async.plan.md](./dhr_export_async/dhr_export_async.plan.md) | docs/01-plan/features/ (루트) | Plan |
| [dhr_export_async.design.md](./dhr_export_async/dhr_export_async.design.md) | docs/02-design/features/ (루트) | Design |
| [dhr_export_async.analysis.md](./dhr_export_async/dhr_export_async.analysis.md) | docs/03-analysis/ (루트) | Analysis (Match **99%** 1차 통과) |
| [dhr_export_async.report.md](./dhr_export_async/dhr_export_async.report.md) | docs/04-report/ (루트) | Report |

## 핵심 성과

- **자재 재고 임계값 알림 (#27)**: `material_stock` 테이블 + 재고 설정 다이얼로그 + 대시보드 재고 부족 알림 카드. 임계값 이하 자재를 KPI 상단에 경고 표시. 전체 스위트 201 passed (Match 100%). 첫 사용자 가치 기능(#25 dashboard_export) 라인의 후속.
- **UI 스레드 분리 (#33)**: `ui/workers.py` FunctionWorker(QThread) 인프라 신설, Sheets 백업/Excel COM PDF 등 5경로 백그라운드화. 저장/출력 중 UI 멈춤 해소. 295 passed (+19), 커밋 b128d92.
- **재고 정합성 검사·보정 (#34)**: 장부 체인 검사(현재고 vs stock_after) + 재고 불변 장부 정렬 + LOT 마커 기반 미차감 검출/소급 차감. 수동 편집 ADJUST 이력화(log_history opt-in). 321 passed (+26), 커밋 f6c2dcc.
- **백업 견고화 (#35)**: JSONL 재시도 큐 + 헤더 관용 매핑(시트가 진실) + BACKUP_COLUMNS SSOT. 백업 실패가 데이터 누락으로 이어지지 않음. 341 passed (+20), 커밋 b68bd08. **2026-06-10 전체 검토 High 3건(#33/#34/#35) 전부 종결.**
- **DHR 출력 비동기화 (#36)**: 수기 입력(출력만)·일괄 생성(전체)을 워커로 — #33 잔여 종결, **UI 스레드를 막는 무거운 작업 경로 0 달성**. 346 passed (+5), 커밋 60e2ed7.
- **아카이브 날짜**: 2026-06-01 (#27), 2026-06-10 (#33, #34, #35, #36)
