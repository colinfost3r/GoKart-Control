"""Pure ESP-NOW framing regression checks; no radio, port, or controller access."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
ROOT = Path(__file__).resolve().parents[2]
class EspNowFrameTests(unittest.TestCase):
    def run_native(self, source):
        compiler = shutil.which('c++')
        self.assertIsNotNone(compiler, 'C++ compiler required')
        base = ROOT/'firmware/libraries/M5EspNowLink'
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)/'frame_test'
            subprocess.run([compiler, '-std=c++17', '-Wall', '-Wextra', '-Werror',
                            '-fsanitize=address,undefined', '-g', '-I'+str(base/'src'),
                            str(base/'tests'/source), '-o', str(output)], check=True)
            subprocess.run([str(output)], check=True, timeout=30)
    def test_bounded_framing_and_loss_recovery(self):
        self.run_native('frame_test.cpp')
    def test_authenticated_channel_alignment(self):
        self.run_native('channel_test.cpp')
    def test_runtime_channel_alignment(self):
        compiler = shutil.which('c++')
        self.assertIsNotNone(compiler, 'C++ compiler required')
        base = ROOT/'firmware/libraries/M5EspNowLink'
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)/'runtime_test'
            subprocess.run([compiler, '-std=c++17', '-Wall', '-Wextra', '-Werror',
                            '-fsanitize=address,undefined', '-g', '-I'+str(base/'tests/stubs'),
                            '-I'+str(base/'src'), str(base/'tests/channel_runtime_test.cpp'),
                            str(base/'src/M5EspNowLink.cpp'), '-o', str(output)], check=True)
            subprocess.run([str(output)], check=True, timeout=30)
if __name__ == '__main__':
    unittest.main()
