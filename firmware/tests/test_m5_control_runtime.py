"""Run actual kart .ino control functions with fake hardware, not a copied command model.

The temporary includes are extracted afresh from the production sketch. Only peripheral
adapters, clock and test setup are mocked. No sockets, serial devices or controllers are used.
"""
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
SKETCH = ROOT / 'firmware/kart-heltec-v4/kart-heltec-v4.ino'


def section(source, start, end):
    a = source.index(start)
    b = source.index(end, a + len(start))
    return source[a:b]


def function(source, name):
    # Sketch functions end at column zero; nested blocks remain indented. Fail loudly if
    # a production refactor changes this convention, rather than testing stale copied code.
    match = re.search(r'^static [^\n]*\b' + re.escape(name) + r'\([^\n]*', source, re.M)
    if not match:
        raise AssertionError('Production function not found: ' + name)
    start = match.start()
    if match.group().rstrip().endswith('}'):
        return match.group() + '\n'
    end = re.search(r'^}', source[match.end():], re.M)
    if not end:
        raise AssertionError('Production function has no closing brace: ' + name)
    return source[start:match.end() + end.end()] + '\n'


class M5ControlRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        compiler = shutil.which('c++')
        if not compiler:
            raise RuntimeError('C++17 compiler required for production control tests')
        cls.tmp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.tmp.cleanup)
        tmp = Path(cls.tmp.name)
        source = SKETCH.read_text()
        (tmp / 'production_state.inc').write_text(section(source,
            '// ---------------------------------------------------------------- supervisory state',
            '// ---------------------------------------------------------------- fleet'))
        parts = [
            section(source, 'static bool writesEnabled()', 'static bool ppsFresh()'),
            section(source, '// ---------------------------------------------------------------- command bookkeeping',
                    '// ---------------------------------------------------------------- telemetry'),
            section(source, '// ---------------------------------------------------------------- vesc writes',
                    '// ---------------------------------------------------------------- M5 display UART'),
            function(source, 'm5ModeReady'), function(source, 'm5HandleLine'),
            function(source, 'serviceVesc'),
        ]
        (tmp / 'production_control.inc').write_text('\n'.join(parts))
        cls.binary = tmp / 'm5-control-runtime'
        subprocess.run([compiler, '-std=c++17', '-Wall', '-Wextra', '-Werror',
            '-Wno-unused-function', '-Wno-unused-variable', '-fsanitize=address,undefined', '-g',
            '-DGK_M5_CONTROL=1', '-DGK_M5_ESPNOW=1', '-DENABLE_VESC_WRITES=1',
            '-I' + str(tmp), '-I' + str(ROOT / 'firmware/tests/vesc_link_stub'),
            '-I' + str(ROOT / 'firmware/libraries/VescLink'),
            '-I' + str(ROOT / 'firmware/libraries/GoKartProtocol'),
            '-I' + str(ROOT / 'firmware/libraries/M5DisplayLink'),
            '-I' + str(ROOT / 'firmware/kart-heltec-v4'),
            str(ROOT / 'firmware/tests/m5_control_runtime.cpp'), '-o', str(cls.binary)], check=True)

    def run_case(self, *args):
        subprocess.run([str(self.binary), *args], check=True, timeout=10)

    def test_fresh_config_and_identity_before_mutation(self):
        for reason in ('stale', 'old-config', 'no-pin', 'old-identity', 'wrong-identity',
                       'suspect', 'nan', 'invalid-poles', 'changed-drivetrain', 'no-link'):
            with self.subTest(reason=reason):
                self.run_case('guard', reason)

    def test_mode_uses_live_passthrough_and_verified_ceiling(self):
        self.run_case('passthrough')

    def test_ack_readback_and_duplicate_suppression(self):
        self.run_case('ack')

    def test_stop_to_zero_then_start(self):
        self.run_case('stop-start')

    def test_boost_slow_and_race_timers_preserved(self):
        self.run_case('timers')

    def test_link_change_cancels_pending_result_without_replay(self):
        self.run_case('link-change')

    def test_mode_and_boost_above_ceiling_do_not_change_state(self):
        self.run_case('ceiling')

    def test_boot_identity_ordering_and_baseline_are_read_only(self):
        self.run_case('baseline')
        self.run_case('baseline-wrong-identity')

    def test_rejected_usb_durations_do_not_leak_into_pit_commands(self):
        self.run_case('durations')

    def test_stop_never_increases_low_current_allowance(self):
        self.run_case('low-stop')

    def test_stop_cancellation_before_and_between_ramp_steps(self):
        self.run_case('ramp-link-change', 'before')
        self.run_case('ramp-link-change', 'between')

    def test_mismatch_and_timeout_never_retry_motor_write(self):
        self.run_case('verification-failure', 'mismatch')
        self.run_case('verification-failure', 'timeout')

    def test_blocked_m5_request_does_not_replay_after_recovery(self):
        self.run_case('m5-blocked')


if __name__ == '__main__':
    unittest.main()
