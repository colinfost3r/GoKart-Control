"""Read-only Lisp backup regressions using real packet parsing and fake fd IO."""
import binascii
from contextlib import ExitStack, redirect_stderr
import io
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools/vesc'))
import capture
import read_lisp

IDENTITY = (ROOT / 'hardware/vesc/kart3/2026-11-10/usb-prewrite-connected/raw/firmware.bin').read_bytes()


def packet(payload):
    header = (bytes((2, len(payload))) if len(payload) < 256 else
              b'\x03' + len(payload).to_bytes(2, 'big'))
    return header + payload + binascii.crc_hqx(payload, 0).to_bytes(2, 'big') + b'\x03'


class FakeWire:
    def __init__(self, code=b'(print "backup only")\x00\xff'):
        self.code, self.firmware = code, IDENTITY
        self.firmware_after = None
        self.sent, self.pending = [], bytearray()
        self.reply_hook = None
        self.partial_at = self.raise_at = self.bad_crc_at = None
        self.identity_reads = 0

    def write(self, fd, frame):
        requests = capture.PacketParser().feed(frame)
        assert len(requests) == 1
        request = requests[0]
        index = len(self.sent)
        self.sent.append(request)
        if index == self.partial_at:
            return len(frame) - 1
        if index == self.raise_at:
            raise OSError('Delivery unknown')
        if request[0] == 0:
            self.identity_reads += 1
            reply = (self.firmware_after if self.identity_reads > 1 and self.firmware_after
                     else self.firmware)
        else:
            assert request[0] == 130, 'Unexpected/mutating command'
            length, offset = struct.unpack('>ii', request[1:])
            reply = (b'\x82' + struct.pack('>ii', len(self.code), offset) +
                     self.code[offset:offset + length])
        if self.reply_hook:
            reply = self.reply_hook(request, reply, index)
        framed = bytearray(packet(reply))
        if index == self.bad_crc_at:
            framed[-2] ^= 1
        self.pending.extend(framed)
        return len(frame)

    def read(self, fd, size):
        # Fragment both short and >255-byte packets, including binary code bytes.
        chunk = bytes(self.pending[:17])
        del self.pending[:17]
        return chunk

    def select(self, fds, *unused):
        return (fds if self.pending else [], [], [])


class FakeConnection(read_lisp.SerialConnection):
    def __enter__(self):
        self.fd = 77
        return self

    def __exit__(self, *unused):
        self.fd = None


class LispReadTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.output = Path(self.temp.name) / 'new-backup'
        self.wire = FakeWire()
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.object(read_lisp.os, 'write', self.wire.write))
        self.stack.enter_context(patch.object(capture.os, 'read', self.wire.read))
        self.stack.enter_context(patch.object(capture.select, 'select', self.wire.select))
        self.stack.enter_context(patch.object(read_lisp, 'READ_TIMEOUT', .01))

    def run_backup(self):
        return read_lisp.backup('FAKE-NO-HARDWARE', self.output, read_lisp.KART3_UUID,
                                connection_factory=FakeConnection)

    def manifest(self):
        return json.loads((self.output / 'manifest.json').read_text())

    def test_only_identity_and_bounded_code_reads_can_be_serialized(self):
        for command in range(256):
            if command not in (0, 130):
                with self.subTest(command=command), self.assertRaises(ValueError):
                    read_lisp.query_frame(command)
        self.assertEqual(read_lisp.query_frame(0), bytes.fromhex('020100000003'))
        payload = capture.PacketParser().feed(read_lisp.query_frame(130, 256, 1024))
        self.assertEqual(payload, [b'\x82' + struct.pack('>ii', 256, 1024)])
        self.assertEqual(capture.READ_COMMANDS,
                         {0: 'firmware', 4: 'telemetry', 14: 'motor_configuration', 17: 'app_configuration'})
        with self.assertRaises(ValueError):
            capture.query_frame(130)
        for length, offset in [(-1, 0), (257, 0), (1, -1), (0, 1),
                               (1, read_lisp.MAX_CODE_BYTES), (1.0, 0)]:
            with self.subTest(length=length, offset=offset), self.assertRaises(ValueError):
                read_lisp.query_frame(130, length, offset)
        with self.assertRaises(ValueError):
            read_lisp.query_frame(0, 1, 0)

    def test_fragmented_binary_blob_is_exact_with_metadata_and_final_rechecks(self):
        self.wire.code = bytes(range(256)) * 2 + b'\x00\xffEND'
        result = self.run_backup()
        self.assertEqual((self.output / 'lisp_code.bin').read_bytes(), self.wire.code)
        self.assertFalse((self.output / 'lisp_code.partial.bin').exists())
        self.assertTrue(result['capture_complete'])
        self.assertEqual(result['status'], 'code_blob_captured')
        self.assertEqual(result['code_sha256'], read_lisp.sha256(self.wire.code))
        self.assertEqual(result['autostart'], 'not_read_unknown')
        self.assertFalse(result['raw_flash_dump'])
        self.assertFalse(result['snapshot_atomic'])
        self.assertEqual([p[0] for p in self.wire.sent], [0, 130, 130, 130, 130, 130, 0])
        self.assertEqual([struct.unpack('>ii', p[1:]) for p in self.wire.sent if p[0] == 130],
                         [(0, 0), (256, 0), (256, 256), (5, 512), (0, 0)])
        self.assertEqual((self.output / 'identity.bin').read_bytes(), IDENTITY)
        self.assertEqual((self.output / 'identity_after.bin').read_bytes(), IDENTITY)
        for query in result['queries']:
            self.assertTrue(query['transport_crc_verified'])
            raw = (self.output / query['file']).read_bytes()
            self.assertEqual(query['sha256'], read_lisp.sha256(raw))

    def test_empty_probe_is_no_valid_blob_not_erased_flash_proof(self):
        self.wire.code = b''
        result = self.run_backup()
        self.assertEqual(result['status'], 'no_valid_blob')
        self.assertEqual((self.output / 'lisp_code.bin').read_bytes(), b'')
        self.assertIn('not proof of blank', result['empty_result_meaning'])
        self.assertEqual([p[0] for p in self.wire.sent], [0, 130, 0])

    def test_bad_identity_blocks_all_lisp_queries_and_keeps_failure_evidence(self):
        for kind in ('uuid', 'version', 'truncated'):
            self.output = Path(self.temp.name) / kind
            raw = bytearray(IDENTITY)
            if kind == 'uuid': raw[raw.index(0, 3) + 1] ^= 1
            elif kind == 'version': raw[2] = 0
            else: raw = raw[:15]
            self.wire.firmware = bytes(raw)
            self.wire.sent.clear()
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                self.run_backup()
            self.assertEqual([p[0] for p in self.wire.sent], [0])
            self.assertFalse(self.manifest()['capture_complete'])
            self.assertTrue((self.output / 'identity.bin').exists())
            self.assertFalse((self.output / 'lisp_code.bin').exists())

    def test_negative_oversized_wrong_offset_truncated_and_extra_replies_rejected(self):
        malformed = [b'', b'\x00' + b'\0' * 8,
                     b'\x82' + struct.pack('>ii', -1, 0),
                     b'\x82' + struct.pack('>ii', read_lisp.MAX_CODE_BYTES + 1, 0),
                     b'\x82' + struct.pack('>ii', 5, -1),
                     b'\x82' + struct.pack('>ii', 5, 1),
                     b'\x82' + struct.pack('>ii', 5, 0) + b'unrequested']
        for payload in malformed:
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                read_lisp.parse_code_reply(payload, 0, 0)
        for data in (b'four', b'sixsix'):
            with self.assertRaises(ValueError):
                read_lisp.parse_code_reply(b'\x82' + struct.pack('>ii', 5, 0) + data, 5, 0, 5)
        self.assertEqual(read_lisp.parse_code_reply(
            b'\x82' + struct.pack('>ii', read_lisp.MAX_CODE_BYTES, 0), 0, 0)[0],
            read_lisp.MAX_CODE_BYTES)

    def test_changed_total_stops_after_one_valid_chunk_and_preserves_partial(self):
        self.wire.code = b'A' * 1024
        def change_total(request, reply, index):
            return b'\x82' + struct.pack('>ii', 1023, 256) + reply[9:] if index == 3 else reply
        self.wire.reply_hook = change_total
        with self.assertRaisesRegex(ValueError, 'total size changed'):
            self.run_backup()
        report = self.manifest()
        self.assertEqual(report['validated_code_bytes'], 256)
        self.assertEqual((self.output / report['partial_file']).read_bytes(), b'A' * 256)
        self.assertEqual(len(self.wire.sent), 4)
        self.assertFalse((self.output / 'lisp_code.bin').exists())

    def test_blob_becoming_invalid_midread_keeps_partial_without_retry(self):
        self.wire.code = b'A' * 512
        self.wire.reply_hook = lambda request, reply, index: (
            b'\x82' + struct.pack('>ii', 0, 0) if index == 3 else reply)
        with self.assertRaises(ValueError):
            self.run_backup()
        report = self.manifest()
        self.assertEqual(report['status'], 'failed')
        self.assertFalse(report['capture_complete'])
        self.assertEqual(report['validated_code_bytes'], 256)
        self.assertEqual((self.output / report['partial_file']).read_bytes(), b'A' * 256)
        self.assertEqual(len(self.wire.sent), 4)
        self.assertFalse((self.output / 'lisp_code.bin').exists())

    def test_wrong_offset_is_rejected_in_actual_backup_not_accepted_as_next_chunk(self):
        self.wire.reply_hook = lambda req, reply, idx: (
            reply[:5] + struct.pack('>i', 1) + reply[9:] if idx == 2 else reply)
        with self.assertRaisesRegex(ValueError, 'offset'):
            self.run_backup()
        self.assertEqual(self.manifest()['validated_code_bytes'], 0)
        self.assertEqual(len(self.wire.sent), 3)

    def test_bad_crc_times_out_without_resending_or_accepting_code(self):
        self.wire.bad_crc_at = 2
        with self.assertRaises(TimeoutError):
            self.run_backup()
        self.assertEqual(len(self.wire.sent), 3)
        self.assertEqual(self.manifest()['validated_code_bytes'], 0)
        self.assertFalse(self.manifest()['queries'][-1]['reply_received'])

    def test_partial_or_uncertain_query_send_never_retries_or_continues(self):
        for kind, index in [('partial', 0), ('partial', 1), ('partial', 2), ('raise', 2)]:
            self.output = Path(self.temp.name) / f'{kind}{index}'
            self.wire.sent.clear()
            self.wire.partial_at = index if kind == 'partial' else None
            self.wire.raise_at = index if kind == 'raise' else None
            with self.subTest(kind=kind, index=index), self.assertRaises(OSError):
                self.run_backup()
            self.assertEqual(len(self.wire.sent), index + 1)
            self.assertFalse(self.manifest()['capture_complete'])

    def test_final_identity_change_prevents_complete_backup(self):
        raw = bytearray(IDENTITY)
        raw[raw.index(0, 3) + 1] ^= 1
        self.wire.firmware_after = bytes(raw)
        with self.assertRaisesRegex(ValueError, 'UUID'):
            self.run_backup()
        self.assertEqual(self.manifest()['status'], 'failed')
        self.assertFalse((self.output / 'lisp_code.bin').exists())
        self.assertEqual((self.output / 'lisp_code.partial.bin').read_bytes(), self.wire.code)

    def test_final_size_change_prevents_complete_backup(self):
        self.wire.reply_hook = lambda req, reply, idx: (
            b'\x82' + struct.pack('>ii', 0, 0) if idx == 3 else reply)
        with self.assertRaisesRegex(ValueError, 'total size changed'):
            self.run_backup()
        self.assertFalse(self.manifest()['capture_complete'])
        self.assertEqual(len(self.wire.sent), 4)

    def test_existing_destination_or_invalid_expected_uuid_never_opens_port(self):
        self.output.mkdir()
        marker = self.output / 'keep.txt'
        marker.write_text('unchanged')
        with patch.object(read_lisp, 'SerialConnection') as serial:
            with self.assertRaises(FileExistsError):
                read_lisp.backup('NO-PORT', self.output, read_lisp.KART3_UUID)
            for bad in ('', '0' * 24, 'not-a-uuid', 'a' * 25):
                with self.subTest(uuid=bad), self.assertRaises(ValueError):
                    read_lisp.backup('NO-PORT', self.output / 'child', bad)
            serial.assert_not_called()
        self.assertEqual(marker.read_text(), 'unchanged')
        self.assertFalse((self.output / 'child').exists())

    def test_cli_requires_uuid_before_any_hardware_action(self):
        with patch.object(read_lisp, 'SerialConnection') as serial:
            with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                read_lisp.main(['--port', 'NO-PORT', '--out', str(self.output)])
            serial.assert_not_called()
        self.assertFalse(self.output.exists())

    def test_serial_setup_avoids_hangup_on_close_and_restores_other_settings(self):
        original = [1, 2, read_lisp.termios.HUPCL, 4, 5, 6, [0] * 32]
        changes = []
        with patch.object(read_lisp.os, 'open', return_value=88), \
             patch.object(read_lisp.os, 'close') as close, \
             patch.object(read_lisp.termios, 'tcgetattr', side_effect=lambda fd: original.copy()), \
             patch.object(read_lisp.tty, 'setraw') as raw, \
             patch.object(read_lisp.termios, 'tcsetattr',
                          side_effect=lambda fd, when, cfg: changes.append(cfg.copy())):
            with read_lisp.SerialConnection('FAKE-NO-HARDWARE'):
                pass
        raw.assert_called_once_with(88, read_lisp.termios.TCSANOW)
        close.assert_called_once_with(88)
        self.assertEqual(changes[0][2] & read_lisp.termios.HUPCL, 0)
        self.assertEqual(changes[-1][2] & read_lisp.termios.HUPCL, 0)
        self.assertEqual(changes[-1][:2], original[:2])


if __name__ == '__main__':
    unittest.main()
