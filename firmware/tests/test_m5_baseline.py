"""Strict M5 baseline-cache records; no serial ports or controller access."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
ROOT = Path(__file__).resolve().parents[2]
class VerifiedBaselineTests(unittest.TestCase):
    def test_uuid_bound_single_record_and_recovery(self):
        compiler = shutil.which('c++')
        self.assertIsNotNone(compiler, 'C++ compiler required')
        base = ROOT/'firmware/libraries/M5DisplayLink'
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)/'baseline_test'
            subprocess.run([compiler, '-std=c++17', '-Wall', '-Wextra', '-Werror',
                            '-fsanitize=address,undefined', '-g', '-I'+str(base),
                            str(base/'tests/baseline_test.cpp'), '-o', str(output)], check=True)
            subprocess.run([str(output)], check=True, timeout=30)
if __name__ == '__main__':
    unittest.main()
