"""Read-only telemetry trace tests with fake serial packets; never open hardware."""
from contextlib import ExitStack
import io
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools/vesc'))
sys.path.insert(0, str(ROOT/'tests'))
import apply_tune
import telemetry_trace as tracer
from capture import READ_COMMANDS, verified_identity
from test_vesc_apply_tune import FakeSerial, FakeWire

CAPTURE = ROOT/'hardware/vesc/kart3/2026-11-10/usb-prewrite-connected/raw'


class FakeClock:
    """Each query advances time, so the loop ends without real waiting."""
    def __init__(self):
        self.now = 1000.0

    def time(self):
        return self.now

    def monotonic(self):
        self.now += .05
        return self.now


class TelemetryTraceTests(unittest.TestCase):
    def setUp(self):
        payloads = {name: (CAPTURE/(name + '.bin')).read_bytes() for name in READ_COMMANDS.values()}
        self.uuid = verified_identity(payloads['firmware'])['uuid']
        self.wire = FakeWire(payloads)
        self.connection = FakeSerial(self.wire)
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.object(apply_tune.os, 'write', self.wire.write))
        self.stack.enter_context(patch.object(apply_tune.os, 'read', self.wire.read))
        self.stack.enter_context(patch.object(apply_tune.select, 'select', self.wire.select))
        self.stack.enter_context(patch.object(apply_tune.termios, 'tcflush', self.wire.flush))

    def run_trace(self, uuid=None, seconds=1.0, hz=10.0):
        log = io.StringIO()
        count = tracer.trace(self.connection, self.uuid if uuid is None else uuid, log, seconds, hz,
                             clock=FakeClock(), sleep=lambda _: None)
        return count, [json.loads(line) for line in log.getvalue().splitlines()]

    def ids(self):
        return [payload[0] for payload in self.wire.sent]

    def test_sends_identity_once_then_only_get_values(self):
        count, lines = self.run_trace()
        self.assertGreater(count, 3)
        self.assertEqual(self.ids()[0], 0)
        self.assertEqual(set(self.ids()[1:]), {4})
        self.assertEqual(len(self.ids()), count + 1)
        self.assertEqual(lines[0]['event'], 'start')
        self.assertEqual(lines[0]['uuid'], self.uuid)
        self.assertEqual(lines[0]['commands'], [0, 4])
        self.assertEqual(lines[-1], {'t': lines[-1]['t'], 'event': 'end', 'samples': count})
        for sample in lines[1:-1]:
            self.assertEqual(set(sample), {'t', *tracer.KEYS})
            self.assertEqual(sample['fault_code'], 0)
            self.assertEqual(sample['erpm'], 0)

    def test_other_controller_is_refused_before_any_telemetry(self):
        other = ('0' if self.uuid[0] != '0' else '1') + self.uuid[1:]
        with self.assertRaisesRegex(ValueError, 'not the stated one'):
            self.run_trace(uuid=other)
        self.assertEqual(self.ids(), [0])

    def test_bad_uuid_length_and_rate_are_refused_before_opening_a_query(self):
        for kwargs in ({'uuid': 'zz' * 12}, {'uuid': self.uuid.upper()}, {'uuid': self.uuid[:-2]},
                       {'seconds': 0}, {'seconds': 901}, {'hz': 0.5}, {'hz': 21}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                self.run_trace(**kwargs)
        self.assertEqual(self.ids(), [])

    def test_tool_can_only_build_allowlisted_read_frames(self):
        source = (ROOT/'tools/vesc/telemetry_trace.py').read_text()
        for forbidden in ('os.write', 'set_motor_once', 'motor_frame', 'SET_MCCONF', 'query(13', 'query(14', 'query(17'):
            self.assertNotIn(forbidden, source, forbidden)
        self.assertEqual(sorted(set(int(n) for n in __import__('re').findall(r'query\((\d+)\)', source))), [0, 4])


if __name__ == '__main__':
    unittest.main()
