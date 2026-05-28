# 배합 프로그램 v3 (Program-estimation)

> 제조업 원료 배합 관리 및 품질 보증을 위한 Windows 데스크톱 애플리케이션 (PySide6)

## Project Level
**Level: Starter** (데스크톱 애플리케이션 - bkit 기준)

> **참고**: `v3/CLAUDE.md`가 이미 존재하며 상세한 프로젝트 문서를 포함합니다.  
> 이 파일은 프로젝트 루트 관점의 요약입니다. 세부 개발 규칙은 `v3/CLAUDE.md`를 참조하세요.

## Quick Start

```bash
# 가상환경 생성 (Python 3.13.x)
py -3.13 -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r v3\requirements.txt

# 개발 실행
run_dev.bat
# 또는
cd v3
..\.venv\Scripts\python.exe main.py

# 배포본 실행
v3\dist\DHR_Generator.exe

# 테스트
cd v3
..\.venv\Scripts\python.exe tests\run_tests.py

# 릴리스 아티팩트 검증
cd v3
..\.venv\Scripts\python.exe check_release_artifacts.py
```

## Architecture

```
┌──────────────────┐     ┌────────────────┐     ┌──────────┐
│  PySide6 GUI     │────▶│  DataManager   │────▶│  SQLite  │
│  ui/             │     │  models/       │     │  (.db)   │
│  (MainWindow)    │◀────│  (비즈니스 로직)│     │          │
└──────────────────┘     └────────────────┘     └──────────┘
```

### 주요 디렉토리 구조

```
v3/                     # ★ 실제 개발 작업 폴더
├── main.py             # 앱 진입점 (PySide6 + 단일 인스턴스)
├── config/
│   ├── settings.py     # 경로, 환경 설정
│   └── config.json     # 런타임 설정
├── models/
│   ├── data_manager.py # 데이터 관리 (레시피, 배합 기록)
│   ├── database.py     # SQLite DB 관리
│   ├── dhr_database.py # DHR DB 관리
│   ├── excel_exporter.py # Excel/PDF 출력
│   ├── image_processor.py # 서명 이미지 처리
│   ├── lot_manager.py  # LOT 번호 관리
│   └── backup/         # DB 백업 로직
├── ui/
│   ├── main_window.py  # 메인 윈도우
│   ├── components.py   # 재사용 UI 컴포넌트
│   ├── styles.py       # ★ 디자인 시스템 SSOT (UITheme 클래스)
│   ├── controllers.py  # UI 컨트롤러
│   ├── builders.py     # UI 빌더
│   ├── dialogs/        # 다이얼로그
│   ├── panels/         # 패널
│   └── widgets/        # 커스텀 위젯
├── utils/
│   ├── logger.py       # 로깅
│   └── error_handler.py # 예외 처리
├── pdf_processor_gui/  # PDF 처리 도구
├── signature_qa_tool/  # 서명 QA 도구
├── tests/
│   ├── run_tests.py    # 테스트 실행기
│   ├── test_normal_blend.py
│   ├── test_pdf_quality.py
│   ├── test_signature_position.py
│   ├── unit/           # 단위 테스트
│   └── integration/    # 통합 테스트
├── resources/          # 리소스 (아이콘, 이미지)
├── dist/               # 배포 산출물 (DHR_Generator.exe)
├── docs/               # 문서 (SETUP.md, design-system 등)
├── build.py            # 빌드 스크립트
├── deploy.py           # 배포 스크립트
├── release.py          # 릴리스 스크립트
└── requirements.txt    # 의존성 (고정 버전)

docs/                   # 루트 문서 (PDCA, 가이드)
skills/                 # AI 스킬 정의
.agents/                # 에이전트 설정
```

## Key Commands

| 작업 | 명령어 |
|------|--------|
| 개발 실행 | `run_dev.bat` 또는 `cd v3 && ..\.venv\Scripts\python.exe main.py` |
| 배포 실행 | `v3\dist\DHR_Generator.exe` |
| 테스트 | `cd v3 && ..\.venv\Scripts\python.exe tests\run_tests.py` |
| 빌드 (exe) | `cd v3 && ..\.venv\Scripts\python.exe build.py` |
| 릴리스 검증 | `cd v3 && ..\.venv\Scripts\python.exe check_release_artifacts.py` |
| 배포 패키지 | `cd v3 && ..\.venv\Scripts\python.exe deploy.py` |

## Coding Conventions

- **Python 3.9+ 호환** 엄격 유지 (`|` 유니온 대신 `Union`/`Optional` 사용)
- **snake_case**: 함수, 변수, 파일명
- **PascalCase**: 클래스
- **UPPER_SNAKE_CASE**: 상수
- **UTF-8** 인코딩 (BOM 없음)
- **설계 시스템 SSOT**: `v3/ui/styles.py`의 `UITheme` 클래스가 런타임 진실
- **MINT_ 접두어 주의**: 레거시 명명, 실제 색은 앰버/골드 (`#E3A12F`)
- `.get()` 메서드로 안전한 config 접근
- DRY/SRP 원칙: 함수 20줄 이내, if-else 3단계 이내
- 모든 함수에 타입 힌트 추가
- 로깅: `utils.logger.logger` 사용

## Important Notes

- **실제 개발 폴더**: `v3/` — 루트는 설정/문서 역할
- **가상환경**: `.venv/`는 루트에 위치하지만 항상 재설치 권장
- **단일 인스턴스**: Windows Mutex로 중복 실행 방지
- **배포 산출물**: `v3/dist/DHR_Generator.exe` + `resources/` + `README.md`
- **세부 개발 규칙**: `v3/CLAUDE.md`에 상세 기록 (데이터 모델, 테스트, PDCA 등)
- **PyInstaller**: `DHR_Mixing_System.spec`으로 패키징
- **Google Sheets 백업**: gspread 연동 기능 존재
