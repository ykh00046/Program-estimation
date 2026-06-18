"""
DHR Generator 실행 파일 빌드 스크립트
PyInstaller를 사용하여 배포 기준 실행 파일을 생성합니다.
"""
import os
import sys
import shutil
import subprocess

def build_exe():
    """실행 파일 빌드"""
    print("=" * 60)
    print("DHR Generator 빌드 시작")
    print("=" * 60)
    
    # 1. 기존 빌드 폴더 삭제
    if os.path.exists("dist"):
        print("\n[1/4] 기존 dist 폴더 삭제 중...")
        shutil.rmtree("dist")
    
    if os.path.exists("build"):
        print("[1/4] 기존 build 폴더 삭제 중...")
        shutil.rmtree("build")
    
    # 2. PyInstaller 명령어 구성
    print("\n[2/4] PyInstaller 명령어 구성 중...")
    
    # build.py를 실행한 인터프리터(프로젝트 venv)의 PyInstaller를 강제한다.
    # bare "pyinstaller"는 PATH 1순위의 무관한 환경(예: 타 도구 venv)으로 빌드되어
    # qfluentwidgets 등 미설치 모듈이 번들에서 누락될 수 있음 (2026-06-11 사고).
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",                    # 단일 파일로 생성
        "--windowed",                   # 콘솔 창 숨김
        "--name=DHR_Generator",         # 실행 파일 이름
        "--add-data=resources;resources",  # resources 폴더 포함
        "--add-data=config;config",        # config 폴더 포함
        "--hidden-import=openpyxl",     # openpyxl 명시적 포함
        "--hidden-import=PIL",          # Pillow 명시적 포함
        "--hidden-import=gspread",      # Google Sheets 백업을 위한 gspread 임포트
        "--hidden-import=google.auth",  # Google Sheets 백업을 위한 google.auth 임포트
        "--hidden-import=google.oauth2.service_account", # Google Sheets 백업을 위한 service_account 임포트
        "--clean",                      # 캐시 정리
        "main.py"
    ]
    
    print("명령어:", " ".join(cmd))
    
    # 3. 빌드 실행
    print("\n[3/4] 빌드 실행 중...")
    print("-" * 60)
    
    try:
        subprocess.run(cmd, check=True)
        print("-" * 60)
        print("[OK] 빌드 성공!")
    except subprocess.CalledProcessError as e:
        print("-" * 60)
        print(f"[ERROR] 빌드 실패: {e}")
        return False
    
    # 4. 결과 확인
    print("\n[4/4] 빌드 결과 확인 중...")
    
    exe_path = os.path.join("dist", "DHR_Generator.exe")
    if os.path.exists(exe_path):
        file_size = os.path.getsize(exe_path) / (1024 * 1024)  # MB
        print(f"[OK] 실행 파일 생성 완료: {exe_path}")
        print(f"[OK] 파일 크기: {file_size:.1f} MB")
        
        # build 폴더 정리
        if os.path.exists("build"):
            shutil.rmtree("build")
            print("[OK] build 폴더 정리 완료")
        
        # spec 파일 정리
        spec_file = "DHR_Generator.spec"
        if os.path.exists(spec_file):
            os.remove(spec_file)
            print("[OK] spec 파일 정리 완료")
        
        print("\n" + "=" * 60)
        print("빌드 완료!")
        print("=" * 60)
        print(f"\n실행 파일 위치: {os.path.abspath(exe_path)}")
        print("\n다음 단계:")
        print("1. deploy.py를 실행해 배포 패키지를 생성")
        print("2. 배포 계약은 루트 DEPLOY_GUIDE.md 문서를 기준으로 확인")
        print("3. 단일 exe 전달이 아니라 exe와 resources가 함께 포함된 패키지를 배포")
        
        return True
    else:
        print("[ERROR] 실행 파일 생성 실패")
        return False

if __name__ == "__main__":
    print("\nPython 버전:", sys.version)
    print("작업 디렉토리:", os.getcwd())
    print()
    
    # PyInstaller 설치 확인
    try:
        import PyInstaller
        print(f"PyInstaller 버전: {PyInstaller.__version__}\n")
    except ImportError:
        print("[ERROR] PyInstaller가 설치되지 않았습니다.")
        print("설치 명령어: pip install pyinstaller")
        sys.exit(1)
    
    success = build_exe()
    
    if not success:
        sys.exit(1)
