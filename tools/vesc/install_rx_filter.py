#!/usr/bin/env python3
"""Fixed kart-3 persistent Lisp installer; default is offline plan only.

Default is offline plan only. --apply requires supervised setup and a successful
root-operated stop/rollback manifest. Erase resets Lisp; flash operations briefly
inhibit motor output. Writes only the fixed reviewed empty-sector package, never
motor/app settings. No activation/reset command, retry or automatic cleanup.
The valid package will run on a normal future boot (watchdog startup may suppress it).
"""
import argparse
import binascii
import datetime
import hashlib
import json
import os
from pathlib import Path
import struct
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import rx_filter_control as control
from read_lisp import SerialConnection, require_identity, parse_code_reply
from decode import decode_configuration, decode_telemetry, DEFAULT_SCHEMA
from rx_probe import context_summary

SOURCE = ROOT / 'firmware/vesc-lisp/reverse-input/rx-filter-autostart.lisp'
SOURCE_SHA256 = '30981ff45663d254153009ec0f6258b400126afd74a66a6caa2a70c56ac96700'
SOURCE_BYTES = 3981
BLOB_SHA256 = 'a2461adda272a014506cc76f0bdbf2240c85dff39842c6dac8655b4e0be34801'
IMAGE_SHA256 = '428657a58bc6d4a2a0e85df858e36fc7d34972007d7df436ed236632a9a19495'
BLOB_BYTES = 3984
IMAGE_BYTES = 3992
MOTOR_SHA256 = 'ab486bff0406bd7b84c0932160a4387e6862b7dee754ed38f4cc5dc7515a7b71'
SECTOR_BYTES = 131072
CHUNK = 256
BODY_OFFSETS = tuple(range(8, IMAGE_BYTES, CHUNK))
WRITE_OFFSETS = BODY_OFFSETS + (0,)
READ_COMMANDS = {'identity': 0, 'telemetry': 4, 'motor': 14, 'app': 17}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def package():
    source = SOURCE.read_bytes()
    if len(source) != SOURCE_BYTES or digest(source) != SOURCE_SHA256:
        raise ValueError('Fixed autostart source length/hash mismatch')
    blob = source + b'\0\0\0'  # Code terminator and uint16 import_count=0.
    if len(blob) != BLOB_BYTES or digest(blob) != BLOB_SHA256:
        raise ValueError('Fixed code blob length/hash mismatch')
    if not blob.endswith(b'\0\0\0') or b'\0' in blob[:-3]:
        raise ValueError('Expected ASCII source, one NUL, and zero imports')
    blob[:-3].decode('ascii')
    flags = b'\0\0'
    crc = binascii.crc_hqx(flags + blob, 0)
    image = struct.pack('>IH', len(blob), crc) + flags + blob
    if len(image) != IMAGE_BYTES or digest(image) != IMAGE_SHA256:
        raise ValueError('Fixed complete image hash mismatch')
    return image


def payload(action, offset=0, length=0):
    if type(offset) is not int or type(length) is not int:
        raise ValueError('Offsets/lengths must be integers')
    if action in READ_COMMANDS and offset == length == 0:
        return bytes((READ_COMMANDS[action],))
    if action in ('status', 'contexts') and offset == length == 0:
        return control.payload(action)
    if action == 'read' and 0 <= length <= CHUNK and 0 <= offset <= BLOB_BYTES and offset + length <= BLOB_BYTES and (length > 0 or offset == 0):
        return b'\x82' + struct.pack('>ii', length, offset)
    if action == 'erase' and offset == length == 0:
        return b'\x84' + struct.pack('>i', IMAGE_BYTES)
    if action == 'write' and offset in WRITE_OFFSETS and length == 0:
        image = package()
        if offset >= 8:
            data = image[offset:min(offset + CHUNK, IMAGE_BYTES)]
        else:
            data = image[:8]
        if not data or len(data) > CHUNK or not 0 <= offset < SECTOR_BYTES or offset + len(data) > SECTOR_BYTES:
            raise ValueError('Write outside fixed package/sector bounds')
        return b'\x83' + struct.pack('>I', offset) + data
    raise ValueError('Only fixed preflight reads, bounded blob reads, one erase and exact package writes allowed')


def frame(action, offset=0, length=0):
    data = payload(action, offset, length)
    if len(data) > 512:
        raise ValueError('Packet too large')
    header = bytes((2, len(data))) if len(data) < 256 else b'\x03' + struct.pack('>H', len(data))
    return header + data + struct.pack('>H', binascii.crc_hqx(data, 0)) + b'\x03'


def check_ack(action, data, offset=0):
    expected = b'\x84\x01' if action == 'erase' else b'\x83\x01' + struct.pack('>I', offset)
    if action not in ('erase', 'write') or data != expected:
        raise ValueError('Missing/rejected/wrong-offset/malformed flash ACK; never retry or activate')


def require_target(raw):
    identity = require_identity(raw, control.UUID)
    if identity.get('hardware') != '75_300_R2' or identity.get('test_version') != 0 or identity.get('firmware_name') != 'no_hw_limits':
        raise ValueError('Only exact 6.02 / 75_300_R2 / no_hw_limits release build is supported')
    return identity


def require_motor(raw):
    if digest(raw) != MOTOR_SHA256:
        raise ValueError('Whole motor configuration differs from successful trial; refusing changes')
    result = decode_configuration(raw, DEFAULT_SCHEMA / 'parameters_mcconf.xml', 14)
    if len(result['values']) != 189:
        raise ValueError('Incomplete motor schema')
    return result


def require_rollback(path):
    path = Path(path)
    result = json.loads(path.read_text())
    if result.get('action') != 'rollback' or result.get('complete') is not True or result.get('lifecycle_sent') is not True:
        raise ValueError('Successful explicit root-operated rollback evidence required')
    state = result.get('status_after', {})
    if any(state.get(key) != value for key, value in {'run': False, 'active': False, 'pid': -1, 'applied': -1, 'rx': 1}.items()):
        raise ValueError('Rollback evidence does not show restored raw forward input')
    for phase in ('before', 'after'):
        ident = result.get('identity_' + phase, {})
        if ident.get('uuid') != control.UUID or ident.get('firmware') != '6.02':
            raise ValueError('Rollback identity mismatch')
    control.require_app((path.parent / 'app_after.bin').read_bytes())
    require_motor((path.parent / 'motor_after.bin').read_bytes())
    return {'path': str(path), 'sha256': digest(path.read_bytes()), 'finished_utc': result.get('finished_utc')}


class Wire(control.Wire):
    def __init__(self, fd, output):
        super().__init__(fd, output)
        self.deadline = time.monotonic() + 120
        self.erase_deadline = None
    def send(self, action, offset=0, length=0):
        if time.monotonic() >= self.deadline or self.queue or self.parser.buffer:
            raise ValueError('Expired or unsynchronized session; nothing further sent')
        if action == 'erase' and (self.erase_deadline is None or time.monotonic() > self.erase_deadline):
            raise TimeoutError('Fresh pre-erase safety window expired; erase not sent')
        data = frame(action, offset, length)
        self.record(kind='tx_attempt', action=action, offset=offset, length=length, frame_hex=data.hex())
        with (self.output / 'tx-attempts.bin').open('ab') as out:
            out.write(data)
        if action == 'erase' and time.monotonic() > self.erase_deadline:
            self.record(kind='erase_not_sent', reason='safety window expired during journaling')
            raise TimeoutError('Fresh pre-erase safety window expired before write')
        count = os.write(self.fd, data)
        self.record(kind='tx_return', count=count)
        if count != len(data):
            raise IOError('Partial/uncertain flash request; no append, retry, reset or activation')
    def query(self, action, offset=0, length=0):
        self.send(action, offset, length)
        command = payload(action, offset, length)[0]
        deadline = time.monotonic() + (8 if action == 'erase' else 3)
        while time.monotonic() < deadline:
            data = self.packet(deadline)
            if data is None:
                break
            if data[0] == command:
                return data
            if data[0] not in (135, 138):
                raise ValueError('Unexpected response; refusing another command')
        raise TimeoutError('No CRC-valid response; state uncertain, never retry')


def install(port, output, rollback_manifest, *, apply=False, supervised=False,
            connection_factory=SerialConnection, wire_factory=Wire):
    image = package()
    plan = {'target_uuid': control.UUID, 'firmware': '6.02', 'blob_sha256': BLOB_SHA256,
            'image_sha256': IMAGE_SHA256, 'blob_bytes': BLOB_BYTES, 'image_bytes': IMAGE_BYTES,
            'flags': 0, 'write_offsets': list(WRITE_OFFSETS), 'activation_command_available': False,
            'normal_future_boot_runs_valid_code': True, 'power_fail_atomic': False}
    if not apply:
        return {'offline_only': True, **plan}
    if not supervised:
        raise ValueError('Fresh supervised wheels-up/pedal-released/cutoff setup required')
    rollback = require_rollback(rollback_manifest)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    (output / 'planned-image.bin').write_bytes(image)
    manifest = {**plan, 'rollback_evidence': rollback, 'apply': True, 'supervised': True,
                'phase': 'preflight', 'complete': False, 'flash_attempts': [],
                'settings_written': False, 'activation_sent': False,
                'started_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
                'native_detach_independently_readable': False,
                'header_flags_read_back_independently': False}
    def save():
        (output / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    def read(wire, action, label, offset=0, length=0):
        data = wire.query(action, offset, length)
        (output / f'{label}.bin').write_bytes(data)
        return data
    def mutate(wire, action, offset=0):
        manifest['phase'] = action + '_attempted'
        manifest['flash_attempts'].append({'action': action, 'offset': offset, 'request_frame_hex': frame(action, offset).hex()})
        save()
        response = read(wire, action, f'ack_{len(manifest["flash_attempts"]):03d}', offset)
        check_ack(action, response, offset)
        manifest['flash_attempts'][-1]['ack_verified'] = True
        save()
    def empty_blob(wire, label):
        total, data = parse_code_reply(read(wire, 'read', label), 0, 0)
        if total != 0 or data:
            raise ValueError('Existing valid Lisp code: refusing erase/install')
        return {'status': 'no_valid_blob', 'reported_bytes': 0,
                'not_a_raw_blank_flash_backup': True}
    try:
        save()
        with connection_factory(port) as connection:
            wire = wire_factory(connection.fd, output)
            manifest['identity_before'] = require_target(read(wire, 'identity', 'identity_before'))
            app_before = read(wire, 'app', 'app_before')
            motor_before = read(wire, 'motor', 'motor_before')
            control.require_app(app_before)
            require_motor(motor_before)
            manifest['preflight_samples'] = []
            for index in range(4):
                value = decode_telemetry(read(wire, 'telemetry', f'telemetry_{index}'))
                status = control.parse_status(wire.expression('status'))
                if value['fault_code'] != 0 or abs(value['erpm']) > 50 or not control.at_rest(status):
                    raise ValueError('Not at rest/fault-free in released pedal region')
                if status['run'] or status['active'] or status['pid'] != -1 or status['applied'] != -1 or status['rx'] != 1:
                    raise ValueError('Candidate must be stopped and raw forward RX restored')
                manifest['preflight_samples'].append({'telemetry': value, 'status': status})
                save()
            contexts = context_summary(wire.expression('contexts'))
            if contexts['snapshot'] != 'no_contexts_reported':
                raise ValueError('Live or unknown Lisp contexts; refusing erase')
            manifest['contexts_before'] = contexts
            if read(wire, 'app', 'app_preerase') != app_before or read(wire, 'motor', 'motor_preerase') != motor_before:
                raise ValueError('Configuration changed before erase')
            preerase_started = time.monotonic()
            final_status = control.parse_status(wire.expression('status', seconds=0.3))
            final_values = decode_telemetry(read(wire, 'telemetry', 'telemetry_final_preerase'))
            if final_values['fault_code'] != 0 or abs(final_values['erpm']) > 50 or not control.at_rest(final_status):
                raise ValueError('Final stationary/pedal/fault check failed before erase')
            if final_status['run'] or final_status['active'] or final_status['pid'] != -1 or final_status['applied'] != -1 or final_status['rx'] != 1:
                raise ValueError('Final disarmed/raw-forward check failed before erase')
            manifest['final_preerase_sample'] = {'telemetry': final_values, 'status': final_status}
            manifest['stored_before'] = empty_blob(wire, 'stored_before')
            wire.erase_deadline = preerase_started + 0.75
            manifest['final_preerase_window_seconds'] = time.monotonic() - preerase_started
            save()
            if time.monotonic() > wire.erase_deadline:
                raise TimeoutError('Final safety/blob reads exceeded 750 ms; erase not sent')
            # Last empty-code read and fresh input check share one bounded 750 ms window.
            mutate(wire, 'erase')
            manifest['stored_after_erase'] = empty_blob(wire, 'stored_after_erase')
            for offset in WRITE_OFFSETS:
                mutate(wire, 'write', offset)
            manifest['phase'] = 'readback'
            save()
            total, _ = parse_code_reply(read(wire, 'read', 'stored_size_after'), 0, 0)
            if total != BLOB_BYTES:
                raise ValueError('Stored code is invalid or has unexpected length')
            collected = bytearray()
            for offset in range(0, BLOB_BYTES, CHUNK):
                count = min(CHUNK, BLOB_BYTES - offset)
                _, data = parse_code_reply(read(wire, 'read', f'readback_{offset:05d}', offset, count), count, offset, BLOB_BYTES)
                collected.extend(data)
            (output / 'code-readback.bin').write_bytes(collected)
            if bytes(collected) != image[8:] or digest(collected) != BLOB_SHA256:
                raise ValueError('Stored payload differs from exact reviewed package')
            parse_code_reply(read(wire, 'read', 'stored_size_recheck'), 0, 0, BLOB_BYTES)
            app_after = read(wire, 'app', 'app_after')
            motor_after = read(wire, 'motor', 'motor_after')
            control.require_app(app_after)
            require_motor(motor_after)
            if app_after != app_before or motor_after != motor_before:
                raise ValueError('Configuration changed during persistence')
            manifest['identity_after'] = require_target(read(wire, 'identity', 'identity_after'))
            if manifest['identity_after']['hardware'] != manifest['identity_before']['hardware']:
                raise ValueError('Hardware target changed')
            manifest.update({'phase': 'stored_verified_not_activated', 'complete': True,
                             'readback_sha256': digest(collected), 'all_376_settings_preserved': True,
                             'boot_acceptance': 'pending owner-controlled physical power cycle'})
    except BaseException as error:
        manifest['error'] = f'{type(error).__name__}: {error}'
        manifest['failure_policy'] = 'No further sends, retry, reset, activation or cleanup. Flash/runtime state may be partial.'
        raise
    finally:
        manifest['finished_utc'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        save()
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--supervised', action='store_true')
    parser.add_argument('--port')
    parser.add_argument('--out', type=Path)
    parser.add_argument('--rollback-manifest', type=Path)
    args = parser.parse_args()
    if args.apply and (not args.port or not args.out or not args.rollback_manifest):
        parser.error('--apply requires explicit --port, --out and --rollback-manifest')
    print(json.dumps(install(args.port, args.out, args.rollback_manifest, apply=args.apply,
                             supervised=args.supervised), indent=2))


if __name__ == '__main__': main()
