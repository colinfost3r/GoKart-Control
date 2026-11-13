#!/usr/bin/env python3
"""Kart-4/5 reverse-input filter: observe, install once, check after a power-up, remove.

For packages made by prepare_fleet_kart.py. The target is bound to the package's kart ID and
controller UUID, both stated again on the command line, and to the UUID the controller reports;
kart 3 and the reserved controllers are refused. Kart 3's own filter tools stay pinned to kart 3.

  plan     offline: rebuild the package and print what would be stored. Opens no port.
  observe  fixed reads, the fixed pin snapshot and :ctxs. Changes no setting or stored code.
  install  one supervised erase and exact write of the package's script, read back byte for
           byte. No activation: the script first runs at the owner's next normal power-up.
  status   after that power-up: the script's own state, the raw switch level, contexts and the
           stored bytes.
  remove   one supervised erase of exactly the package's stored script, with forward selected
           and held. The controller reads the switch directly again only after the owner's
           next power cycle; until then it keeps the direction the filter last applied.

It never sends a motor command, configuration write, reset or activation, never retries and
never cleans up after an uncertain result. REPL reads may initialise the interpreter; an erase
resets it and flash operations briefly release motor output, so every action is stationary,
wheels-up, pedal-released maintenance with the reverse switch held in forward. Keep every other
VESC client (the kart's Heltec included) off the controller: 6.02 sends Lisp prints to the
interface that spoke last.
"""
import argparse
import binascii
import datetime
import json
import os
from pathlib import Path
import re
import struct
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))
import apply_fleet_tune
import prepare_fleet_kart as fleet
import rx_filter_control as control
from decode import DEFAULT_SCHEMA, decode_configuration, decode_telemetry
from read_lisp import SerialConnection, parse_code_reply, require_identity
from rx_probe import SNAPSHOT_EXPRESSION, context_summary, pin_snapshot_record, printed_text
from tune import sha256

SECTOR_BYTES = 131072
CHUNK = 256
READS = {'identity': 0, 'telemetry': 4, 'motor': 14, 'app': 17}
EXPRESSIONS = {'contexts': control.EXPRESSIONS['contexts'], 'snapshot': SNAPSHOT_EXPRESSION,
               'status': control.EXPRESSIONS['status']}
FORWARD_RX = 1  # RX high is forward; the script and the native button agree on this.


def utcnow():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


class Package:
    """The exact bytes to store, and the only frames this tool can build."""

    def __init__(self, blob):
        if not blob.endswith(b'\0\0\0') or b'\0' in blob[:-3] or not 16 < len(blob) <= SECTOR_BYTES - 8:
            raise ValueError('Expected ASCII source, one NUL and a zero import count')
        blob[:-3].decode('ascii')
        flags = b'\0\0'
        self.blob = blob
        self.crc = binascii.crc_hqx(flags + blob, 0)
        self.image = struct.pack('>IH', len(blob), self.crc) + flags + blob
        self.body_offsets = tuple(range(8, len(self.image), CHUNK))
        self.write_offsets = self.body_offsets + (0,)

    def payload(self, action, offset=0, length=0):
        if type(offset) is not int or type(length) is not int:
            raise ValueError('Offsets/lengths must be integers')
        if action in READS and offset == length == 0:
            return bytes((READS[action],))
        if action in EXPRESSIONS and offset == length == 0:
            return b'\x8a' + EXPRESSIONS[action] + b'\0'
        size = len(self.blob)
        if action == 'read' and 0 <= length <= CHUNK and 0 <= offset <= size and offset + length <= size and (length > 0 or offset == 0):
            return b'\x82' + struct.pack('>ii', length, offset)
        if action == 'erase' and offset == length == 0:
            return b'\x84' + struct.pack('>i', len(self.image))
        if action == 'write' and offset in self.write_offsets and length == 0:
            data = self.image[offset:min(offset + CHUNK, len(self.image))] if offset >= 8 else self.image[:8]
            if not data or len(data) > CHUNK or offset + len(data) > SECTOR_BYTES:
                raise ValueError('Write outside package/sector bounds')
            return b'\x83' + struct.pack('>I', offset) + data
        raise ValueError('Only fixed reads, the fixed snapshot/status/contexts, bounded code reads, one erase and exact package writes are allowed')

    def frame(self, action, offset=0, length=0):
        data = self.payload(action, offset, length)
        if len(data) > 512:
            raise ValueError('Packet too large')
        header = bytes((2, len(data))) if len(data) < 256 else b'\x03' + struct.pack('>H', len(data))
        return header + data + struct.pack('>H', binascii.crc_hqx(data, 0)) + b'\x03'


def check_ack(action, data, offset=0):
    expected = b'\x84\x01' if action == 'erase' else b'\x83\x01' + struct.pack('>I', offset)
    if action not in ('erase', 'write') or data != expected:
        raise ValueError('Missing/rejected/wrong-offset/malformed flash ACK; never retry or activate')


def load_package(directory, *, kart_id, expected_uuid):
    """Rebuild the whole package independently and bind the script to the stated target."""
    bundle = apply_fleet_tune.validate_package(directory, kart_id=kart_id, expected_uuid=expected_uuid)
    directory, plan, artifacts = bundle['directory'], bundle['plan'], bundle['artifacts']
    files = {name: (directory / name).read_bytes() for name in ('rx-filter-codeblob.bin', 'rx-filter-autostart.lisp')}
    if files['rx-filter-codeblob.bin'] != artifacts['filter_blob'] or files['rx-filter-autostart.lisp'] != artifacts['filter_source']:
        raise ValueError('Stored filter files differ from the independently rebuilt package')
    package = Package(artifacts['filter_blob'])
    described = plan['filter']
    if (sha256(package.blob) != described['code_blob_sha256'] or package.crc != described['crc16_flags_and_blob']
            or len(package.blob) != described['code_blob_bytes'] or described['target_uuid'] != bundle['expected_identity']['uuid']):
        raise ValueError('Filter description in the plan does not match the rebuilt script')
    literal = ('\'(' + ' '.join(str(n) for n in bytes.fromhex(described['target_uuid'])) + ')').encode('ascii')
    if package.blob.count(literal) != 1:
        raise ValueError('Script is not guarded by exactly this controller UUID')
    bundle.update(package=package, filter_sha256={name: sha256(data) for name, data in files.items()})
    return bundle


def require_unchanged(bundle):
    apply_fleet_tune.require_unchanged(bundle)
    for name, digest in bundle['filter_sha256'].items():
        if sha256((bundle['directory'] / name).read_bytes()) != digest:
            raise ValueError('Package filter files changed after validation')


def require_target(raw, bundle):
    identity = require_identity(raw, bundle['expected_identity']['uuid'])
    fleet.identity_guard(identity, bundle['expected_identity']['uuid'])
    return identity


def require_app(raw, bundle):
    if raw != bundle['artifacts']['before']['app_configuration']:
        raise ValueError('Application settings differ from the package capture; refusing')
    values = decode_configuration(raw, DEFAULT_SCHEMA / 'parameters_appconf.xml', 17)['values']
    if len(values) != 187 or any(values.get(key) != value for key, value in fleet.FILTER_PRECONDITIONS.items()):
        raise ValueError('Native application prerequisites for the filter are not met')


def require_motor(raw, bundle):
    schema = DEFAULT_SCHEMA / 'parameters_mcconf.xml'
    values = decode_configuration(raw, schema, 14)['values']
    proposed = decode_configuration(bundle['artifacts']['proposed_motor'], schema, 14)['values']
    if len(values) != 189:
        raise ValueError('Incomplete motor schema')
    for field in bundle['plan']['allowlisted_motor_fields']:
        # The kart's Heltec narrows the two ERPM limits at runtime when a mode is selected
        # (a temporary write, gone at the next power-up). Tighter is accepted, looser never.
        if field == 'l_max_erpm':
            ok = 0 < values[field] <= proposed[field]
        elif field == 'l_min_erpm':
            ok = proposed[field] <= values[field] < 0
        else:
            ok = values[field] == proposed[field]
        if not ok:
            raise ValueError('The prepared tune is not on this controller; apply and verify it before the filter: ' + field)


def parse_snapshot(packets):
    records = [pin_snapshot_record(line.strip()) for line in printed_text(packets).splitlines()]
    records = [record for record in records if record is not None]
    if len(records) != 1:
        raise ValueError('No unique complete pin snapshot; outcome unknown, nothing resent')
    return records[0]


def snapshot_at_rest(sample):
    return 0 <= sample['adc_decoded_0'] <= 0.12 and abs(sample['rpm']) <= 50 and sample['fault'] == 0


def telemetry_at_rest(values):
    return values['fault_code'] == 0 and abs(values['erpm']) <= 50


class Wire(control.Wire):
    def __init__(self, fd, output, package):
        super().__init__(fd, output)
        self.package = package
        self.deadline = time.monotonic() + 120
        self.erase_deadline = None

    def send(self, action, offset=0, length=0):
        if time.monotonic() >= self.deadline or self.queue or self.parser.buffer:
            raise ValueError('Expired or unsynchronized session; nothing further sent')
        if action == 'erase' and (self.erase_deadline is None or time.monotonic() > self.erase_deadline):
            raise TimeoutError('Fresh pre-erase safety window expired; erase not sent')
        data = self.package.frame(action, offset, length)
        self.record(kind='tx_attempt', action=action, offset=offset, length=length, frame_hex=data.hex())
        with (self.output / 'tx-attempts.bin').open('ab') as out:
            out.write(data)
        if action == 'erase' and time.monotonic() > self.erase_deadline:
            self.record(kind='erase_not_sent', reason='safety window expired during journaling')
            raise TimeoutError('Fresh pre-erase safety window expired before write')
        count = os.write(self.fd, data)
        self.record(kind='tx_return', count=count)
        if count != len(data):
            raise IOError('Partial/uncertain request; no append, retry, reset or activation')

    def query(self, action, offset=0, length=0):
        self.send(action, offset, length)
        command = self.package.payload(action, offset, length)[0]
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


class Session:
    """Shared journal, raw-reply files and guards for one connection."""

    def __init__(self, bundle, output, action, **facts):
        self.bundle, self.output = bundle, Path(output)
        self.output.mkdir(parents=True, exist_ok=False)
        package = bundle['package']
        self.manifest = {'action': action, 'kart_id': bundle['kart_id'],
                         'target_uuid': bundle['expected_identity']['uuid'], 'firmware': '6.02',
                         'blob_sha256': sha256(package.blob), 'blob_bytes': len(package.blob),
                         'image_sha256': sha256(package.image), 'image_bytes': len(package.image),
                         'complete': False, 'settings_written': False, 'activation_sent': False,
                         'started_utc': utcnow(), **facts}
        self.save()

    def save(self):
        (self.output / 'manifest.json').write_text(json.dumps(self.manifest, indent=2) + '\n')

    def read(self, wire, action, label, offset=0, length=0):
        data = wire.query(action, offset, length)
        (self.output / f'{label}.bin').write_bytes(data)
        return data

    def settings(self, wire, stage):
        identity = require_target(self.read(wire, 'identity', f'identity_{stage}'), self.bundle)
        app = self.read(wire, 'app', f'app_{stage}')
        motor = self.read(wire, 'motor', f'motor_{stage}')
        require_app(app, self.bundle)
        require_motor(motor, self.bundle)
        self.manifest[f'identity_{stage}'] = identity
        self.save()
        return app, motor

    def stored_total(self, wire, label):
        total, data = parse_code_reply(self.read(wire, 'read', label), 0, 0)
        if data:
            raise ValueError('Unexpected data in a size-only code read')
        return total

    def stored_bytes(self, wire, label):
        package = self.bundle['package']
        size = len(package.blob)
        if self.stored_total(wire, label + '_size') != size:
            raise ValueError('Stored code is invalid or has unexpected length')
        collected = bytearray()
        for offset in range(0, size, CHUNK):
            count = min(CHUNK, size - offset)
            _, data = parse_code_reply(self.read(wire, 'read', f'{label}_{offset:05d}', offset, count), count, offset, size)
            collected.extend(data)
        (self.output / 'code-readback.bin').write_bytes(collected)
        if bytes(collected) != package.blob:
            raise ValueError('Stored payload differs from the exact package script')
        parse_code_reply(self.read(wire, 'read', label + '_size_recheck'), 0, 0, size)
        return sha256(bytes(collected))

    def contexts(self, wire, label):
        summary = context_summary(wire.expression('contexts'))
        self.manifest[label] = summary
        self.save()
        return summary

    def mutate(self, wire, action, offset=0):
        """One journalled flash request and its exact acknowledgement. Never repeated."""
        manifest = self.manifest
        manifest['phase'] = action + '_attempted'
        manifest['flash_attempts'].append({'action': action, 'offset': offset,
                                           'request_frame_hex': self.bundle['package'].frame(action, offset).hex()})
        self.save()
        response = self.read(wire, action, f'ack_{len(manifest["flash_attempts"]):03d}', offset)
        check_ack(action, response, offset)
        manifest['flash_attempts'][-1]['ack_verified'] = True
        self.save()

    def fail(self, error, policy):
        self.manifest['error'] = f'{type(error).__name__}: {error}'
        self.manifest['failure_policy'] = policy

    def finish(self):
        self.manifest['finished_utc'] = utcnow()
        self.save()


def observe(port, output, bundle, *, samples=5, pause=0.25, connection_factory=SerialConnection, wire_factory=Wire):
    """Reads and fixed pin snapshots only. Reports what it sees; requires nothing about the switch."""
    if type(samples) is not int or not 1 <= samples <= 40:
        raise ValueError('1..40 samples')
    session = Session(bundle, output, 'observe', flash_attempts=[],
                      interpreter_side_effects='REPL may initialise the interpreter; no stored code is run or changed')
    manifest = session.manifest
    try:
        with connection_factory(port) as connection:
            wire = wire_factory(connection.fd, session.output, bundle['package'])
            app, motor = session.settings(wire, 'before')
            manifest['stored_code_bytes'] = session.stored_total(wire, 'stored_size')
            manifest['samples'] = []
            for index in range(samples):
                telemetry = decode_telemetry(session.read(wire, 'telemetry', f'telemetry_{index}'))
                pins = parse_snapshot(wire.expression('snapshot'))
                manifest['samples'].append({'pins': pins, 'erpm': telemetry['erpm'], 'fault_code': telemetry['fault_code'],
                                            'input_voltage_v': telemetry.get('input_voltage_v'),
                                            'at_rest': snapshot_at_rest(pins) and telemetry_at_rest(telemetry)})
                session.save()
                if index + 1 < samples:
                    time.sleep(pause)
            session.contexts(wire, 'contexts')
            if session.read(wire, 'app', 'app_after') != app or session.read(wire, 'motor', 'motor_after') != motor:
                raise ValueError('Configuration changed during observation')
            manifest['identity_after'] = require_target(session.read(wire, 'identity', 'identity_after'), bundle)
            levels = sorted({s['pins']['rx'] for s in manifest['samples']})
            manifest.update(complete=True, rx_levels_seen=levels,
                            adc_range=[min(s['pins']['adc_decoded_0'] for s in manifest['samples']),
                                       max(s['pins']['adc_decoded_0'] for s in manifest['samples'])],
                            all_at_rest=all(s['at_rest'] for s in manifest['samples']))
    except BaseException as error:
        session.fail(error, 'Nothing was written. No further sends or retry.')
        raise
    finally:
        session.finish()
    return manifest


def install(port, output, bundle, *, apply=False, supervised=False,
            connection_factory=SerialConnection, wire_factory=Wire):
    package = bundle['package']
    plan = {'kart_id': bundle['kart_id'], 'target_uuid': bundle['expected_identity']['uuid'], 'firmware': '6.02',
            'blob_sha256': sha256(package.blob), 'image_sha256': sha256(package.image),
            'blob_bytes': len(package.blob), 'image_bytes': len(package.image), 'flags': 0,
            'write_offsets': list(package.write_offsets), 'activation_command_available': False,
            'normal_future_boot_runs_valid_code': True, 'power_fail_atomic': False}
    if not apply:
        return {'offline_only': True, **plan}
    if not supervised:
        raise ValueError('Fresh supervised wheels-up/pedal-released/forward-selected/cutoff setup required')
    require_unchanged(bundle)
    session = Session(bundle, output, 'install', apply=True, supervised=True, phase='preflight', flash_attempts=[],
                      write_offsets=plan['write_offsets'], power_fail_atomic=False,
                      native_detach_independently_readable=False, header_flags_read_back_independently=False)
    manifest = session.manifest
    (session.output / 'planned-image.bin').write_bytes(package.image)

    def forward_rest(pins, telemetry, what):
        if not telemetry_at_rest(telemetry) or not snapshot_at_rest(pins):
            raise ValueError(what + ': not at rest/fault-free in the released pedal region')
        if pins['rx'] != FORWARD_RX:
            raise ValueError(what + ': reverse switch is not reading forward (RX high)')

    try:
        with connection_factory(port) as connection:
            wire = wire_factory(connection.fd, session.output, package)
            app_before, motor_before = session.settings(wire, 'before')
            manifest['preflight_samples'] = []
            for index in range(4):
                telemetry = decode_telemetry(session.read(wire, 'telemetry', f'telemetry_{index}'))
                pins = parse_snapshot(wire.expression('snapshot'))
                forward_rest(pins, telemetry, 'Preflight')
                manifest['preflight_samples'].append({'telemetry': telemetry, 'pins': pins})
                session.save()
            if session.contexts(wire, 'contexts_before')['snapshot'] != 'no_contexts_reported':
                raise ValueError('Live or unknown Lisp contexts; refusing erase')
            if session.read(wire, 'app', 'app_preerase') != app_before or session.read(wire, 'motor', 'motor_preerase') != motor_before:
                raise ValueError('Configuration changed before erase')
            require_unchanged(bundle)
            preerase_started = time.monotonic()
            final_pins = parse_snapshot(wire.expression('snapshot', seconds=0.3))
            final_values = decode_telemetry(session.read(wire, 'telemetry', 'telemetry_final_preerase'))
            forward_rest(final_pins, final_values, 'Final check before erase')
            manifest['final_preerase_sample'] = {'telemetry': final_values, 'pins': final_pins}
            if session.stored_total(wire, 'stored_before') != 0:
                raise ValueError('Existing valid Lisp code: refusing erase/install')
            manifest['stored_before'] = {'status': 'no_valid_blob', 'not_a_raw_blank_flash_backup': True}
            wire.erase_deadline = preerase_started + 0.75
            manifest['final_preerase_window_seconds'] = time.monotonic() - preerase_started
            session.save()
            if time.monotonic() > wire.erase_deadline:
                raise TimeoutError('Final safety/blob reads exceeded 750 ms; erase not sent')
            # The last empty-code read and the fresh input check share one bounded 750 ms window.
            session.mutate(wire, 'erase')
            if session.stored_total(wire, 'stored_after_erase') != 0:
                raise ValueError('Code reported after erase; state unknown')
            for offset in package.write_offsets:
                session.mutate(wire, 'write', offset)
            manifest['phase'] = 'readback'
            session.save()
            manifest['readback_sha256'] = session.stored_bytes(wire, 'readback')
            app_after = session.read(wire, 'app', 'app_after')
            motor_after = session.read(wire, 'motor', 'motor_after')
            require_app(app_after, bundle)
            require_motor(motor_after, bundle)
            if app_after != app_before or motor_after != motor_before:
                raise ValueError('Configuration changed during persistence')
            manifest['identity_after'] = require_target(session.read(wire, 'identity', 'identity_after'), bundle)
            manifest.update({'phase': 'stored_verified_not_activated', 'complete': True,
                             'all_376_settings_preserved': True,
                             'boot_acceptance': 'pending owner-controlled physical power cycle'})
    except BaseException as error:
        session.fail(error, 'No further sends, retry, reset, activation or cleanup. Flash/runtime state may be partial.')
        raise
    finally:
        session.finish()
    return manifest


def remove(port, output, bundle, *, apply=False, supervised=False,
           connection_factory=SerialConnection, wire_factory=Wire):
    """Erase exactly the package's stored script, once. Nothing is written in its place.

    The erase stops the script but not what it last told the controller: the direction it
    applied stays in force until the next power cycle. So removal is refused unless forward is
    selected and forward is what the filter holds (or it never took over the switch)."""
    package = bundle['package']
    plan = {'kart_id': bundle['kart_id'], 'target_uuid': bundle['expected_identity']['uuid'], 'firmware': '6.02',
            'removes_blob_sha256': sha256(package.blob), 'removes_blob_bytes': len(package.blob),
            'flash_requests': ['erase'], 'writes': 0, 'settings_written': False,
            'raw_switch_restored': 'only after the owner power-cycles the controller',
            'direction_until_power_cycle': 'forward, held'}
    if not apply:
        return {'offline_only': True, **plan}
    if not supervised:
        raise ValueError('Fresh supervised wheels-up/pedal-released/forward-selected/cutoff setup required')
    require_unchanged(bundle)
    session = Session(bundle, output, 'remove', apply=True, supervised=True, phase='preflight', flash_attempts=[],
                      native_detach_independently_readable=False)
    manifest = session.manifest

    def forward_rest(state, telemetry, what):
        if not telemetry_at_rest(telemetry) or not control.at_rest(state):
            raise ValueError(what + ': not at rest/fault-free in the released pedal region')
        if state['rx'] != FORWARD_RX:
            raise ValueError(what + ': reverse switch is not reading forward (RX high)')
        if state['applied'] == 1:
            raise ValueError(what + ': the filter is holding reverse, which would stay in force until the power '
                             'cycle; power-cycle with forward selected, then remove')
        if state['active'] and state['applied'] != 0:
            raise ValueError(what + ': the filter has taken over the switch but reports no applied direction')

    try:
        with connection_factory(port) as connection:
            wire = wire_factory(connection.fd, session.output, package)
            app_before, motor_before = session.settings(wire, 'before')
            # Only ever erase the script this package describes.
            manifest['stored_before_sha256'] = session.stored_bytes(wire, 'stored')
            manifest['preflight_samples'] = []
            for index in range(4):
                telemetry = decode_telemetry(session.read(wire, 'telemetry', f'telemetry_{index}'))
                state = control.parse_status(wire.expression('status'))
                forward_rest(state, telemetry, 'Preflight')
                manifest['preflight_samples'].append({'telemetry': telemetry, 'filter_status': state})
                session.save()
            if session.read(wire, 'app', 'app_preerase') != app_before or session.read(wire, 'motor', 'motor_preerase') != motor_before:
                raise ValueError('Configuration changed before erase')
            require_unchanged(bundle)
            preerase_started = time.monotonic()
            final_state = control.parse_status(wire.expression('status', seconds=0.3))
            final_values = decode_telemetry(session.read(wire, 'telemetry', 'telemetry_final_preerase'))
            forward_rest(final_state, final_values, 'Final check before erase')
            manifest['final_preerase_sample'] = {'telemetry': final_values, 'filter_status': final_state}
            wire.erase_deadline = preerase_started + 0.75
            manifest['final_preerase_window_seconds'] = time.monotonic() - preerase_started
            session.save()
            if time.monotonic() > wire.erase_deadline:
                raise TimeoutError('Final safety reads exceeded 750 ms; erase not sent')
            session.mutate(wire, 'erase')
            # Flash-level reads only from here: a REPL request could start the interpreter again.
            if session.stored_total(wire, 'stored_after_erase') != 0:
                raise ValueError('Code reported after erase; state unknown')
            app_after = session.read(wire, 'app', 'app_after')
            motor_after = session.read(wire, 'motor', 'motor_after')
            if app_after != app_before or motor_after != motor_before:
                raise ValueError('Configuration changed during removal')
            manifest['identity_after'] = require_target(session.read(wire, 'identity', 'identity_after'), bundle)
            held = 'forward, held by the stopped filter' if final_state['active'] else 'raw switch: the filter had not taken it over'
            manifest.update({'phase': 'erased_power_cycle_required', 'complete': True,
                             'all_376_settings_preserved': True, 'direction_until_power_cycle': held,
                             'boot_acceptance': 'pending owner-controlled physical power cycle, then observe: no stored code, no contexts'})
    except BaseException as error:
        session.fail(error, 'No further sends, retry, reset, activation or cleanup. Flash/runtime state may be partial.')
        raise
    finally:
        session.finish()
    return manifest


def status(port, output, bundle, *, expected_rx, connection_factory=SerialConnection, wire_factory=Wire):
    """After a normal power-up: is the stored script the package's, and is its worker armed?"""
    if type(expected_rx) is not int or expected_rx not in (0, 1):
        raise ValueError('State the physical switch position: --expected-rx 1 (forward) or 0 (reverse)')
    session = Session(bundle, output, 'status', expected_rx=expected_rx, flash_attempts=[],
                      native_detach_independently_readable=False,
                      note='A stock :ctxs listing omits the context that is executing; run/active/pid/applied plus physical behaviour are bounded evidence')
    manifest = session.manifest
    try:
        with connection_factory(port) as connection:
            wire = wire_factory(connection.fd, session.output, bundle['package'])
            session.settings(wire, 'before')
            manifest['readback_sha256'] = session.stored_bytes(wire, 'stored')
            manifest['telemetry'] = decode_telemetry(session.read(wire, 'telemetry', 'telemetry'))
            state = control.parse_status(wire.expression('status'))
            manifest['filter_status'] = state
            session.save()
            session.contexts(wire, 'contexts')
            manifest['identity_after'] = require_target(session.read(wire, 'identity', 'identity_after'), bundle)
            if not telemetry_at_rest(manifest['telemetry']) or not control.at_rest(state):
                raise ValueError('Not at rest/fault-free with the pedal released; state recorded, no verdict')
            if state['rx'] != expected_rx:
                raise ValueError('Raw switch level is not the stated position')
            if not (state['run'] and state['active'] and state['pid'] >= 0):
                raise RuntimeError('Stored script is present but its worker is not armed; do not drive, inspect')
            if state['applied'] != 1 - state['rx']:
                raise RuntimeError('Applied direction does not match the switch; do not drive, inspect')
            manifest.update(complete=True, armed=True,
                            applied_direction='reverse' if state['applied'] else 'forward')
    except BaseException as error:
        session.fail(error, 'Nothing was written. No start, stop, rollback, retry or cleanup was attempted.')
        raise
    finally:
        session.finish()
    return manifest


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('action', choices=('plan', 'observe', 'install', 'status', 'remove'))
    parser.add_argument('package', type=Path, help='Directory written by prepare_fleet_kart.py for this kart')
    parser.add_argument('--kart-id', type=int, choices=(4, 5), required=True)
    parser.add_argument('--expected-uuid', required=True, help='Controller UUID of the physically labelled target')
    parser.add_argument('--port', help='Explicit VESC USB serial port')
    parser.add_argument('--out', type=Path, help='New evidence directory, outside the package')
    parser.add_argument('--samples', type=int, default=5, help='observe: number of pin snapshots (default 5)')
    parser.add_argument('--apply', action='store_true', help='install: actually erase and write; remove: actually erase')
    parser.add_argument('--supervised', action='store_true', help='install/remove: wheels up, pedal released, forward selected, operator at the cutoff')
    parser.add_argument('--expect-blob-sha256', help='install/remove: SHA-256 of the reviewed rx-filter-codeblob.bin')
    parser.add_argument('--expected-rx', type=int, choices=(0, 1), help='status: physical switch position, 1 forward / 0 reverse')
    args = parser.parse_args(argv)
    flashing = args.action in ('install', 'remove')
    live = args.action in ('observe', 'status') or (flashing and args.apply)
    if not flashing and (args.apply or args.supervised or args.expect_blob_sha256):
        parser.error('--apply, --supervised and --expect-blob-sha256 belong to install and remove')
    if flashing and args.apply != bool(args.expect_blob_sha256):
        parser.error(args.action + ' --apply and --expect-blob-sha256 must be supplied together')
    if args.action == 'status' and args.expected_rx is None:
        parser.error('status requires --expected-rx')
    if live and (not args.port or not args.out):
        parser.error('This action needs both --port and a new --out directory')
    if not live and (args.port or args.out):
        parser.error('Offline action: no --port or --out')
    bundle = load_package(args.package, kart_id=args.kart_id, expected_uuid=args.expected_uuid)
    blob_sha = sha256(bundle['package'].blob)
    if flashing and args.apply:
        stated = args.expect_blob_sha256.lower()
        if not re.fullmatch(r'[0-9a-f]{64}', stated) or stated != blob_sha:
            raise ValueError('Stated script hash is not the hash of this package; no device opened')
    if live:
        resolved = args.out.resolve()
        if args.out.exists() or args.out.is_symlink():
            raise FileExistsError('Evidence output must be a new directory')
        protected = [bundle['directory']] + [Path(bundle['plan'][side]['provenance']['manifest_path']).parent.resolve()
                                             for side in ('source', 'target')]
        if any(resolved == path or path in resolved.parents for path in protected):
            raise ValueError('Evidence output must be outside the prepared package and original input captures')
    if args.action == 'observe':
        result = observe(args.port, args.out, bundle, samples=args.samples)
        summary = {k: result[k] for k in ('complete', 'stored_code_bytes', 'rx_levels_seen', 'adc_range', 'all_at_rest')}
        summary['contexts'] = result['contexts']['snapshot']
    elif args.action == 'status':
        result = status(args.port, args.out, bundle, expected_rx=args.expected_rx)
        summary = {k: result[k] for k in ('complete', 'armed', 'applied_direction', 'filter_status', 'readback_sha256')}
    elif args.action == 'remove':
        result = remove(args.port, args.out, bundle, apply=args.apply, supervised=args.supervised)
        summary = result if result.get('offline_only') else {k: result[k] for k in ('complete', 'phase', 'direction_until_power_cycle', 'boot_acceptance')}
    else:
        result = install(args.port, args.out, bundle, apply=args.action == 'install' and args.apply, supervised=args.supervised)
        summary = result if result.get('offline_only') else {k: result[k] for k in ('complete', 'phase', 'readback_sha256', 'boot_acceptance')}
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
