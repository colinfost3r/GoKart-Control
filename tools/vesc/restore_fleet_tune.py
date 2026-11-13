#!/usr/bin/env python3
"""Put a kart-4/5 controller's motor settings back to what they were before its package.

Default: offline; lists the settings that would be restored. --preflight-only reads and checks.
An explicitly opted-in --apply writes MCCONF exactly once.

What is written is the controller's CURRENT motor bytes with only the settings the package
changed set back to the values in the package's own `before` capture. Every other byte stays
as read, including the offsets the controller measures at each power-up. It refuses unless
every other setting still equals that capture, so a temporary limit can never be made
permanent: run it with the kart's Heltec off the VESC and after a VESC power cycle.

The target is bound like the writer that made the change: the package's kart ID and UUID, the
same two stated again on the command line, and the UUID the controller reports. The original
bytes being restored must be named by hash. It never sends APPCONF, Lisp, motor, reset or
detection commands, never retries, and cannot address kart 3 or a reserved controller.
"""
import argparse
import json
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import apply_fleet_tune
from apply_tune import SET_MCCONF, SerialConnection, capture_four, motor_frame, write_json
import prepare_fleet_kart as fleet
import tune

MEASURED_PREFIX = 'foc_offsets_'   # measured by the controller at each power-up; never compared or restored
MAX_TELEMETRY_AGE_S = apply_fleet_tune.MAX_TELEMETRY_AGE_S
MAX_CAPTURE_AGE_S = apply_fleet_tune.MAX_CAPTURE_AGE_S


def changed_patches(bundle):
    return [p for p in bundle['plan']['patches'] if p['before_hex'] != p['proposed_hex']]


def describe(bundle):
    original = bundle['artifacts']['before']['motor_configuration']
    return {'kart_id': bundle['kart_id'], 'target_uuid': bundle['expected_identity']['uuid'],
            'restores': [{'setting': p['field'], 'now_expected': p['proposed'], 'restored_to': p['before']}
                         for p in changed_patches(bundle)],
            'original_motor_sha256': tune.sha256(original),
            'every_other_setting': 'left exactly as read; refused if it differs from the package capture',
            'controller_measured_offsets': 'left as the controller measured them at this power-up'}


def plan_restore(bundle, fresh):
    """The exact bytes to write, and where each package setting stands now."""
    original = bundle['artifacts']['before']['motor_configuration']
    proposed = bundle['artifacts']['proposed_motor']
    spans = tune.motor_spans(fresh)
    if len(fresh) != len(original) or spans != tune.motor_spans(original) or spans != tune.motor_spans(proposed):
        raise ValueError('Fresh motor settings do not have the package layout')
    changed = [p['field'] for p in changed_patches(bundle)]
    covered, state = set(), {}
    for name, (start, end) in spans.items():
        covered.update(range(start, end))
        now = fresh[start:end]
        if name in changed:
            if now == proposed[start:end]:
                state[name] = 'package_value'
            elif now == original[start:end]:
                state[name] = 'already_original'
            else:
                raise ValueError('Setting holds neither the package value nor the original; review by hand: ' + name)
        elif name.startswith(MEASURED_PREFIX):
            continue
        elif now != original[start:end]:
            raise ValueError('A setting the package never touched differs from its capture (a temporary '
                             'limit from the Heltec, or a manual change); power-cycle with the Heltec off: ' + name)
    if any(fresh[i] != original[i] for i in range(len(original)) if i not in covered):
        raise ValueError('Motor settings header differs from the package capture')
    if set(state) != set(changed):
        raise ValueError('Package settings missing from the motor layout')
    restored, _ = fleet.patch_fields(original, fresh, changed)
    return restored, state


def require_preserved(bundle, capture):
    for name in ('firmware', 'app_configuration'):
        if capture['payloads'][name] != bundle['artifacts']['before'][name]:
            raise ValueError('Fresh controller bytes differ from the package capture: ' + name)
    tune.require_stationary(capture['decoded']['telemetry'])
    apply_fleet_tune.require_unchanged(bundle)


def verify_after(bundle, capture, restored):
    require_preserved(bundle, capture)
    after = capture['payloads']['motor_configuration']
    spans = tune.motor_spans(after)
    if len(after) != len(restored) or spans != tune.motor_spans(restored):
        raise ValueError('Readback does not have the written layout')
    measured_same = True
    covered = set()
    for name, (start, end) in spans.items():
        covered.update(range(start, end))
        if name.startswith(MEASURED_PREFIX):
            measured_same = measured_same and after[start:end] == restored[start:end]
        elif after[start:end] != restored[start:end]:
            raise ValueError('Readback differs from the written settings: ' + name)
    if any(after[i] != restored[i] for i in range(len(restored)) if i not in covered):
        raise ValueError('Readback header differs from the written settings')
    return measured_same


def run(bundle, connection, out, apply=False):
    """Run on an already-open connection; every failure keeps the evidence journal."""
    out = Path(out)
    out.mkdir(parents=True, exist_ok=False)
    identity = bundle['expected_identity']
    report = {'started_at_utc': apply_fleet_tune.utcnow(), 'mode': 'restore_once' if apply else 'preflight_only',
              'status': 'preflight_in_progress', 'kart_id': bundle['kart_id'], 'expected_identity': identity,
              'source_sha256': bundle['source_sha256'], 'plan': describe(bundle),
              'mutating_write_attempts': 0, 'ack_verified': False, 'readback_verified': False,
              'retry_performed': False, 'saved_flash_independently_verified': False,
              'persistence': 'COMM_SET_MCCONF (13) stores the full motor configuration; '
                             'runtime readback does not independently verify persistence across reboot.'}
    write_json(out/'restore-manifest.json', report)
    after = None
    try:
        before = capture_four(connection, out/'before', identity)
        require_preserved(bundle, before)
        restored, state = plan_restore(bundle, before['payloads']['motor_configuration'])
        report['settings_now'] = state
        report['to_restore'] = [name for name, where in state.items() if where == 'package_value']
        report['restored_motor_sha256'] = tune.sha256(restored)
        if not report['to_restore']:
            report['status'] = 'nothing_to_restore_no_settings_sent'
            return report
        if not apply:
            report['status'] = 'preflight_verified_no_settings_sent'
            return report
        frame = motor_frame(restored)
        (out/'set_mcconf_frame.bin').write_bytes(frame)
        report.update(status='persistent_write_intent_recorded', write_command=SET_MCCONF,
                      do_not_retry_this_application=True, write_frame_sha256=tune.sha256(frame),
                      write_frame_bytes=len(frame), write_intent_at_utc=apply_fleet_tune.utcnow(),
                      interrupted_intent_warning='If this process ends before its final journal, the write '
                                                'may have started even if the recorded attempt count is zero.')
        write_json(out/'restore-manifest.json', report)
        apply_fleet_tune.require_unchanged(bundle)
        deadline = min(before['telemetry_at'] + MAX_TELEMETRY_AGE_S, before['started'] + MAX_CAPTURE_AGE_S)
        connection.set_motor_once(frame, deadline)
        report['full_frame_accepted_at_utc'] = apply_fleet_tune.utcnow()
        connection.receive_ack()
        report['ack_verified'] = True
        write_json(out/'restore-manifest.json', report)
        after = capture_four(connection, out/'after', identity)
        report['measured_offsets_identical_after_write'] = verify_after(bundle, after, restored)
        report.update(status='acknowledged_runtime_readback_verified', readback_verified=True,
                      application_bytes_unchanged=True, restored_settings=report['to_restore'])
        return report
    except BaseException as error:
        report['error'] = f'{type(error).__name__}: {error}'
        report['status'] = ('write_uncertain_do_not_retry' if connection.mutation_attempts
                            else 'rejected_no_settings_sent')
        raise
    finally:
        report['mutating_write_attempts'] = connection.mutation_attempts
        report['full_write_frame_accepted'] = connection.full_write_accepted
        report['finished_at_utc'] = apply_fleet_tune.utcnow()
        write_json(out/'restore-manifest.json', report)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('package', type=Path, help='The package that was applied to this kart')
    parser.add_argument('--kart-id', type=int, choices=(4, 5), required=True)
    parser.add_argument('--expected-uuid', required=True, help='Controller UUID of the physically labelled target')
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--preflight-only', action='store_true', help='Read four fresh payloads and check; never write')
    mode.add_argument('--apply', action='store_true', help='Attempt the restoring persistent motor write exactly once')
    parser.add_argument('--acknowledge-persistent-write', action='store_true',
                        help='Required with --apply: SET_MCCONF persists the entire motor configuration')
    parser.add_argument('--expect-original-sha256',
                        help="Required with --apply: SHA-256 of the package's before/motor_configuration.bin")
    parser.add_argument('--port', help='Explicit VESC USB serial port; keep every other client off the controller')
    parser.add_argument('--out', type=Path, help='New evidence directory, outside the package')
    args = parser.parse_args(argv)
    live = args.apply or args.preflight_only
    if args.apply != args.acknowledge_persistent_write:
        parser.error('--apply and --acknowledge-persistent-write must be supplied together')
    if args.apply != bool(args.expect_original_sha256):
        parser.error('--apply and --expect-original-sha256 must be supplied together')
    if live and (not args.port or not args.out):
        parser.error('Hardware reads/restore require both --port and a new --out directory')
    if not live and (args.port or args.out):
        parser.error('Default mode is offline; select --preflight-only or --apply for --port/--out')
    bundle = apply_fleet_tune.validate_package(args.package, kart_id=args.kart_id, expected_uuid=args.expected_uuid)
    plan = describe(bundle)
    if args.apply:
        stated = args.expect_original_sha256.lower()
        if not re.fullmatch(r'[0-9a-f]{64}', stated) or stated != plan['original_motor_sha256']:
            raise ValueError('Stated hash is not the hash of this package\'s original motor settings; no device opened')
    if not live:
        print(json.dumps(dict(plan, offline_only=True), indent=2))
        return 0
    resolved = args.out.resolve()
    if args.out.exists() or args.out.is_symlink():
        raise FileExistsError('Evidence output must be a new directory')
    protected = [bundle['directory']]
    protected += [Path(bundle['plan'][side]['provenance']['manifest_path']).parent.resolve() for side in ('source', 'target')]
    if any(resolved == path or path in resolved.parents for path in protected):
        raise ValueError('Evidence output must be outside the prepared package and original input captures')
    with SerialConnection(args.port) as connection:
        result = run(bundle, connection, args.out, apply=args.apply)
    print(result['status'] + '; evidence: ' + str(args.out.resolve()))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
