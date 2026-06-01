# PDCA #27 완료 보고서 — 자재 재고 임계값 알림

> feature: `inventory_threshold_alert` · 완료일: 2026-06-01 · Level: Starter
> 결과: ✅ 완료 (Match ~98%, 테스트 201 passed, 요구사항 5/5 충족)

## 1. 요약

대시보드에 **자재 재고 부족 알림** 기능을 추가했다. 사용자가 자재별 **현재 재고**와
**최소 임계값**(및 전역 기본 임계값)을 설정하면, 현재 재고가 임계값 이하인 자재를
대시보드 상단 알림 카드로 능동 경고한다. 입고/발주 플로우 없이 수동 입력 기반의
경량 재고 모델로 5개 요구사항을 모두 충족했다.

## 2. PDCA 사이클 기록

| 단계 | 산출물 | 결과 |
|---|---|---|
| **Plan** | `01-plan/features/inventory_threshold_alert.plan.md` | "재고 의미론" 재정렬(사용량 상한→재고 모델) |
| **Design** | `02-design/features/inventory_threshold_alert.design.md` | 4계층 분리, 기존 `material_stock` 자산 재사용 |
| **Do** | 구현 6파일 + 다이얼로그 + 테스트 4파일 | 누락 위임 3종 보완으로 실행 가능화 |
| **Check** | `03-analysis/inventory_threshold_alert.analysis.md` | gap-detector Match 94% |
| **Iterate** | parity 보강 + 설계 문서 정렬 | Match ~98%, 데드 코드/판정 불일치 제거 |
| **QA** | 전체 테스트 + 무목 E2E 스모크 | 201 passed, SQL·순수 경로 일치 |
| **Report** | 본 문서 | 완료 |

## 3. 구현 변경 내역

### 신규 파일
- `models/inventory_alert.py` — 순수 평가 로직 `evaluate_inventory_alerts(rows, default_threshold)`,
  `MaterialAlert` NamedTuple, `LEVEL_OUT`/`LEVEL_LOW`.
- `ui/dialogs/stock_settings_dialog.py` — `StockSettingsDialog`(자재별 현재고/임계값 +
  전역 기본 임계값 편집·저장, 이력 재시드).
- 테스트 4개: `tests/unit/test_inventory_alert.py`(순수 평가 10), `tests/unit/test_material_stock_db.py`(DB CRUD 8),
  `tests/unit/test_material_stock.py`(위임·임계값 9), `tests/integration/test_stock_alert_dashboard.py`(패널·다이얼로그 스모크 5).

### 수정 파일
- `models/database.py` — `material_stock` 테이블 + `get_all_material_stock` /
  `get_low_stock_materials` / `upsert_material_stock` / `seed_material_stock_from_history`.
- `models/data_manager.py` — 위임 래퍼 + `get_default_min_threshold` /
  `set_default_min_threshold` / `get_low_stock_materials` / `get_inventory_alerts`(parity).
- `config/config_manager.py` — `set_value(dotted_key, value)` 점표기 저장 헬퍼.
- `ui/panels/dashboard_panel.py` — 재고 부족 알림 섹션/카드 + "재고 설정" 버튼 +
  `_refresh_low_stock_alerts()`(refresh 연동).

## 4. 요구사항 충족

| # | 요구사항 | 충족 |
|---|---|:--:|
| 1 | 자재별 `min_stock_threshold` 설정 | ✅ |
| 2 | 임계값 이하 자재 대시보드 알림 카드 | ✅ |
| 3 | 임계값 설정에서 변경 | ✅ |
| 4 | 카드에 자재명/현재고/임계값/부족분 | ✅ |
| 5 | 기존 대시보드 UI 스타일 유지 | ✅ |

## 5. 품질 지표
- 테스트: **201 passed / 0 failed**(기존 198 회귀 0 + 신규 3 스위트).
- 설계 일치: ~98%.
- 컨벤션: Python 3.9 호환, 타입힌트, UTF-8, `UITheme`/`UIStyles` SSOT 준수.
- 안전성: 입력 결측/음수/비숫자 방어, 신규 테이블 `IF NOT EXISTS`(기존 DB 무영향),
  offscreen 다이얼로그 가드 + QMessageBox patch.

## 6. 교훈 (Lessons)
1. **단어 트랩 재확인**: "재고 임계값"을 사용량 상한으로 재해석한 초기 Plan보다,
   사용자가 명시한 요구사항(현재고/부족분)을 따른 수동 재고 모델이 정답이었다.
   사용자 명시 요구 > 추정 재해석.
2. **이중 평가 경로의 위험**: SQL 경로와 순수 함수 경로가 병존할 때 판정 규칙이
   어긋나면 한쪽이 데드 코드가 된다. **parity 테스트**로 두 경로의 등가성을 강제하는 것이
   효과적이었다.
3. **순수 변환부 분리 효과**: Qt·DB 무의존 `evaluate_inventory_alerts` 덕분에 경계값을
   빠르고 견고하게 단위 테스트할 수 있었다(기존 대시보드 #17 교훈 재확인).
4. **기존 자산 재사용**: 신규 `material_inventory` 테이블 대신 이미 존재하던
   `material_stock`을 SSOT로 채택해 중복 스키마 안티패턴을 회피(PDCA #18 교훈).

## 7. 후속 후보 (선택)
- `get_input_field_style` 등 누락 스타일 토큰 보강(현재 try/except 안전 처리).
- 임계값/재고 변경 이력(감사 로그) — 필요 시 신규 사이클.
- 입고/발주/사용량 연동 자동 차감 — 본 사이클 비-범위.

→ 상태: **completed**. 필요 시 `/pdca archive inventory_threshold_alert`로 문서 아카이브.
