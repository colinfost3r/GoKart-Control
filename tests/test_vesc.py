"""Offline checks against the real captured baseline and invalid wire data."""
import binascii
from contextlib import ExitStack, redirect_stdout
import hashlib
import io
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools/vesc'))
import capture
from capture import PacketParser, query_frame, identity, verified_identity, validate_snapshot
from decode import decode_configuration, decode_telemetry, decode_capture, crc32c

RAW = ROOT / 'hardware/vesc/baseline-kart/2026-11-05/raw'
SCHEMA = ROOT / 'third_party/vesc_tool/6.00'


def packet(payload):
    length = len(payload)
    header = bytes([2, length]) if length < 256 else b'\x03' + length.to_bytes(2, 'big')
    return header + payload + binascii.crc_hqx(payload, 0).to_bytes(2, 'big') + b'\x03'


class ProtocolTests(unittest.TestCase):
    def test_mutating_commands_rejected(self):
        for command in (1, 2, 3, 5, 6, 7, 8, 13, 16, 20, 29, 30, 48, 49, 255):
            with self.assertRaises(ValueError):
                query_frame(command)

    def test_known_crc_vectors(self):
        self.assertEqual(crc32c(b'123456789'), 0xe3069283)
        self.assertEqual(query_frame(0), bytes.fromhex('020100000003'))

    def test_fragmented_real_configuration(self):
        payload = (RAW / 'motor_configuration.bin').read_bytes()
        parser, result = PacketParser(), []
        for byte in packet(payload):
            result.extend(parser.feed(bytes([byte])))
        self.assertEqual(result, [payload])

    def test_multiple_packets_and_noise(self):
        payload = (RAW / 'firmware.bin').read_bytes()
        self.assertEqual(PacketParser().feed(b'\xff\xff' + packet(payload)*2), [payload, payload])

    def test_bad_crc_and_truncated_packets_are_not_accepted(self):
        wire = bytearray(packet((RAW / 'firmware.bin').read_bytes()))
        wire[-2] ^= 1
        self.assertEqual(PacketParser().feed(wire), [])
        self.assertEqual(PacketParser().feed(bytes(wire[:10])), [])

    def test_baseline_identity(self):
        data = identity((RAW / 'firmware.bin').read_bytes())
        self.assertEqual((data['firmware'], data['hardware'], data['firmware_name']),
                         ('6.00', '75_100_V2', 'no_hw_limits'))

    def test_full_schema_decode_and_measured_limits(self):
        for name, schema, command, count in [('motor_configuration','parameters_mcconf.xml',14,189),
                                             ('app_configuration','parameters_appconf.xml',17,187)]:
            raw = (RAW / (name+'.bin')).read_bytes()
            decoded = decode_configuration(raw, SCHEMA/schema, command)
            self.assertEqual(len(decoded['values']), count)
            self.assertEqual(decoded['bytes_consumed'], len(raw))
            if command == 14:
                self.assertEqual(decoded['values']['l_in_current_max'], 100)
                self.assertEqual(decoded['values']['l_current_max'], 140)
                self.assertEqual(decoded['enum_labels']['m_motor_temp_sens_type'], 'Disabled')
            for invalid in (raw[:-1], raw+b'\x00', raw[:1]+b'\x00'*4+raw[5:]):
                with self.assertRaises(ValueError):
                    decode_configuration(invalid, SCHEMA/schema, command)

    def test_telemetry_snapshot(self):
        d = decode_telemetry((RAW/'telemetry.bin').read_bytes())
        self.assertEqual(d['input_voltage_v'], 76.4)
        self.assertEqual(d['fault_code'], 0)
        self.assertEqual(d['controller_id'], 69)
        self.assertEqual(d['bytes_consumed'], 74)


class CompatibilityTests(unittest.TestCase):
    @staticmethod
    def fixture_602():
        # Synthetic identity, not a measurement from kart 3. Configuration wire
        # fixtures remain the real, immutable Nov 5 baseline with matching schemas.
        old = (RAW / 'firmware.bin').read_bytes()
        end = old.index(0, 3)
        return b'\x00\x06\x02' + b'75_300_R2\x00' + old[end+1:]

    def make_capture(self, target, firmware=None):
        target.mkdir()
        for name in capture.READ_COMMANDS.values():
            (target / (name + '.bin')).write_bytes((RAW / (name + '.bin')).read_bytes())
        if firmware is not None:
            (target / 'firmware.bin').write_bytes(firmware)
        return target

    def test_verified_602_full_configuration_and_layout(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = self.make_capture(Path(tmp)/'capture', self.fixture_602())
            decoded = decode_capture(directory)
            self.assertEqual(decoded['identity']['firmware'], '6.02')
            self.assertEqual(decoded['identity']['hardware'], '75_300_R2')
            validation = validate_snapshot(directory)
            for name, count, signature in [('motor_configuration',189,'2e43a161'),
                                           ('app_configuration',187,'1d003a2c')]:
                self.assertEqual(validation[name]['field_count'], count)
                self.assertEqual(validation[name]['signature_hex'], signature)
                self.assertEqual(decoded[name]['schema_version'], '6.00')
                self.assertEqual(decoded[name]['firmware_version'], '6.02')

    def test_both_schemas_and_exact_lengths_required_for_602(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = self.make_capture(Path(tmp)/'capture', self.fixture_602())
            for name in ('motor_configuration', 'app_configuration'):
                path = directory / (name + '.bin')
                raw = path.read_bytes()
                for invalid in (raw[:-1], raw+b'\x00', raw[:1]+b'\x00'*4+raw[5:]):
                    with self.subTest(name=name, size=len(invalid)):
                        path.write_bytes(invalid)
                        with self.assertRaises(ValueError):
                            validate_snapshot(directory)
                path.write_bytes(raw)
            telemetry = directory / 'telemetry.bin'
            raw = telemetry.read_bytes()
            for invalid in (raw[:-1], raw+b'\x00'):
                telemetry.write_bytes(invalid)
                with self.assertRaises(ValueError):
                    validate_snapshot(directory)

    def test_identity_version_and_layout_are_explicit(self):
        good = self.fixture_602()
        verified_identity(good)
        for invalid in (good[:2]+b'\x03'+good[3:], good[:-1], good+b'\x00', good[:10]):
            with self.assertRaises(ValueError):
                verified_identity(invalid)
        zero_uuid = bytearray(good)
        start = good.index(0, 3)+1
        zero_uuid[start:start+12] = bytes(12)
        with self.assertRaises(ValueError):
            verified_identity(bytes(zero_uuid))

    def test_baseline_bitfields_are_sets_not_enum_indices(self):
        data = decode_capture(RAW)['app_configuration']
        self.assertNotIn('app_adc_conf.buttons', data['enum_labels'])
        self.assertNotIn('can_status_msgs_r2', data['enum_labels'])
        self.assertEqual(data['bitfield_labels']['app_adc_conf.buttons'], [])
        self.assertEqual(data['bitfield_labels']['can_status_msgs_r2'], [])
        self.assertEqual(data['bitfield_labels']['can_status_msgs_r1'],
                         ['Status 1', 'Status 2', 'Status 3', 'Status 4'])
        self.assertEqual(data['bitfield_unknown_bits'], {})

    def test_bitfield_multiple_and_unknown_bits_are_preserved(self):
        xml = ('<ConfigParams><Params><flags><type>6</type><enumNames>A</enumNames>'
               '<enumNames>B</enumNames></flags><mode><type>4</type>'
               '<enumNames>Off</enumNames><enumNames>On</enumNames></mode></Params>'
               '<SerOrder><s>flags</s><s>mode</s></SerOrder></ConfigParams>')
        signature = crc32c(b'flags60ABmode40OffOn')
        with tempfile.TemporaryDirectory() as tmp:
            schema = Path(tmp)/'test.xml'
            schema.write_text(xml)
            decoded = decode_configuration(b'\x11'+signature.to_bytes(4,'big')+b'\x83\x01', schema, 17)
            self.assertEqual(decoded['values']['flags'], 0x83)
            self.assertEqual(decoded['bitfield_labels']['flags'], ['A','B'])
            self.assertEqual(decoded['bitfield_unknown_bits']['flags'], 0x80)
            self.assertEqual(decoded['enum_labels'], {'mode':'On'})

    def test_pinned_602_compatibility_evidence_matches_local_layout(self):
        evidence = json.loads((ROOT/'third_party/vesc_tool/compatibility-6.02.json').read_text())
        for kind, expected in evidence['schemas'].items():
            schema = SCHEMA / ('parameters_'+kind+'.xml')
            self.assertEqual(hashlib.sha256(schema.read_bytes()).hexdigest(), expected['reused_600_sha256'])
            root = ET.parse(schema).getroot()
            params = {x.tag:x for x in root.find('Params')}
            order = [x.text for x in root.find('SerOrder')]
            layout = [(name, params[name].findtext('type','0'), params[name].findtext('vTx','0'),
                       params[name].findtext('vTxDoubleScale'),
                       [x.text or '' for x in params[name].findall('enumNames')]) for name in order]
            canonical = json.dumps(layout, separators=(',',':'), ensure_ascii=False).encode()
            self.assertEqual(hashlib.sha256(canonical).hexdigest(), expected['wire_layout_sha256'])
            self.assertEqual(len(order), expected['field_count'])


class CaptureCliTests(unittest.TestCase):
    def run_mock_capture(self, directory, payloads, error=None):
        # Every serial-system call is mocked: this test cannot open a port.
        with ExitStack() as stack:
            stack.enter_context(patch.object(sys, 'argv', ['capture.py','--port','/never/open','--out',str(directory)]))
            stack.enter_context(patch.object(capture.os, 'open', return_value=123))
            writes = stack.enter_context(patch.object(capture.os, 'write', side_effect=lambda fd,b:len(b)))
            stack.enter_context(patch.object(capture.os, 'close'))
            stack.enter_context(patch.object(capture.termios, 'tcgetattr', side_effect=lambda fd:[0,0,0,0,0,0,[]]))
            stack.enter_context(patch.object(capture.termios, 'tcsetattr'))
            stack.enter_context(patch.object(capture.tty, 'setraw'))
            stack.enter_context(patch.object(capture, 'receive', side_effect=payloads))
            stack.enter_context(patch.object(capture.time, 'sleep'))
            stack.enter_context(redirect_stdout(io.StringIO()))
            if error:
                with self.assertRaises(error):
                    capture.main()
            else:
                capture.main()
            return json.loads((directory/'manifest.json').read_text()), [call.args[1] for call in writes.call_args_list]

    def payloads(self):
        return [CompatibilityTests.fixture_602()] + [
            (RAW/(capture.READ_COMMANDS[c]+'.bin')).read_bytes() for c in (4,14,17)]

    def test_complete_requires_all_verified_reads(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)/'capture'
            manifest, writes = self.run_mock_capture(directory, self.payloads())
            self.assertTrue(manifest['capture_complete'])
            self.assertEqual(writes, [query_frame(c) for c in (0,4,14,17)])
            self.assertEqual(len(manifest['configuration_validation']), 2)
            self.assertEqual(len(manifest['queries']), 4)
            for query in manifest['queries']:
                data = (directory/(query['name']+'.bin')).read_bytes()
                self.assertEqual(query['sha256'], hashlib.sha256(data).hexdigest())

    def test_invalid_app_never_becomes_complete(self):
        payloads = self.payloads()
        payloads[-1] = payloads[-1][:-1]
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)/'capture'
            manifest, writes = self.run_mock_capture(directory, payloads, ValueError)
            self.assertFalse(manifest['capture_complete'])
            self.assertIn('Truncated', manifest['error'])
            self.assertEqual(writes, [query_frame(c) for c in (0,4,14,17)])
            self.assertEqual((directory/'app_configuration.bin').read_bytes(), payloads[-1])

    def test_unsupported_firmware_stops_after_identity(self):
        raw = self.payloads()[0]
        with tempfile.TemporaryDirectory() as tmp:
            manifest, writes = self.run_mock_capture(Path(tmp)/'capture', [raw[:2]+b'\x03'+raw[3:]], ValueError)
            self.assertFalse(manifest['capture_complete'])
            self.assertEqual(writes, [query_frame(0)])
            self.assertEqual(manifest['identity']['firmware'], '6.03')

    def test_partial_read_retains_incomplete_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest, writes = self.run_mock_capture(Path(tmp)/'capture', [self.payloads()[0], TimeoutError('no reply')], TimeoutError)
            self.assertFalse(manifest['capture_complete'])
            self.assertEqual(len(manifest['queries']), 1)
            self.assertEqual(writes, [query_frame(0),query_frame(4)])


if __name__ == '__main__':
    unittest.main()
