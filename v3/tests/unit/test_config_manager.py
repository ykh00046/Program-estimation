"""
ConfigManager 단위 테스트
"""
import unittest
from unittest.mock import patch, mock_open
import json
import os
import sys

# Ensure project root is in path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))
sys.path.insert(0, project_root)


class TestConfig(unittest.TestCase):
    """Config 클래스 테스트"""

    def setUp(self):
        """테스트용 Config 인스턴스 생성"""
        # Mock config.json 내용
        self.mock_config_data = {
            "mixing": {
                "default_scale": "M-100",
                "tolerance": 0.1,
                "workers": ["Worker1", "Worker2"]
            },
            "scan_effects": {
                "dpi": 300,
                "blur_radius": 0.5
            },
            "nested": {
                "level1": {
                    "level2": "deep_value"
                }
            }
        }

    @patch('os.path.exists')
    @patch('builtins.open', new_callable=mock_open)
    @patch('os.makedirs')
    def test_get_default_values(self, mock_makedirs, mock_file, mock_exists):
        """기본값 반환 테스트"""
        mock_exists.return_value = False  # config 파일 없음
        
        from config.config_manager import Config
        cfg = Config()
        
        # 없는 키에 대해 기본값 반환
        result = cfg.get("nonexistent.key", "default_value")
        self.assertEqual(result, "default_value")

    @patch('os.path.exists')
    @patch('builtins.open', new_callable=mock_open)
    @patch('os.makedirs')
    def test_get_nested_key(self, mock_makedirs, mock_file, mock_exists):
        """중첩 키 접근 테스트"""
        mock_exists.return_value = True
        mock_file.return_value.read.return_value = json.dumps(self.mock_config_data)
        
        from config.config_manager import Config
        cfg = Config()
        cfg._data = self.mock_config_data  # 직접 데이터 설정
        
        result = cfg.get("nested.level1.level2")
        self.assertEqual(result, "deep_value")

    @patch('os.path.exists')
    @patch('builtins.open', new_callable=mock_open)
    @patch('os.makedirs')  
    def test_default_scale_property(self, mock_makedirs, mock_file, mock_exists):
        """default_scale 프로퍼티 테스트"""
        mock_exists.return_value = True
        
        from config.config_manager import Config
        cfg = Config()
        cfg._data = self.mock_config_data
        
        self.assertEqual(cfg.default_scale, "M-100")

    @patch('os.path.exists')
    @patch('builtins.open', new_callable=mock_open)
    @patch('os.makedirs')
    def test_tolerance_property(self, mock_makedirs, mock_file, mock_exists):
        """tolerance 프로퍼티 테스트"""
        mock_exists.return_value = True
        
        from config.config_manager import Config
        cfg = Config()
        cfg._data = self.mock_config_data
        
        self.assertEqual(cfg.tolerance, 0.1)
        
    @patch('os.path.exists')
    @patch('builtins.open', new_callable=mock_open)
    @patch('os.makedirs')
    def test_workers_property(self, mock_makedirs, mock_file, mock_exists):
        """workers 프로퍼티 테스트"""
        mock_exists.return_value = True
        
        from config.config_manager import Config
        cfg = Config()
        cfg._data = self.mock_config_data
        
        workers = cfg.workers
        self.assertEqual(len(workers), 2)
        self.assertIn("Worker1", workers)


if __name__ == '__main__':
    unittest.main()
