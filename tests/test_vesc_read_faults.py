"""Fault-log reader tests with a fake serial port; never open hardware."""
import binascii
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools/vesc'))
sys.path.insert(0, str(ROOT/'tests'))
import read_faults as faults
from capture import PacketParser
from test_vesc_prepare_fleet_kart import FAKE_UUID, TARGET, fixture, uuid_field

SAMPLE = ('The following faults were registered since start:\n',
          'Fault            : FAULT_CODE_ABS_OVER_CURRENT\nMotor            : 1\nCurrent          : 231.4\n'
          'Current filtered : 142.7\nVoltage          : 78.21\nDuty             : 0.412\nRPM              : 9120.5\n',
          'Fault            : FAULT_CODE_ABS_OVER_CURRENT\nMotor            : 1\nCurrent          : 224.9\n',
          'Fault            : FAULT_CODE_OVER_VOLTAGE\nVoltage          : 90.6\n')


def packet(payload):
    return bytes((2, len(payload))) + payload + binascii.crc_hqx(payload, 0).to_bytes(2, 'big') + b'\x03'


class Connection:
    fd = 55
    def __init__(self, port): pass
    def __enter__(self): return self
    def __exit__(self, *unused): pass


class Port:
    """Answers the identity read and the faults command; records every request."""
    def __init__(self, identity, replies):
        self.identity, self.replies, self.sent, self.pending = identity, replies, [], bytearray()

    def write(self, fd, frame):
        payloads = PacketParser().feed(frame)
        assert len(payloads) == 1
        self.sent.append(payloads[0])
        if payloads[0][0] == 0:
            self.pending += packet(self.identity)
        else:
            for text in self.replies:
                self.pending += packet(bytes((21,)) + text.encode())
        return len(frame)

    def read(self, fd, size):
        chunk = bytes(self.pending[:23]); del self.pending[:23]
        return chunk

    def select(self, fds, write, error, timeout):
        return (fds if self.pending else [], [], [])


class ReadFaultsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        target = fixture(self.base/'target', TARGET)
        uuid_field(target, FAKE_UUID)
        self.identity = (target/'firmware.bin').read_bytes()
        self.out = self.base/'faults'

    def run_read(self, replies, uuid=FAKE_UUID):
        self.port = Port(self.identity, replies)
        ticks = iter(range(0, 100000))
        with patch.object(faults.os, 'write', self.port.write), patch.object(faults.os, 'read', self.port.read), \
             patch.object(faults.select, 'select', self.port.select), \
             patch('capture.os.read', self.port.read), patch('capture.select.select', self.port.select), \
             patch.object(faults.time, 'monotonic', side_effect=lambda: next(ticks) * 0.05), \
             patch('capture.time.monotonic', side_effect=lambda: next(ticks) * 0.05):
            return faults.read('FAKE', self.out, uuid, connection_factory=Connection)

    def test_only_the_identity_read_and_the_fixed_faults_command_are_sent(self):
        result = self.run_read(SAMPLE)
        self.assertEqual(self.port.sent, [b'\x00', b'\x14faults'])
        self.assertEqual(faults.FAULTS_PAYLOAD, b'\x14faults')
        self.assertEqual(PacketParser().feed(faults.faults_frame()), [b'\x14faults'])
        self.assertTrue(result['complete'] and result['answered'])
        self.assertEqual(result['fault_count'], 3)
        self.assertEqual(result['faults_by_name'], {'FAULT_CODE_ABS_OVER_CURRENT': 2, 'FAULT_CODE_OVER_VOLTAGE': 1})
        self.assertFalse(result['reported_none'])
        text = (self.out/'faults.txt').read_text()
        self.assertIn('Current          : 231.4', text)
        self.assertEqual(json.loads((self.out/'manifest.json').read_text())['identity']['uuid'], FAKE_UUID)

    def test_no_faults_and_no_answer_are_different_results(self):
        result = self.run_read(('No faults registered since startup\n',))
        self.assertTrue(result['complete'] and result['reported_none'])
        self.assertEqual(result['fault_count'], 0)
        self.out = self.base/'silent'
        result = self.run_read(())
        self.assertFalse(result['complete'] or result['answered'] or result['reported_none'])
        self.assertIn('not evidence of no faults', result['note'])

    def test_another_controller_is_refused_before_the_terminal_command(self):
        with self.assertRaisesRegex(ValueError, 'UUID does not match'):
            self.run_read(SAMPLE, uuid='0c0b0a090807060504030201')
        self.assertEqual(self.port.sent, [b'\x00'])
        self.assertIn('error', json.loads((self.out/'manifest.json').read_text()))


if __name__ == '__main__':
    unittest.main()
