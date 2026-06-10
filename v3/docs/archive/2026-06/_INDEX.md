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

## 핵심 성과

- **자재 재고 임계값 알림 (#27)**: `material_stock` 테이블 + 재고 설정 다이얼로그 + 대시보드 재고 부족 알림 카드. 임계값 이하 자재를 KPI 상단에 경고 표시. 전체 스위트 201 passed (Match 100%). 첫 사용자 가치 기능(#25 dashboard_export) 라인의 후속.
- **UI 스레드 분리 (#33)**: `ui/workers.py` FunctionWorker(QThread) 인프라 신설, Sheets 백업/Excel COM PDF 등 5경로 백그라운드화. 저장/출력 중 UI 멈춤 해소. 295 passed (+19), 커밋 b128d92.
- **재고 정합성 검사·보정 (#34)**: 장부 체인 검사(현재고 vs stock_after) + 재고 불변 장부 정렬 + LOT 마커 기반 미차감 검출/소급 차감. 수동 편집 ADJUST 이력화(log_history opt-in). 321 passed (+26), 커밋 f6c2dcc.
- **아카이브 날짜**: 2026-06-01 (#27), 2026-06-10 (#33, #34)
