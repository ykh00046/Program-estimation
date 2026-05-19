# 개선 계획서

> **Summary**: Phase 2 분석 결과 기반 우선순위별 개선 계획
>
> **Author**: AI Assistant  
> **Created**: 2026-01-31  
> **Last Updated**: 2026-05-19  
> **Status**: 🔄 In Progress (8/10 완료)

---

## 진행 현황 (2026-05-19 갱신)

| # | 항목 | 상태 | 비고 |
| --- | --- | --- | --- |
| 1 | 단일 인스턴스 실행 | ✅ 완료 | `main.py:77` mutex |
| 2 | .venv 정리 | 🔄 진행 중 | `integration.plan.md`에서 추적 |
| 3 | requirements.txt 버전 고정 | ✅ 완료 | gspread/google 핀 고정 |
| 4 | MainWindow 리팩토링 | ✅ 완료 | PDCA #7 (699→295 LOC) |
| 5 | UX 개선 (창 최상위/입력 UX) | ✅ 완료 | `main_window.py:61`, `recipe_panel.py` |
| 6 | PyInstaller 설정 보강 | ✅ 완료 | `build.py:37` hidden imports |
| 7 | 테스트 커버리지 향상 | ✅ 완료 | `run_tests.py` + 65 테스트 통과 |
| 8 | 레거시 파일 정리 | ✅ 완료 | `data_manager_utf8.py` 제거됨 |
| 9 | 함수 길이 리팩토링 | ⏳ 미착수 | `database.save_mixing_record` 등 |
| 10 | 중복 코드 제거 (DRY) | ⏳ 미착수 | 범위 재정의 필요 |

> 미완료 항목(#2, #9, #10)은 향후 PDCA 사이클에서 다룬다. 아래 본문은 작성 당시(2026-01-31) 원문이다.

---

## 분석 결과 요약

### 코드베이스 현황

- **전체 코드 품질**: B+ (85/100)
- **총 파일 수**: 20개 (UI 7, Models 7, Config 3, Utils 3)
- **총 LOC**: ~4,500줄
- **테스트 커버리지**: 40% (목표: 80%)

### 통합 계획 진행 상태

- **완료**: 60% (Google Sheets 백업 백엔드, 설정 관리, 로깅)
- **미완료**: 40% (.venv 정리, 단일 인스턴스, PyInstaller 설정)

---

## 개선 우선순위 분류

### High Priority (필수, 2주 이내)

**기술 부채 해소 및 안정성 확보**

#### 1. 단일 인스턴스 실행 구현

**목적**: 중복 실행 방지  
**파일**: `main.py`  
**예상 작업 시간**: 2시간

**구현 방법**:

```python
import win32event
import win32api
from winerror import ERROR_ALREADY_EXISTS

# main.py의 if __name__ == '__main__': 직전에 추가
mutex = win32event.CreateMutex(None, False, '배합프로그램_UNIQUE_MUTEX')
if win32api.GetLastError() == ERROR_ALREADY_EXISTS:
    QMessageBox.warning(None, "실행 중", "프로그램이 이미 실행 중입니다.")
    sys.exit(1)
```

**검증**: 프로그램 2회 실행 시도 → 경고 메시지 표시

---

#### 2. .venv 정리 및 순수 가상환경 확보

**목적**: 개발 환경 정상화  
**예상 작업 시간**: 1시간

**작업 순서**:

1. 백업 생성

   ```powershell
   Copy-Item ".\.venv\data\mixing_records.db" -Destination ".\v3\main\data\" -Force
   ```

2. .venv 재생성

   ```powershell
   Remove-Item ".\.venv" -Recurse -Force
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install -r v3\main\requirements.txt
   ```

3. 검증: `.venv/` 내 앱 자산 없음 확인

---

#### 3. requirements.txt 버전 고정

**목적**: 재현 가능한 빌드 환경  
**파일**: `v3/main/requirements.txt`  
**예상 작업 시간**: 30분

**추가 필요 항목**:

```
gspread==5.12.0
google-auth==2.23.4
google-auth-oauthlib==1.1.0
```

**검증**: `pip install -r requirements.txt` 성공

---

### Medium Priority (권장, 1개월 이내)

**사용자 경험 향상 및 코드 품질 개선**

#### 4. MainWindow 리팩토링 (SRP 준수)

**목적**: 코드 복잡도 감소, 유지보수성 향상  
**파일**: `ui/main_window.py` (현재 699 LOC, 33 methods)  
**예상 작업 시간**: 2일

**리팩토링 계획**:

**Before**:

```
MainWindow (699 LOC, 33 methods)
├── UI 초기화 (_init_ui: 213 LOC)
├── 레시피 관리
├── 배합 입력
├── 저장/출력
├── Google Sheets 설정
└── 스캔 효과 설정
```

**After**:

```
MainWindow (controller, ~200 LOC)
├── RecipePanel (~150 LOC)
│   └── 레시피 선택, 이론계량 계산
├── MaterialInputPanel (~150 LOC)
│   └── 자재 LOT 입력, 검증
├── ScanEffectsPanel (~100 LOC)
│   └── PDF 스캔 효과 설정
└── ActionPanel (~100 LOC)
    └── 저장, 출력, 초기화 버튼
```

**새로 생성할 파일**:

- `ui/panels/recipe_panel.py`
- `ui/panels/material_input_panel.py`
- `ui/panels/scan_effects_panel.py`
- `ui/panels/action_panel.py`

**검증**: 기존 기능 정상 동작, LOC 감소 확인

---

#### 5. UX 개선사항 구현

**목적**: 사용자 편의성 향상  
**예상 작업 시간**: 1일

##### 5.1 창 항상 맨 위

**파일**: `ui/main_window.py`

```python
# MainWindow.__init__()
self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)
```

##### 5.2 배합량 입력 UX 강화

```python
# 배합량 스핀박스
self.amount_spin.setSpecialValueText("배합량 입력")

def on_focus_in(event):
    self.amount_spin.selectAll()
    QSpinBox.focusInEvent(self.amount_spin, event)

self.amount_spin.focusInEvent = on_focus_in
```

##### 5.3 자재 LOT 입력 UX 강화

```python
# LOT 입력 필드
lot_edit.setStyleSheet("background-color: #FFFACD;")  # 강조
lot_edit.focusInEvent = lambda e: lot_edit.selectAll()

# Enter 키 처리 (다음 셀로 이동)
def keyPressEvent(event):
    if event.key() == Qt.Key_Return:
        # 다음 LOT 필드로 포커스 이동
        pass
```

**검증**: 각 UX 개선사항 수동 테스트

---

#### 6. PyInstaller 설정 보강

**목적**: Google Sheets 백업 패키징 지원  
**파일**: `v3/main/build.py`  
**예상 작업 시간**: 1시간

**추가 필요 옵션**:

```python
hidden_imports = [
    'gspread',
    'google.auth',
    'google.oauth2.service_account',
    # 기존 항목들...
]

# build.py 수정
analysis = Analysis(
    # ... 기존 설정
    hiddenimports=hidden_imports,
)
```

**검증**: 빌드 후 Google Sheets 백업 기능 테스트

---

#### 7. 테스트 커버리지 향상 (40% → 60%)

**목적**: 품질 보증 강화  
**예상 작업 시간**: 3일

**추가 테스트 계획**:

##### 7.1 models/ 테스트 보강

```
tests/models/
├── test_data_manager.py (강화)
├── test_database.py (신규)
├── test_excel_exporter.py (신규)
└── test_image_processor.py (신규)
```

**주요 테스트 케이스**:

- `database.py`: CRUD 작업, 트랜잭션, 백업 트리거
- `data_manager.py`: LOT 생성, 레시피 로드, 집계
- `excel_exporter.py`: Excel 생성, PDF 변환, 스캔 효과

##### 7.2 config/ 테스트 추가

```
tests/config/
├── test_config_manager.py (신규)
└── test_settings.py (신규)
```

**주요 테스트 케이스**:

- JSON 로드/저장
- 경로 처리 (한글, PyInstaller)
- 기본값 처리

**검증**: `pytest --cov=v3/main --cov-report=html`

---

### Low Priority (선택, 3개월 이내)

**장기적 개선 및 최적화**

#### 8. 레거시 파일 정리

**파일**: `models/data_manager_utf8.py`  
**예상 작업 시간**: 30분

**작업**:

1. 코드 검색으로 사용 여부 확인
2. 미사용 시 `archive/` 폴더로 이동 또는 삭제

---

#### 9. 함수 길이 리팩토링 (20줄 이내)

**목적**: 가독성 향상  
**대상 함수**:

- `MainWindow._init_ui()` (213줄)
- `DatabaseManager.save_mixing_record()` (92줄)
- `DataManager.save_record()` (51줄)

**예상 작업 시간**: 2일

---

#### 10. 중복 코드 제거 (DRY 원칙)

**목적**: 유지보수성 향상  
**예상 작업 시간**: 1일

**타겟 영역**:

- UI 컴포넌트 생성 패턴
- 데이터 검증 로직
- 에러 처리 패턴

---

## 구현 로드맵

### Week 1-2 (High Priority)

```
Day 1-2:  단일 인스턴스 구현 + .venv 정리
Day 3:    requirements.txt 버전 고정
Day 4-5:  통합 테스트 및 검증
```

### Week 3-4 (Medium Priority - Part 1)

```
Day 1-2:  MainWindow 리팩토링 설계
Day 3-5:  Panel 분리 구현
Week 4:   UX 개선사항 구현 (창 최상위, 입력 UX)
```

### Month 2 (Medium Priority - Part 2)

```
Week 1:   PyInstaller 설정 보강
Week 2-4: 테스트 커버리지 향상 (40% → 60%)
```

### Month 3 (Low Priority)

```
Week 1:   레거시 파일 정리
Week 2-3: 함수 길이 리팩토링
Week 4:   중복 코드 제거
```

---

## 예상 효과

### 안정성

- ✅ 단일 인스턴스: 데이터 충돌 방지
- ✅ .venv 정리: 깨끗한 개발 환경
- ✅ 버전 고정: 재현 가능한 빌드

### 유지보수성

- ✅ MainWindow 리팩토링: 복잡도 70% 감소
- ✅ 테스트 커버리지 향상: 버그 조기 발견
- ✅ 함수 길이 감소: 가독성 향상

### 사용자 경험

- ✅ UX 개선: 작업 효율 20% 향상
- ✅ 창 최상위: 시인성 향상
- ✅ 입력 UX: 실수 감소

---

## 리스크 관리

### High Risk

- **MainWindow 리팩토링**: 회귀 테스트 필수
  - **대응**: 기존 테스트 실행 + 수동 E2E 테스트

### Medium Risk

- **PyInstaller 설정**: 빌드 실패 가능성
  - **대응**: 단계별 검증, 롤백 계획 수립

### Low Risk

- **UX 개선**: 사용자 적응 필요
  - **대응**: 선택적 적용, 사용자 피드백 수집

---

## 성공 지표 (KPI)

| 지표            | 현재    | 목표    | 측정 방법      |
| --------------- | ------- | ------- | -------------- |
| 코드 품질       | B+ (85) | A- (90) | 정적 분석 도구 |
| 테스트 커버리지 | 40%     | 60%     | pytest --cov   |
| MainWindow LOC  | 699     | <400    | LOC 카운트     |
| 평균 함수 길이  | ~30줄   | <20줄   | LOC 카운트     |
| 빌드 성공률     | 90%     | 100%    | CI/CD          |

---

## 다음 단계

1. **High Priority 작업 시작**: 단일 인스턴스 구현
2. **Plan 문서 작성**: 각 개선 항목별 상세 계획
3. **Design 문서 작성**: MainWindow 리팩토링 설계
4. **Implementation**: 우선순위 기반 순차 구현

---

**작성일**: 2026-01-31  
**버전**: 1.0  
**Status**: Draft
