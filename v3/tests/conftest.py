"""pytest 전역 부트스트랩 (PDCA #21).

프로젝트 모듈(config.settings) import보다 먼저 실행되어 환경을 설정한다.
- offscreen Qt 플랫폼
- 테스트 로그를 프로세스별 임시 경로로 격리 → 공유 프로덕션 로그와의
  롤오버 rename 경합(Windows WinError 32) 및 오염 방지.
"""
import os
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("MIXING_LOG_DIR", tempfile.mkdtemp(prefix="mixing_test_logs_"))
