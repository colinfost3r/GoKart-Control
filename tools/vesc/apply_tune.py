#!/usr/bin/env python3
"""Validate the fixed kart-3 trial; explicitly opted-in application writes MCCONF once.

Default: offline validation only. This is a separate, narrow writer: capture.py's
read allowlist is unchanged. Never sends APPCONF, motor, reset, or detection commands.
"""
import argparse
import binascii
import datetime
import fcntl
import json
import os
from pathlib import Path
import select
import termios
import time
import tty

from capture import MAX_PAYLOAD, PacketParser, READ_COMMANDS, query_frame, verified_identity
from compare import compare_decoded
from decode import DEFAULT_SCHEMA, decode_payloads
import tune

SET_MCCONF = 13
APP_SCHEMA_SHA256 = '33c64b9db644b524f5a90a85d3fc76130950cb7247c33cd915aa5bd0414f2436'
READ_ORDER = (0, 14, 17, 4)  # Stationary telemetry must be the final fresh query.
MAX_TELEMETRY_AGE_S = .75
MAX_CAPTURE_AGE_S = 10.0
PLAN_KEYS = (
    'trial_format', 'operation', 'apply_supported', 'status',
    'expected_target_identity', 'expected_before_sha256',
    'proposed_motor_response_sha256', 'proposed_motor_file',
    'allowlisted_motor_fields', 'patches', 'summary', 'field_audit',
)


def utcnow():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def strict_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate JSON key: ' + key)
        result[key] = value
    return result


def write_json(path, value):
    """Replace an evidence journal atomically and flush it before any mutation."""
    path = Path(path)
    temp = path.with_name(path.name + '.tmp')
    with temp.open('w') as stream:
        stream.write(json.dumps(value, indent=2, allow_nan=False) + '\n')
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temp, path)


def source_hashes(directory):
    files = [directory/'trial.json', directory/'proposed_motor_response.bin']
    for side in ('reference', 'before'):
        files += [directory/side/'manifest.json']
        files += [directory/side/(name + '.bin') for name in READ_COMMANDS.values()]
    files += [DEFAULT_SCHEMA/'parameters_mcconf.xml', DEFAULT_SCHEMA/'parameters_appconf.xml']
    return {str(path): tune.sha256(path.read_bytes()) for path in files}


def validate_trial(directory):
    """Rebuild the fixed 12-field candidate independently of the saved proposal."""
    directory = Path(directory).resolve(strict=True)
    initial_hashes = source_hashes(directory)
    if tune.sha256((DEFAULT_SCHEMA/'parameters_appconf.xml').read_bytes()) != APP_SCHEMA_SHA256:
        raise ValueError('Pinned application schema bytes changed')
    plan = json.loads((directory/'trial.json').read_text(), object_pairs_hook=strict_object,
                      parse_constant=lambda value: (_ for _ in ()).throw(ValueError('Nonfinite JSON: ' + value)))
    rebuilt, artifacts = tune.prepare(directory/'reference', directory/'before')
    for key in PLAN_KEYS:
        if plan.get(key) != rebuilt[key]:
            raise ValueError('Prepared plan does not match independent recomputation: ' + key)
    for side in ('reference', 'current'):
        if plan.get(side, {}).get('identity') != rebuilt[side]['identity']:
            raise ValueError('Prepared identity changed: ' + side)
        # Original source paths may differ after archiving; hashes and dated query
        # evidence must still be exactly the records validated from those copies.
        for key in ('manifest_sha256', 'queries'):
            if plan[side].get('provenance', {}).get(key) != rebuilt[side]['provenance'][key]:
                raise ValueError('Prepared capture provenance changed: ' + side + '/' + key)
    if (directory/'proposed_motor_response.bin').read_bytes() != artifacts['proposed_motor']:
        raise ValueError('Proposed motor bytes differ from the independently rebuilt trial')
    if source_hashes(directory) != initial_hashes:
        raise ValueError('Trial/schema files changed during validation')
    return {'directory': directory, 'plan': plan, 'artifacts': artifacts,
            'source_sha256': initial_hashes}


def require_unchanged(bundle):
    if source_hashes(bundle['directory']) != bundle['source_sha256']:
        raise ValueError('Trial/schema files changed after validation')


def motor_frame(response_payload):
    """Build only SET_MCCONF from an already validated GET_MCCONF payload."""
    tune.motor_spans(response_payload)  # Complete pinned schema; never raw arbitrary commands.
    payload = bytes([SET_MCCONF]) + response_payload[1:]
    size = len(payload)
    header = bytes([2, size]) if size < 256 else b'\x03' + size.to_bytes(2, 'big')
    return header + payload + binascii.crc_hqx(payload, 0).to_bytes(2, 'big') + b'\x03'


class SerialConnection:
    """One explicit USB port. No reconnect, reset, write retry or command queue."""
    def __init__(self, port):
        self.port = port
        self.fd = None
        self.old = None
        self.mutation_attempts = 0
        self.full_write_accepted = False
        self.safe_for_queries = True
        self.bytes_accepted = None

    def __enter__(self):
        try:
            self.fd = os.open(self.port, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
            # Prevent another process opening the same device during this transaction.
            fcntl.ioctl(self.fd, termios.TIOCEXCL)
            self.old = termios.tcgetattr(self.fd)
            tty.setraw(self.fd)
            cfg = termios.tcgetattr(self.fd)
            cfg[2] = (cfg[2] | termios.CLOCAL | termios.CREAD) & ~termios.HUPCL
            cfg[4] = cfg[5] = termios.B115200
            termios.tcsetattr(self.fd, termios.TCSANOW, cfg)
            self.discard_input()
            return self
        except BaseException:
            self.__exit__(None, None, None)
            raise

    def __exit__(self, *_):
        if self.fd is not None:
            try:
                if self.old is not None:
                    # Never restore HUPCL: closing this utility must not reset hardware.
                    self.old[2] &= ~termios.HUPCL
                    termios.tcsetattr(self.fd, termios.TCSANOW, self.old)
            finally:
                os.close(self.fd)
                self.fd = None

    def discard_input(self):
        termios.tcflush(self.fd, termios.TCIFLUSH)

    def receive(self, command, timeout=3.0):
        parser = PacketParser()
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            ready, _, _ = select.select([self.fd], [], [], max(0, min(.2, deadline-time.monotonic())))
            if not ready:
                continue
            try:
                chunk = os.read(self.fd, MAX_PAYLOAD)
            except BlockingIOError:
                continue
            if not chunk:
                raise EOFError('USB serial device closed during response')
            for payload in parser.feed(chunk):
                if payload[0] == command:
                    return payload
        raise TimeoutError(f'No CRC-valid response for command {command}; no retry attempted')

    def query(self, command):
        if not self.safe_for_queries:
            raise RuntimeError('Queries prohibited after an incomplete or uncertain serial send')
        frame = query_frame(command)  # Existing four-command read allowlist.
        self.discard_input()
        self.safe_for_queries = False
        if os.write(self.fd, frame) != len(frame):
            raise IOError('Partial read-query frame; no further commands permitted')
        self.safe_for_queries = True
        return self.receive(command)

    def set_motor_once(self, frame, latest_write_time):
        if self.mutation_attempts or not self.safe_for_queries:
            raise RuntimeError('A second or unsafe motor-configuration write is prohibited')
        parsed = PacketParser().feed(frame)
        if len(parsed) != 1 or parsed[0][0] != SET_MCCONF or motor_frame(b'\x0e' + parsed[0][1:]) != frame:
            raise ValueError('Invalid single motor-configuration frame')
        self.discard_input()  # Never accept an ACK left over before this write.
        if time.monotonic() > latest_write_time:
            raise ValueError('Fresh pre-write telemetry/configuration expired; no settings sent')
        # An exception from os.write cannot establish how many bytes reached the
        # device. Do not append recovery queries to a potentially partial frame.
        self.mutation_attempts = 1
        self.safe_for_queries = False
        self.bytes_accepted = os.write(self.fd, frame)  # Exactly ONE syscall; no remainder/retry.
        if self.bytes_accepted != len(frame):
            raise IOError('Partial persistent write; do not retry or append any commands')
        self.full_write_accepted = True
        self.safe_for_queries = True

    def receive_ack(self):
        payload = self.receive(SET_MCCONF, timeout=5.0)
        if payload != bytes([SET_MCCONF]):
            raise ValueError('Malformed SET_MCCONF acknowledgment')
        return payload


def capture_four(connection, directory, expected_identity):
    directory.mkdir()
    started = time.monotonic()
    manifest = {'started_at_utc': utcnow(), 'transport': 'usb_serial', 'port': connection.port,
                'scope': 'current_runtime_not_verified_saved_flash', 'capture_complete': False,
                'queries': [], 'procedure': 'Guarded tune readback; four read commands only'}
    payloads = {}
    telemetry_at = None
    try:
        for command in READ_ORDER:
            name = READ_COMMANDS[command]
            payload = connection.query(command)
            received = time.monotonic()
            (directory/(name + '.bin')).write_bytes(payload)
            payloads[name] = payload
            manifest['queries'].append({'command': command, 'name': name, 'crc_verified': True,
                'captured_at_utc': utcnow(), 'payload_bytes': len(payload), 'sha256': tune.sha256(payload)})
            if command == 0:
                manifest['identity'] = verified_identity(payload)
                tune.require_identity(manifest['identity'], expected_identity)
            if command == 4:
                telemetry_at = received
        decoded = decode_payloads(payloads)
        compare_decoded(decoded, decoded)  # Require all 189 + 187 supported fields.
        manifest['configuration_validation'] = {
            name: {'signature_hex': decoded[name]['signature_hex'],
                   'schema_version': decoded[name]['schema_version'],
                   'field_count': len(decoded[name]['values']),
                   'bytes_consumed': decoded[name]['bytes_consumed']}
            for name in ('motor_configuration', 'app_configuration')}
        manifest['capture_complete'] = True
        return {'payloads': payloads, 'decoded': decoded, 'started': started,
                'telemetry_at': telemetry_at, 'manifest': manifest}
    except BaseException as error:
        manifest['error'] = f'{type(error).__name__}: {error}'
        raise
    finally:
        manifest['finished_at_utc'] = utcnow()
        write_json(directory/'manifest.json', manifest)


def require_before(bundle, capture):
    for name in ('firmware', 'motor_configuration', 'app_configuration'):
        if capture['payloads'][name] != bundle['artifacts']['before'][name]:
            raise ValueError('Fresh controller bytes differ from prepared before snapshot: ' + name)
    tune.require_stationary(capture['decoded']['telemetry'])
    require_unchanged(bundle)


def verify_after(bundle, capture):
    expected = dict(bundle['artifacts']['before'])
    expected['motor_configuration'] = bundle['artifacts']['proposed_motor']
    for name in ('firmware', 'motor_configuration', 'app_configuration'):
        if capture['payloads'][name] != expected[name]:
            raise ValueError('Readback differs from the exact proposed/preserved bytes: ' + name)
    tune.require_stationary(capture['decoded']['telemetry'])
    audit = compare_decoded(decode_payloads(bundle['artifacts']['before']), capture['decoded'])
    expected_audit = bundle['plan']['field_audit']
    for name, group in audit.items():
        for row, wanted in zip(group['fields'], expected_audit[name]['fields']):
            if any(row[key] != wanted[key] for key in row):
                raise ValueError('Readback field audit differs from prepared trial')
    return audit


def run(bundle, connection, out, apply=False):
    """Run on an already-open connection; all failures retain the evidence journal."""
    out = Path(out)
    out.mkdir(parents=True, exist_ok=False)
    report = {'started_at_utc': utcnow(), 'mode': 'apply_once' if apply else 'preflight_only',
              'status': 'preflight_in_progress', 'source_sha256': bundle['source_sha256'],
              'expected_identity': tune.TARGET_IDENTITY, 'mutating_write_attempts': 0,
              'ack_verified': False, 'readback_verified': False, 'retry_performed': False,
              'rollback_performed': False, 'saved_flash_independently_verified': False,
              'protocol_source': tune.PROTOCOL_SOURCE,
              'persistence': 'COMM_SET_MCCONF (13) stores the full motor configuration; '
                             'runtime readback does not independently verify persistence across reboot.'}
    write_json(out/'apply-manifest.json', report)
    after = None
    try:
        before = capture_four(connection, out/'before', tune.TARGET_IDENTITY)
        require_before(bundle, before)
        report['before_sha256'] = {name: tune.sha256(data) for name, data in before['payloads'].items()}
        if not apply:
            report['status'] = 'preflight_verified_no_settings_sent'
            return report
        frame = motor_frame(bundle['artifacts']['proposed_motor'])
        (out/'set_mcconf_frame.bin').write_bytes(frame)
        report.update(status='persistent_write_intent_recorded', write_command=SET_MCCONF,
                      do_not_retry_this_application=True,
                      interrupted_intent_warning='If this process ends before its final journal, '
                                                'the write may have started even if the recorded attempt count is zero.',
                      write_frame_sha256=tune.sha256(frame), write_frame_bytes=len(frame),
                      write_intent_at_utc=utcnow())
        write_json(out/'apply-manifest.json', report)
        require_unchanged(bundle)
        deadline = min(before['telemetry_at'] + MAX_TELEMETRY_AGE_S,
                       before['started'] + MAX_CAPTURE_AGE_S)
        connection.set_motor_once(frame, deadline)
        report['full_frame_accepted_at_utc'] = utcnow()
        connection.receive_ack()
        report['ack_verified'] = True
        report['ack_received_at_utc'] = utcnow()
        write_json(out/'apply-manifest.json', report)
        after = capture_four(connection, out/'after', tune.TARGET_IDENTITY)
        report['after_sha256'] = {name: tune.sha256(data) for name, data in after['payloads'].items()}
        audit = verify_after(bundle, after)
        write_json(out/'field-audit.json', audit)
        report.update(status='acknowledged_runtime_readback_verified', readback_verified=True,
                      verified_motor_fields=189, verified_app_fields=187, verified_total_fields=376,
                      application_bytes_unchanged=True, all_nonallowlisted_motor_bytes_unchanged=True)
        return report
    except BaseException as error:
        report['error'] = f'{type(error).__name__}: {error}'
        report['status'] = ('write_uncertain_do_not_retry' if connection.mutation_attempts
                            else 'rejected_no_settings_sent')
        if connection.mutation_attempts and connection.full_write_accepted and connection.safe_for_queries and after is None:
            try:
                recovered = capture_four(connection, out/'recovery', tune.TARGET_IDENTITY)
                report['recovery_sha256'] = {name: tune.sha256(data) for name, data in recovered['payloads'].items()}
                try:
                    verify_after(bundle, recovered)
                    report['recovery_matches_proposal'] = True
                except ValueError as mismatch:
                    report['recovery_matches_proposal'] = False
                    report['recovery_comparison_error'] = str(mismatch)
            except BaseException as recovery_error:
                report['recovery_error'] = f'{type(recovery_error).__name__}: {recovery_error}'
        elif connection.mutation_attempts and not connection.safe_for_queries:
            report['recovery_skipped'] = 'Incomplete/unknown serial send: additional bytes could complete an unintended frame.'
        raise
    finally:
        report['mutating_write_attempts'] = connection.mutation_attempts
        report['full_write_frame_accepted'] = connection.full_write_accepted
        report['write_bytes_accepted'] = connection.bytes_accepted
        report['finished_at_utc'] = utcnow()
        write_json(out/'apply-manifest.json', report)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('trial', type=Path, help='Prepared trial directory with reference and before snapshots')
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--preflight-only', action='store_true', help='Read four fresh payloads; never write settings')
    mode.add_argument('--apply', action='store_true', help='Attempt the fixed persistent motor tune exactly once')
    parser.add_argument('--acknowledge-persistent-write', action='store_true',
                        help='Required with --apply: SET_MCCONF persists the entire motor configuration')
    parser.add_argument('--port', help='Explicit VESC USB serial port; close other control/configuration clients first')
    parser.add_argument('--out', type=Path, help='New evidence directory, outside the prepared trial')
    args = parser.parse_args(argv)
    live = args.apply or args.preflight_only
    if args.apply != args.acknowledge_persistent_write:
        parser.error('--apply and --acknowledge-persistent-write must be supplied together')
    if live and (not args.port or not args.out):
        parser.error('Hardware reads/application require both --port and a new --out directory')
    if not live and (args.port or args.out):
        parser.error('Default mode is offline; select --preflight-only or --apply for --port/--out')
    bundle = validate_trial(args.trial)
    if not live:
        print('OFFLINE VALIDATION PASSED: fixed 12-field trial recomputed; no device opened or settings sent.')
        return 0
    resolved = args.out.resolve()
    if args.out.exists() or args.out.is_symlink():
        raise FileExistsError('Evidence output must be a new directory')
    protected = [bundle['directory']]
    protected += [Path(bundle['plan'][side]['provenance']['manifest_path']).parent.resolve()
                  for side in ('reference', 'current')]
    if any(resolved == path or path in resolved.parents for path in protected):
        raise ValueError('Evidence output must be outside the prepared trial and original input captures')
    with SerialConnection(args.port) as connection:
        result = run(bundle, connection, args.out, apply=args.apply)
    print(result['status'] + '; evidence: ' + str(args.out.resolve()))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
