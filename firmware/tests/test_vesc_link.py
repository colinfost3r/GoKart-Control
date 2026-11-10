"""Exercise the production VescLink parser with real framed replies, without hardware."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


class VescIdentityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        compiler = shutil.which('c++')
        if compiler is None:
            raise RuntimeError('C++ compiler required for VESC identity regression checks')
        cls.tmp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.tmp.cleanup)
        cls.binary = Path(cls.tmp.name) / 'vesc-identity'
        subprocess.run([
            compiler, '-std=c++17', '-Wall', '-Wextra', '-Werror',
            '-fsanitize=address,undefined', '-g',
            '-I' + str(ROOT / 'firmware/tests/vesc_link_stub'),
            '-I' + str(ROOT / 'firmware/libraries/VescLink'),
            str(ROOT / 'firmware/tests/vesc_link_identity.cpp'),
            str(ROOT / 'firmware/libraries/VescLink/VescLink.cpp'),
            '-o', str(cls.binary),
        ], check=True)

    def run_case(self, case):
        subprocess.run([str(self.binary), case], check=True, timeout=30)

    def test_link_loss_invalidates_identity(self):
        self.run_case('loss')

    def test_every_truncated_reply_invalidates_identity(self):
        self.run_case('truncation')

    def test_hardware_name_termination_and_bounds(self):
        self.run_case('name')

    def test_config_and_telemetry_before_identity(self):
        self.run_case('ordering')

    def test_replacement_controller_needs_own_uuid(self):
        self.run_case('replacement')


if __name__ == '__main__':
    unittest.main()
