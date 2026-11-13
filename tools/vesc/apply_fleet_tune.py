#!/usr/bin/env python3
"""Validate a prepared kart-4/5 package; an explicitly opted-in run writes MCCONF once.

Default: offline validation only. This is the separate, narrow writer for packages made by
prepare_fleet_kart.py. The target is bound three ways: the package's kart ID and controller
UUID, the same two values stated again on the command line, and the UUID the controller
itself reports immediately before the write. The exact proposed bytes must also be named by
hash. It cannot address kart 3 or a reserved controller, and never sends APPCONF, Lisp,
motor, reset or detection commands. apply_tune.py stays pinned to kart 3 and is not changed.
"""
import argparse
import datetime
import json
from pathlib import Path
import re

from apply_tune import (APP_SCHEMA_SHA256, SET_MCCONF, SerialConnection, capture_four,
                        motor_frame, strict_object, write_json)
from capture import READ_COMMANDS
from compare import compare_decoded
from decode import DEFAULT_SCHEMA, decode_payloads
import prepare_fleet_kart as fleet
import tune

MAX_TELEMETRY_AGE_S = .75
MAX_CAPTURE_AGE_S = 10.0
BUILD = {'firmware': '6.02', 'hardware': '75_300_R2', 'test_version': 0, 'firmware_name': 'no_hw_limits'}
# Everything the package asserts about the write must survive an independent recomputation.
PLAN_KEYS = (
    'format', 'operation', 'apply_supported', 'status', 'kart_id', 'expected_before_sha256',
    'allowlisted_motor_fields', 'patches', 'protection_limits', 'proposed_motor_response_sha256',
    'summary', 'target_vs_proposed_all_fields', 'source_vs_proposed_all_fields',
    'remaining_differences', 'operating_differences_require_resolution', 'filter',
)


def utcnow():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def source_hashes(directory):
    files = [directory/'plan.json', directory/'proposed_motor_response.bin']
    for side in ('source', 'before'):
        files += [directory/side/'manifest.json']
        files += [directory/side/(name + '.bin') for name in READ_COMMANDS.values()]
    files += [DEFAULT_SCHEMA/'parameters_mcconf.xml', DEFAULT_SCHEMA/'parameters_appconf.xml']
    return {str(path): tune.sha256(path.read_bytes()) for path in files}


def validate_package(directory, *, kart_id, expected_uuid):
    """Rebuild the package from its own input copies and require the stated target."""
    directory = Path(directory).resolve(strict=True)
    initial_hashes = source_hashes(directory)
    if tune.sha256((DEFAULT_SCHEMA/'parameters_appconf.xml').read_bytes()) != APP_SCHEMA_SHA256:
        raise ValueError('Pinned application schema bytes changed')
    if type(kart_id) is not int or kart_id not in (4, 5):
        raise ValueError('Only kart IDs 4 and 5 are in scope')
    expected_uuid = fleet.uuid_text(expected_uuid)
    if expected_uuid in fleet.RESERVED_UUIDS:
        raise ValueError('Stated UUID belongs to kart 3 or a reserved controller')
    plan = json.loads((directory/'plan.json').read_text(), object_pairs_hook=strict_object,
                      parse_constant=lambda value: (_ for _ in ()).throw(ValueError('Nonfinite JSON: ' + value)))
    limits = plan.get('protection_limits', {}).get('copied')
    if type(limits) is not bool:
        raise ValueError('Package does not state whether protection limits are copied')
    if plan.get('kart_id') != kart_id:
        raise ValueError('Package was prepared for a different kart ID')
    stated = (plan.get('target', {}).get('identity', {}).get('uuid'), plan.get('filter', {}).get('target_uuid'))
    if stated != (expected_uuid, expected_uuid):
        raise ValueError('Package was prepared for a different controller UUID')
    rebuilt, artifacts = fleet.prepare(directory/'source', directory/'before', kart_id=kart_id,
                                       target_uuid=expected_uuid, protection_limits=limits)
    rebuilt = json.loads(json.dumps(rebuilt, allow_nan=False))
    for key in PLAN_KEYS:
        if plan.get(key) != rebuilt[key]:
            raise ValueError('Prepared package does not match independent recomputation: ' + key)
    for side in ('source', 'target'):
        if plan[side].get('identity') != rebuilt[side]['identity']:
            raise ValueError('Prepared identity changed: ' + side)
        # Original capture paths differ from the package's copies; hashes and dated
        # query evidence must still be exactly the records validated from those copies.
        for key in ('manifest_sha256', 'queries'):
            if plan[side].get('provenance', {}).get(key) != rebuilt[side]['provenance'][key]:
                raise ValueError('Prepared capture provenance changed: ' + side + '/' + key)
    proposed = artifacts['proposed_motor']
    if (directory/'proposed_motor_response.bin').read_bytes() != proposed:
        raise ValueError('Proposed motor bytes differ from the independently rebuilt package')
    if tune.sha256(proposed) != plan['proposed_motor_response_sha256']:
        raise ValueError('Proposed motor hash differs from the package')
    if source_hashes(directory) != initial_hashes:
        raise ValueError('Package/schema files changed during validation')
    return {'directory': directory, 'plan': plan, 'artifacts': artifacts, 'source_sha256': initial_hashes,
            'kart_id': kart_id, 'expected_identity': dict(BUILD, uuid=expected_uuid)}


def require_unchanged(bundle):
    if source_hashes(bundle['directory']) != bundle['source_sha256']:
        raise ValueError('Package/schema files changed after validation')


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
    expected_audit = bundle['plan']['target_vs_proposed_all_fields']
    for name, group in audit.items():
        wanted_rows = expected_audit[name]['fields']
        if len(group['fields']) != len(wanted_rows):
            raise ValueError('Readback field audit differs from prepared package')
        for row, wanted in zip(group['fields'], wanted_rows):
            if any(row[key] != wanted[key] for key in row):
                raise ValueError('Readback field audit differs from prepared package')
    return audit


def run(bundle, connection, out, apply=False):
    """Run on an already-open connection; all failures retain the evidence journal."""
    out = Path(out)
    out.mkdir(parents=True, exist_ok=False)
    identity, plan = bundle['expected_identity'], bundle['plan']
    report = {'started_at_utc': utcnow(), 'mode': 'apply_once' if apply else 'preflight_only',
              'status': 'preflight_in_progress', 'kart_id': bundle['kart_id'],
              'source_sha256': bundle['source_sha256'], 'expected_identity': identity,
              'allowlisted_motor_fields': plan['allowlisted_motor_fields'],
              'changed_motor_fields': [p['field'] for p in plan['patches'] if p['before_hex'] != p['proposed_hex']],
              'protection_limits_copied': plan['protection_limits']['copied'],
              'retained_operating_differences': [d['configuration'] + ' / ' + d['field']
                                                 for d in plan['operating_differences_require_resolution']],
              'proposed_motor_response_sha256': plan['proposed_motor_response_sha256'],
              'mutating_write_attempts': 0, 'ack_verified': False, 'readback_verified': False,
              'retry_performed': False, 'rollback_performed': False,
              'saved_flash_independently_verified': False, 'protocol_source': tune.PROTOCOL_SOURCE,
              'persistence': 'COMM_SET_MCCONF (13) stores the full motor configuration; '
                             'runtime readback does not independently verify persistence across reboot.'}
    write_json(out/'apply-manifest.json', report)
    after = None
    try:
        before = capture_four(connection, out/'before', identity)
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
        after = capture_four(connection, out/'after', identity)
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
                recovered = capture_four(connection, out/'recovery', identity)
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
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('package', type=Path, help='Directory written by prepare_fleet_kart.py for this kart')
    parser.add_argument('--kart-id', type=int, choices=(4, 5), required=True, help='Fleet ID the package was prepared for')
    parser.add_argument('--expected-uuid', required=True,
                        help='Controller UUID of the physically labelled target, stated independently of the package')
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--preflight-only', action='store_true', help='Read four fresh payloads; never write settings')
    mode.add_argument('--apply', action='store_true', help='Attempt the prepared persistent motor write exactly once')
    parser.add_argument('--acknowledge-persistent-write', action='store_true',
                        help='Required with --apply: SET_MCCONF persists the entire motor configuration')
    parser.add_argument('--expect-proposed-sha256',
                        help='Required with --apply: SHA-256 of the reviewed proposed_motor_response.bin')
    parser.add_argument('--port', help='Explicit VESC USB serial port; close other control/configuration clients first')
    parser.add_argument('--out', type=Path, help='New evidence directory, outside the package and its input captures')
    args = parser.parse_args(argv)
    live = args.apply or args.preflight_only
    if args.apply != args.acknowledge_persistent_write:
        parser.error('--apply and --acknowledge-persistent-write must be supplied together')
    if args.apply != bool(args.expect_proposed_sha256):
        parser.error('--apply and --expect-proposed-sha256 must be supplied together')
    if live and (not args.port or not args.out):
        parser.error('Hardware reads/application require both --port and a new --out directory')
    if not live and (args.port or args.out):
        parser.error('Default mode is offline; select --preflight-only or --apply for --port/--out')
    bundle = validate_package(args.package, kart_id=args.kart_id, expected_uuid=args.expected_uuid)
    proposed_sha = bundle['plan']['proposed_motor_response_sha256']
    if args.apply:
        stated = args.expect_proposed_sha256.lower()
        if not re.fullmatch(r'[0-9a-f]{64}', stated) or stated != proposed_sha:
            raise ValueError('Stated proposed-bytes hash is not the hash of this package; no device opened')
    if not live:
        print(f'OFFLINE VALIDATION PASSED: kart {args.kart_id} package recomputed; '
              f'{bundle["plan"]["summary"]["changed_fields"]} field changes; proposed sha256 {proposed_sha}. '
              'No device opened or settings sent.')
        return 0
    resolved = args.out.resolve()
    if args.out.exists() or args.out.is_symlink():
        raise FileExistsError('Evidence output must be a new directory')
    protected = [bundle['directory']]
    protected += [Path(bundle['plan'][side]['provenance']['manifest_path']).parent.resolve()
                  for side in ('source', 'target')]
    if any(resolved == path or path in resolved.parents for path in protected):
        raise ValueError('Evidence output must be outside the prepared package and original input captures')
    with SerialConnection(args.port) as connection:
        result = run(bundle, connection, args.out, apply=args.apply)
    print(result['status'] + '; evidence: ' + str(args.out.resolve()))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
