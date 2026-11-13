#!/usr/bin/env python3
"""Fixed RX-filter lifecycle controller; no motor commands.

Requires separately reviewed/loaded definitions. Never loads/redefines, resets,
writes flash/configuration, retries, or performs automatic cleanup. STOP stops
the filter worker and holds its last direction; it does NOT stop the motor.
"""
import argparse
import binascii
import datetime
import hashlib
import json
import math
import os
from pathlib import Path
import re
import select
import struct
import sys
import time

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
from capture import PacketParser
from decode import decode_configuration, decode_telemetry, DEFAULT_SCHEMA
from read_lisp import SerialConnection, require_identity
from rx_probe import Capture, context_summary, printed_text

UUID = '37004e000951343037353739'
APP_SHA256 = '2f666b2e9eb8130251b6ba3a6aea3da28f5416e3d3e3ec56883507f65abf185d'
CANDIDATE_SHA256 = '1f49ab2370b5a5960723efd3e0a0b62dd1a9fd5549a2ed21ba9b1281b2def21f'
DEPLOYMENT_SHA256 = 'd530aeb20c81c185e25ba9b4954473a8bd7069fe5b59b1babeca3ca2b89e94dc'
EXPRESSIONS = {
    'contexts': b':ctxs',
    'status': (b"(print (list 'gk-rx-status gk-rx-filter-run gk-rx-filter-active "
               b"gk-rx-filter-pid gk-rx-filter-applied (gpio-read 'pin-rx) "
               b"(get-adc-decoded 0) (get-rpm) (get-fault)))"),
    'start': b"(print (list 'gk-rx-start-result (gk-rx-filter-start t)))",
    'stop': b"(print (list 'gk-rx-stop-result (gk-rx-filter-stop)))",
    'rollback': b"(print (list 'gk-rx-rollback-result (gk-rx-filter-rollback t)))",
}
READS = {'identity': 0, 'telemetry': 4, 'motor': 14, 'app': 17}
NUMBER = r'[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?'
FLOAT = r'(?:' + NUMBER + r'|\{' + NUMBER + r'\})'


def payload(action):
    if action in READS:
        return bytes((READS[action],))
    if action in EXPRESSIONS:
        return b'\x8a' + EXPRESSIONS[action] + b'\0'
    raise ValueError('Only fixed reads and explicit status/start/stop/rollback are allowed')


def frame(action):
    data = payload(action)
    if len(data) > 512:
        raise ValueError('Fixed expression exceeds pinned packet ceiling')
    header = bytes((2, len(data))) if len(data) < 256 else b'\x03' + struct.pack('>H', len(data))
    return header + data + struct.pack('>H', binascii.crc_hqx(data, 0)) + b'\x03'


def parse_status(packets):
    pattern = (r'\(gk-rx-status (nil|t) (nil|t) (-?[0-9]+) (-1|0|1) ([01]) (' +
               FLOAT + r') (' + FLOAT + r') ([0-9]+)\)')
    matches = [re.fullmatch(pattern, line.strip()) for line in printed_text(packets).splitlines()]
    matches = [match for match in matches if match]
    if len(matches) != 1:
        raise ValueError('No unique complete RX-filter status record')
    match = matches[0]
    adc, rpm = (float(value[1:-1] if value.startswith('{') else value) for value in (match[6], match[7]))
    if not math.isfinite(adc) or not math.isfinite(rpm):
        raise ValueError('Nonfinite status data')
    return {'run': match[1] == 't', 'active': match[2] == 't', 'pid': int(match[3]),
            'applied': int(match[4]), 'rx': int(match[5]), 'adc': adc, 'erpm': rpm,
            'fault': int(match[8])}


def at_rest(status):
    return 0 <= status['adc'] <= 0.12 and abs(status['erpm']) <= 50 and status['fault'] == 0


def require_app(raw):
    if hashlib.sha256(raw).hexdigest() != APP_SHA256:
        raise ValueError('Full application payload differs from the reviewed unchanged calibration/settings')
    decoded = decode_configuration(raw, DEFAULT_SCHEMA / 'parameters_appconf.xml', 17)
    values = decoded['values']
    expected = {'app_to_use': 2, 'app_adc_conf.ctrl_type': 3, 'app_adc_conf.buttons': 0,
                'servo_out_enable': 0, 'app_adc_conf.safe_start': 1,
                'app_adc_conf.hyst': 0.15000000596046448}
    if len(values) != 187 or any(values.get(key) != value for key, value in expected.items()):
        raise ValueError('Native application guard failed')
    return decoded


class Wire:
    def __init__(self, fd, output):
        self.fd, self.output = fd, output
        self.parser, self.queue = PacketParser(), []
        self.last_rx = time.monotonic()
        self.deadline = self.last_rx + 40.0
        self.received = 0

    def record(self, **item):
        item['monotonic'] = time.monotonic()
        with (self.output / 'wire.jsonl').open('a') as out:
            out.write(json.dumps(item) + '\n')

    def send(self, action):
        if time.monotonic() >= self.deadline:
            raise TimeoutError('Session expired before send')
        if self.queue or self.parser.buffer:
            raise ValueError('Pending/partial serial data before command; no send')
        data = frame(action)
        self.record(kind='tx_attempt', action=action, frame_hex=data.hex())
        with (self.output / 'tx-attempts.bin').open('ab') as out:
            out.write(data)
        count = os.write(self.fd, data)
        self.record(kind='tx_return', count=count)
        if count != len(data):
            raise IOError('Partial/uncertain send; never append, retry or clean up automatically')

    def packet(self, deadline):
        deadline = min(deadline, self.deadline)
        while time.monotonic() < deadline:
            if self.queue:
                return self.queue.pop(0)
            ready, _, _ = select.select([self.fd], [], [], max(0, min(0.2, deadline - time.monotonic())))
            if not ready:
                continue
            try:
                raw = os.read(self.fd, 4096)
            except BlockingIOError:
                continue
            if not raw:
                raise IOError('Serial EOF')
            self.last_rx = time.monotonic()
            with (self.output / 'rx-wire.bin').open('ab') as out:
                out.write(raw)
            self.record(kind='rx_chunk', hex=raw.hex())
            self.received += len(raw)
            if self.received > 128 * 1024:
                raise IOError('RX byte budget exceeded')
            self.queue.extend(self.parser.feed(raw))
            for data in self.queue:
                self.record(kind='crc_valid_packet', payload_hex=data.hex())
        return None

    def query(self, action):
        self.send(action)
        deadline = time.monotonic() + 3.0
        while time.monotonic() < deadline:
            data = self.packet(deadline)
            if data is None:
                break
            if data[0] == READS[action]:
                return data
            if data[0] not in (135, 138):
                raise ValueError('Unexpected read response')
        raise TimeoutError('Read response missing; no retry')

    def expression(self, action, seconds=1.0):
        self.send(action)
        deadline = time.monotonic() + seconds
        result = Capture()
        while time.monotonic() < deadline:
            data = self.packet(deadline)
            if data is None:
                break
            if data[0] not in (135, 138):
                raise ValueError('Unexpected control response during REPL capture')
            result.append(data)
        result.quiet_tail_seconds = max(0, time.monotonic() - self.last_rx)
        result.pending_bytes = len(self.parser.buffer)
        if result.pending_bytes:
            raise ValueError('Incomplete reply frame; command outcome uncertain')
        return result


def run(port, output, action, *, setup_confirmed=False, loaded_reviewed=False, expected_rx=None,
        connection_factory=SerialConnection, wire_factory=Wire):
    if action not in ('status', 'start', 'stop', 'rollback'):
        raise ValueError('Unsupported lifecycle action')
    if action != 'status' and (not loaded_reviewed or not re.fullmatch(r'[0-9a-f]{64}', CANDIDATE_SHA256)):
        raise ValueError('Reviewed fixed candidate load required before lifecycle action')
    if action in ('start', 'rollback') and (not setup_confirmed or type(expected_rx) is not int or expected_rx not in (0, 1)):
        raise ValueError('Fresh supervised setup and expected RX level required')
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    manifest = {'action': action, 'uuid_pin': UUID, 'firmware_pin': '6.02', 'app_sha256': APP_SHA256,
                'candidate_sha256': CANDIDATE_SHA256, 'deployment_sha256': DEPLOYMENT_SHA256,
                'deployment_sha256_scope': 'Exact compact candidate core; optional persistent startup wrapper is verified separately',
                'stored_program_verified_here': False,
                'loaded_source_readback_verified_here': False, 'complete': False, 'lifecycle_sent': False,
                'setup_confirmed': setup_confirmed, 'loaded_reviewed': loaded_reviewed,
                'expected_rx': expected_rx, 'native_detach_independently_readable': False,
                'stop_meaning': 'stop filter worker; hold last direction; NOT motor stop',
                'started_utc': datetime.datetime.now(datetime.timezone.utc).isoformat()}
    def save():
        (output / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    def raw_read(wire, name, stage):
        data = wire.query(name)
        (output / f'{name}_{stage}.bin').write_bytes(data)
        return data
    def state(wire, stage):
        value = parse_status(wire.expression('status'))
        context_packets = wire.expression('contexts')
        summary = context_summary(context_packets)
        if not (summary['all_context_headings_seen_in_order'] and summary['quiet_tail_at_least_250ms'] and summary['no_partial_frame']):
            raise ValueError('Incomplete context snapshot')
        pids = [int(re.search(r'ContextID:\s*([0-9]+)', line)[1]) for line in summary['context_id_lines']]
        manifest[f'status_{stage}'] = value
        manifest[f'contexts_{stage}'] = summary
        save()
        return value, pids
    def verify_after(wire, motor_before):
        require_app(raw_read(wire, 'app', 'after'))
        if raw_read(wire, 'motor', 'after') != motor_before:
            raise ValueError('Motor configuration changed during lifecycle session')
        manifest['identity_after'] = require_identity(raw_read(wire, 'identity', 'after'), UUID)
        if manifest['identity_after']['hardware'] != manifest['identity_before']['hardware']:
            raise ValueError('Hardware identity changed')
        manifest['after_settings_verified'] = True
        save()

    try:
        save()
        with connection_factory(port) as connection:
            wire = wire_factory(connection.fd, output)
            manifest['identity_before'] = require_identity(raw_read(wire, 'identity', 'before'), UUID)
            require_app(raw_read(wire, 'app', 'before'))
            motor_before = raw_read(wire, 'motor', 'before')
            before, pids_before = state(wire, 'before')
            if action == 'start':
                if before['run'] or before['active'] or before['pid'] != -1 or before['applied'] != -1 or pids_before:
                    raise ValueError('Not a clean disarmed candidate/runtime; no start')
                if not at_rest(before) or before['rx'] != expected_rx:
                    raise ValueError('Pedal/RPM/fault/RX guard failed; no start')
                manifest['start_telemetry'] = []
                for index in range(4):
                    sample = decode_telemetry(raw_read(wire, 'telemetry', f'prestart_{index}'))
                    manifest['start_telemetry'].append(sample)
                    save()
                    if sample['fault_code'] != 0 or abs(sample['erpm']) > 50:
                        raise ValueError('One of four stationary telemetry samples failed; no start')
                    if index < 3:
                        time.sleep(0.1)
                # Last fixed input read immediately before the explicit start.
                fresh = parse_status(wire.expression('status'))
                if not at_rest(fresh) or fresh['rx'] != expected_rx or any(fresh[key] != before[key] for key in ('run', 'active', 'pid', 'applied')):
                    raise ValueError('Fresh input/lifecycle preflight changed; no start')
            elif action == 'rollback':
                if before['run'] or not before['active'] or before['pid'] != -1 or before['applied'] not in (0, 1):
                    raise ValueError('Rollback requires a joined worker and held override')
                if not at_rest(before) or before['rx'] != expected_rx or before['rx'] != 1 - before['applied']:
                    raise ValueError('Rollback requires matching raw switch at rest')
            if action != 'status':
                require_app(raw_read(wire, 'app', 'preaction'))
                manifest['lifecycle_sent'] = True  # Attempt may reach the controller even if write raises.
                save()
                replies = wire.expression(action, seconds=3.0)
                lines = printed_text(replies).splitlines()
                manifest['lifecycle_lines'] = lines
                pattern = r'\(gk-rx-' + action + r'-result ([0-9]+|t|nil)\)'
                matches = [re.fullmatch(pattern, line.strip()) for line in lines]
                results = [match[1] for match in matches if match]
                if len(results) != 1 or (action == 'start' and not results[0].isdigit()) or (action != 'start' and results[0] != 't'):
                    raise RuntimeError('No unique successful lifecycle result; outcome uncertain, no retry/cleanup')
                after, pids_after = state(wire, 'after')
                verify_after(wire, motor_before)
                if action == 'start':
                    if not (after['run'] and after['active'] and after['pid'] == int(results[0]) and after['pid'] in pids_after and after['applied'] == 1 - expected_rx):
                        manifest['start_warning'] = 'Worker may be running and can qualify later; do not drive or automatically retry/stop'
                        raise RuntimeError('Start not verified as armed with the expected direction and live worker')
                elif action == 'stop':
                    if after['run'] or after['pid'] != -1 or after['active'] != before['active'] or after['applied'] != before['applied']:
                        raise RuntimeError('Stop/join/held direction not verified')
                elif after['run'] or after['active'] or after['pid'] != -1 or after['applied'] != -1:
                    raise RuntimeError('Raw-input rollback not verified')
            if action == 'status':
                verify_after(wire, motor_before)
            manifest['complete'] = True
    except BaseException as error:
        manifest['error'] = f'{type(error).__name__}: {error}'
        if manifest['lifecycle_sent']:
            manifest['state_after_failure'] = 'May have changed; preserve last state, inspect, do not repeat or auto-rollback'
        raise
    finally:
        manifest['finished_utc'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        save()
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('status', 'start', 'stop', 'rollback'))
    parser.add_argument('--port', required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--loaded-reviewed', action='store_true')
    parser.add_argument('--setup-confirmed', action='store_true')
    parser.add_argument('--expected-rx', type=int, choices=(0, 1))
    args = parser.parse_args()
    print(json.dumps(run(args.port, args.out, args.action, loaded_reviewed=args.loaded_reviewed,
                         setup_confirmed=args.setup_confirmed, expected_rx=args.expected_rx), indent=2))


if __name__ == '__main__':
    main()
