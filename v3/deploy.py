"""
DHR Generator 배포 패키지 생성 스크립트.

배포 계약은 프로젝트 루트 DEPLOY_GUIDE.md를 기준으로 유지합니다.
"""
import os
import shutil
import zipfile
from datetime import datetime

def create_deployment_package():
    """배포 패키지 생성"""
    print("=" * 60)
    print("DHR Generator 배포 패키지 생성")
    print("=" * 60)
    
    # 버전 정보
    version = "v3.0.0"
    date_str = datetime.now().strftime("%Y%m%d")
    package_name = f"DHR_Generator_{version}_{date_str}"
    
    # 1. 배포 폴더 생성
    print(f"\n[1/5] 배포 폴더 생성 중: {package_name}")
    if os.path.exists(package_name):
        shutil.rmtree(package_name)
    os.makedirs(package_name)
    
    # 2. 실행 파일 복사
    print("\n[2/5] 실행 파일 복사 중...")
    exe_src = os.path.join("dist", "DHR_Generator.exe")
    if not os.path.exists(exe_src):
        print("[ERROR] 실행 파일이 없습니다. 먼저 build.py를 실행하세요.")
        return False
    
    shutil.copy(exe_src, package_name)
    print(f"[OK] {exe_src} → {package_name}/")
    
    # 3. resources 폴더 복사
    print("\n[3/5] resources 폴더 복사 중...")
    resources_src = "resources"
    resources_dst = os.path.join(package_name, "resources")
    
    if os.path.exists(resources_src):
        # DB와 배합기록.xlsx는 제외
        shutil.copytree(resources_src, resources_dst, 
                       ignore=shutil.ignore_patterns('*.db', '배합기록.xlsx', '__pycache__', '*.pyc'))
        print(f"[OK] {resources_src}/ → {resources_dst}/")
    else:
        print("[WARNING] resources 폴더가 없습니다.")
    
    # 4. 문서 파일 복사
    print("\n[4/5] 문서 파일 복사 중...")
    docs = ["../README.md", "../DEPLOY_GUIDE.md", "../RELEASE_SMOKE_CHECKLIST.md"]
    for doc in docs:
        if os.path.exists(doc):
            shutil.copy(doc, package_name)
            print(f"[OK] {doc} → {package_name}/")
        else:
            print(f"[WARNING] 문서 파일이 없어 건너뜀: {doc}")
    
    # 5. 압축
    print("\n[5/5] 압축 파일 생성 중...")
    zip_name = f"{package_name}.zip"
    
    with zipfile.ZipFile(zip_name, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(package_name):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, package_name)
                arcname = os.path.join(package_name, arcname)
                zipf.write(file_path, arcname)
                print(f"  추가: {arcname}")
    
    zip_size = os.path.getsize(zip_name) / (1024 * 1024)
    print(f"\n[OK] 압축 완료: {zip_name} ({zip_size:.1f} MB)")
    
    # 완료 메시지
    print("\n" + "=" * 60)
    print("배포 패키지 생성 완료!")
    print("=" * 60)
    print(f"\n패키지 이름: {package_name}")
    print(f"압축 파일: {zip_name}")
    print(f"압축 크기: {zip_size:.1f} MB")
    print("\n배포 방법:")
    print(f"1. {zip_name} 파일을 대상 PC에 전달")
    print("2. 압축 해제 후 DHR_Generator.exe와 resources/를 같은 폴더 구조로 유지")
    print("3. DEPLOY_GUIDE.md의 사용자 실행 절차에 따라 DHR_Generator.exe 실행")
    
    return True

if __name__ == "__main__":
    import sys
    
    print("\n작업 디렉토리:", os.getcwd())
    print()
    
    success = create_deployment_package()
    
    if not success:
        sys.exit(1)
