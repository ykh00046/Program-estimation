# CLAUDE.md

> AI 협업을 위한 프로젝트 설정 파일

---

## Project Information

- **Project Name**: 배합 프로그램 v3 (Manufacturing Batch Recipe Management System)
- **Project Level**: **Starter** (Desktop Application)
- **Version**: v3.0
- **Last Updated**: 2026-01-31

---

## Tech Stack

### Core Technologies

- **Python**: 3.9+ (호환성 유지 필수)
- **GUI Framework**: PySide6
- **Database**: SQLite
- **Data Processing**: pandas, openpyxl
- **Image Processing**: Pillow (PIL)
- **Windows Automation**: pywin32 (Excel COM, PDF 변환)

### Additional Libraries

- pdf2image, poppler-utils (PDF → 이미지 변환)
- gspread, google-auth (Google Sheets 백업)

---

## Development Rules

### 1. Python 호환성

- **Python 3.9** 호환성 엄격히 유지
- 타입 힌트는 `typing` 모듈 사용 (`Optional`, `List`, `Dict` 등)
- `|` 유니온 문법 대신 `Union` 또는 `Optional` 사용

```python
# ❌ Python 3.10+ 문법 (금지)
def function(param: str | None):
    pass

# ✅ Python 3.9 호환 문법
from typing import Optional
def function(param: Optional[str]):
    pass
```

### 2. 인코딩 처리

- **모든 파일은 UTF-8 인코딩**
- BOM 없는 UTF-8 사용
- 한글 경로/파일명 처리 표준: `config/settings.py`의 경로 처리 로직 따름

```python
# settings.py 경로 처리 예시
def get_resource_path(relative_path):
    \"\"\"리소스 파일 경로를 안전하게 가져옴 (한글 경로 대응)\"\"\"
    if getattr(sys, 'frozen', False):
        # PyInstaller 패키징 환경
        base_path = sys._MEIPASS
    else:
        # 개발 환경
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)
```

### 3. 경로 처리 표준

- **절대 경로** 우선 사용
- PyInstaller 패키징 고려 (`sys.frozen` 체크)
- 출력 폴더 자동 폴백 처리 (한글 폴더 → 영문 폴더)

---

## Code Quality Standards

### 1. DRY (Don't Repeat Yourself)

- **2회 이상 반복되는 코드는 함수/메서드로 추출**
- 공통 유틸리티는 `utils/` 모듈에 배치

### 2. SRP (Single Responsibility Principle)

- 하나의 함수/클래스는 하나의 책임만
- 함수 길이는 **20줄 이내** 권장
- if-else 중첩은 **3단계 이내**

### 3. 안전한 Config 접근

- **`.get()` 메서드 사용 필수**
- 기본값 제공으로 KeyError 방지

```python
# ❌ 위험: KeyError 가능
value = config['some_key']

# ✅ 안전: KeyError 방지
value = config.get('some_key', default_value)
```

### 4. 타입 힌트

- 모든 함수/메서드에 타입 힌트 추가
- 반환 타입 명시

```python
from typing import Optional, List, Dict

def get_records(start_date: str, end_date: str) -> List[Dict]:
    \"\"\"배합 기록 조회\"\"\"
    pass
```

### 5. 로깅

- `utils.logger.logger` 사용
- 적절한 로그 레벨 선택 (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- f-string 포맷 사용

```python
from utils.logger import logger

logger.info(f\"레시피 로드 완료: {len(recipes)}종\")
logger.error(f\"데이터베이스 연결 실패: {error}\")
```

---

## Module Structure

```
v3/main/
├── config/              # 설정 관리
│   ├── settings.py      # 경로, 환경 설정
│   ├── config.json      # 런타임 설정
│   └── config_manager.py # 설정 관리자
├── models/              # 비즈니스 로직
│   ├── data_manager.py  # 데이터 관리 (레시피, 배합 기록)
│   ├── database.py      # SQLite DB 관리
│   ├── excel_exporter.py # Excel/PDF 출력
│   ├── image_processor.py # 서명 이미지 처리
│   └── lot_manager.py   # LOT 번호 관리
├── ui/                  # 사용자 인터페이스
│   ├── main_window.py   # 메인 윈도우
│   ├── components.py    # 재사용 UI 컴포넌트
│   ├── styles.py        # 스타일 시스템
│   └── dialogs/         # 다이얼로그
├── utils/               # 유틸리티
│   ├── logger.py        # 로깅 시스템
│   └── error_handler.py # 예외 처리
├── pdf_processor_gui/   # PDF 처리 도구
├── signature_qa_tool/   # 서명 QA 도구
└── tests/               # 단위 테스트
```

---

## Design System (SSOT)

UI 디자인 토큰의 SSOT는 두 곳이며, 두 위치는 항상 정렬되어야 한다.

| 위치 | 형태 | 우선순위 |
|---|---|---|
| `v3/ui/styles.py` (`UITheme` 클래스) | Python 상수 — PySide6 stylesheet에서 사용 | **런타임 진실(SSOT)** |
| `v3/docs/design-system/colors_and_type.css` | CSS 커스텀 프로퍼티 + HTML 프리뷰 | 참조용 미러 |

### 새 UI 코드 작성 시 규칙

- 색·간격·radius·폰트는 **반드시 `UITheme`의 기존 토큰 사용**. 새 색을 직접 적어 넣지 말 것.
- 시각 의도가 헷갈릴 때는 `v3/docs/design-system/preview/*.html`을 열어 정답 시안을 확인.
- `ui_kits/desktop/index.html`은 메인 화면 3종(배합·로그인·DHR 관리) 웹 재현본 — 새 화면 디자인의 출발점으로 활용 가능.

### 토큰 명명 주의

소스 코드의 `MINT_*` 접두어는 레거시 명명이다. **실제 색은 앰버/골드 (`#E3A12F`)** 이며 민트/틸이 아니다. **민트/틸 계열을 새로 도입하지 말 것.**

### 두 SSOT가 어긋날 때

1. `styles.py`(런타임)가 옳다고 가정.
2. `design-system/colors_and_type.css`를 그쪽에 맞게 갱신.
3. 정렬 작업은 PDCA 사이클로 추적 (`design_system_alignment_audit` 류).

---

## Data Model

### mixing_records (배합 기록)

- `id` (INTEGER PRIMARY KEY)
- `product_lot` (TEXT) - 제품 LOT 번호
- `recipe_name` (TEXT) - 레시피명
- `worker` (TEXT) - 작업자
- `work_date` (TEXT) - 작업일자 (YYYY-MM-DD)
- `work_time` (TEXT) - 작업시간 (HH:MM:SS)
- `total_amount` (REAL) - 총 배합량 (g)
- `scale` (TEXT) - 저울 정보
- `created_at`, `updated_at` (TIMESTAMP)

### mixing_details (배합 상세)

- `id` (INTEGER PRIMARY KEY)
- `mixing_record_id` (INTEGER FK)
- `material_code`, `material_name` (TEXT)
- `material_lot` (TEXT) - 자재 LOT
- `ratio` (REAL) - 배합 비율 (%)
- `theory_amount` (REAL) - 이론 배합량 (g)
- `actual_amount` (REAL) - 실제 배합량 (g)
- `sequence_order` (INTEGER)
- `created_at` (TIMESTAMP)

---

## Testing Guidelines

### Test Structure

```
tests/
├── test_runner.py           # 테스트 실행기
├── test_normal_blend.py     # 정상 배합 테스트
├── test_pdf_quality.py      # PDF 품질 테스트
└── test_signature_position.py # 서명 위치 테스트
```

### Test Execution

```bash
# 모든 테스트 실행
python tests/test_runner.py

# 특정 테스트 실행
python tests/test_runner.py --module test_normal_blend
```

---

## PDCA Documentation

프로젝트 개선 사항은 PDCA 사이클에 따라 문서화:

### 01-plan/ (Plan - 계획)

- 기능 계획서
- 통합 계획
- 개선 제안

### 02-design/ (Do - 설계)

- 시스템 아키텍처
- API 설계
- UI/UX 설계

### 03-analysis/ (Check - 분석)

- Gap 분석
- 코드 리뷰
- 성능 분석

### 04-report/ (Act - 보고)

- 완료 보고서
- 교훈 정리
- 다음 사이클 계획

---

## Conventions

### File Naming

- Python 파일: `snake_case.py`
- 문서 파일: `{name}.{type}.md` (예: `integration.plan.md`)

### Variable Naming

- 변수/함수: `snake_case`
- 클래스: `PascalCase`
- 상수: `UPPER_SNAKE_CASE`

### Commit Messages (Git 사용 시)

- 형식: `[타입] 간단한 설명`
- 타입: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`

---

## Current Focus Areas

1. **.venv 정리**: 가상환경에서 앱 자산 분리 (INTEGRATION_PLAN.md 참조)
2. **Google Sheets 백업**: 통합 작업 완료 확인
3. **UX 개선**: 단일 인스턴스, 창 최상위, 입력 UX 강화
4. **코드 품질**: DRY, SRP 원칙 적용, 테스트 커버리지 향상

---

**마지막 업데이트**: 2026-01-31  
**담당자**: AI Assistant
