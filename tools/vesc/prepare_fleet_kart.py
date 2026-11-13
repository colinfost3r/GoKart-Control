#!/usr/bin/env python3
"""Prepare kart 4/5 tune and UUID-bound reverse-filter artifacts OFFLINE; never apply."""
import argparse
import binascii
import datetime
import json
import math
from pathlib import Path
import re

from compare import compare_decoded, cell
from decode import DEFAULT_SCHEMA, decode_configuration, decode_payloads
from tune import TRIAL_FIELDS, motor_spans, sha256, snapshot

ROOT = Path(__file__).resolve().parents[2]
SOURCE_UUID = '37004e000951343037353739'
RESERVED_UUIDS = {SOURCE_UUID, '2c004c000951343037353739'}
REVIEWED_TUNE = {
    'l_current_max': 140.0, 'l_current_min': -5.0, 'l_in_current_max': 100.0,
    'l_min_erpm': -150000.0, 'l_max_erpm': 150000.0, 'l_max_duty': 0.95,
    'foc_fw_current_max': 95.0, 'foc_fw_duty_start': 0.87,
    'foc_openloop_rpm': 700.0, 'foc_sl_erpm': 4000.0,
    'cc_ramp_step_max': 0.04, 'm_motor_temp_sens_type': 8,
}
FILTER_SOURCE = ROOT / 'firmware/vesc-lisp/reverse-input/rx-filter-autostart.lisp'
FILTER_SOURCE_SHA = '30981ff45663d254153009ec0f6258b400126afd74a66a6caa2a70c56ac96700'
FILTER_CORE_SHA = 'd530aeb20c81c185e25ba9b4954473a8bd7069fe5b59b1babeca3ca2b89e94dc'
FILTER_CORE_BYTES = 3732
FILTER_PRECONDITIONS = {
    'app_to_use': 2, 'app_adc_conf.ctrl_type': 3, 'app_adc_conf.buttons': 0,
    'servo_out_enable': 0, 'app_adc_conf.safe_start': 1,
    'app_adc_conf.hyst': 0.15000000596046448,
}
LIMIT_MATCH_FIELDS = ('l_current_max_scale', 'l_current_min_scale', 'l_in_current_min')
# Owner decision 2026-11-13, after reviewing kart 4's capture: these five protection limits may
# also be copied from kart 3. They are NOT part of the twelve-field operating tune and are only
# copied when asked for explicitly, per kart. Values are the reviewed kart-3 source values.
PROTECTION_LIMITS = {
    'l_in_current_min': -12.0, 'l_abs_current_max': 220.0,
    'l_min_vin': 60.0, 'l_max_vin': 90.0, 'm_fault_stop_time_ms': 500,
}


def uuid_text(value):
    if not isinstance(value, str) or not re.fullmatch(r'[0-9a-fA-F]{24}', value) or int(value, 16) == 0:
        raise ValueError('Expected an actual nonzero 24-hex-digit controller UUID')
    return value.lower()


def identity_guard(identity, uuid):
    expected = {'uuid': uuid, 'firmware': '6.02', 'hardware': '75_300_R2',
                'test_version': 0, 'firmware_name': 'no_hw_limits'}
    if any(identity.get(k) != v for k, v in expected.items()):
        raise ValueError('Capture identity/build mismatch: requires pinned 6.02 release / 75_300_R2 / no_hw_limits')


def capture_guard(decoded):
    for group in ('motor_configuration', 'app_configuration'):
        for field, value in decoded[group]['values'].items():
            if isinstance(value, float) and not math.isfinite(value):
                raise ValueError(f'Nonfinite captured field: {field}')
    t = decoded['telemetry']
    for name, maximum in (('erpm', 50), ('motor_current_a', 1), ('battery_current_a', 1)):
        value = t.get(name)
        if not isinstance(value, (int, float)) or not math.isfinite(value) or abs(value) > maximum:
            raise ValueError('Preparation requires captured rest/low-current evidence; a later write needs fresh checks')
    if t.get('fault_code') != 0 or t.get('timeout_active') or t.get('kill_switch_active'):
        raise ValueError('Captured fault/timeout/kill state requires review')
    if decoded['motor_configuration']['values']['motor_type'] != 2:
        raise ValueError('Only the reviewed FOC motor-control configuration is supported')
    app = decoded['app_configuration']['values']
    if any(app.get(k) != v for k, v in FILTER_PRECONDITIONS.items()):
        raise ValueError('Native RX reverse-filter prerequisites differ; preserve and review target app settings separately')


def target_specific(group, field):
    """Classify preserved differences, never auto-copy/approve them."""
    if group == 'app_configuration':
        return field == 'controller_id' or field.startswith('app_adc_conf.voltage')
    return (field.startswith(('foc_hall_table__', 'hall_table__', 'foc_offsets_', 'si_')) or
            field in {'foc_motor_r', 'foc_motor_l', 'foc_motor_ld_lq_diff',
                      'foc_motor_flux_linkage', 'foc_current_kp', 'foc_current_ki',
                      'foc_encoder_offset', 'foc_encoder_ratio', 'foc_encoder_inverted',
                      'p_pid_offset', 'm_invert_direction', 'foc_phase_filter_enable'})


def patch_fields(source, before, fields):
    """Copy the exact source bytes of the named motor fields; every other byte stays the target's."""
    source_spans, target_spans = motor_spans(source), motor_spans(before)
    if source_spans != target_spans:
        raise ValueError('Source and target motor serialization spans differ')
    if len(set(fields)) != len(fields):
        raise ValueError('Duplicate field in the copy scope')
    proposed, permitted = bytearray(before), set()
    for name in fields:
        start, end = target_spans[name]
        proposed[start:end] = source[start:end]
        permitted.update(range(start, end))
    if len(proposed) != len(before) or any(proposed[i] != before[i] for i in range(len(before)) if i not in permitted):
        raise ValueError('Package changed an unapproved motor byte')
    decode_configuration(proposed, DEFAULT_SCHEMA / 'parameters_mcconf.xml', 14)
    return bytes(proposed), target_spans


def filter_artifact(target_uuid):
    source = FILTER_SOURCE.read_bytes()
    if sha256(source) != FILTER_SOURCE_SHA or len(source) != 3981:
        raise ValueError('Reviewed autostart source changed; separate review required')
    core = source[:FILTER_CORE_BYTES]
    if sha256(core) != FILTER_CORE_SHA:
        raise ValueError('Reviewed reverse-filter core changed')
    def literal(uuid):
        return ('\'(' + ' '.join(str(n) for n in bytes.fromhex(uuid)) + ')').encode('ascii')
    old, new = literal(SOURCE_UUID), literal(target_uuid)
    if source.count(old) != 1 or old in core:
        raise ValueError('Expected exactly one UUID literal in the startup wrapper')
    adapted = source.replace(old, new, 1)
    if adapted[:FILTER_CORE_BYTES] != core:
        raise ValueError('Filter adaptation altered the tested core')
    blob = adapted + b'\0\0\0'  # ASCII program, NUL, uint16 import count zero.
    if b'\0' in adapted or len(blob) > 131072 - 8:
        raise ValueError('Invalid or oversized stored-code package')
    return adapted, blob


def prepare(source_raw, target_raw, *, kart_id, target_uuid, protection_limits=False):
    if type(kart_id) is not int or kart_id not in (4, 5):
        raise ValueError('Only kart IDs 4 and 5 are in scope; IDs 1/2 belong to Eamon and 3 is the source')
    if type(protection_limits) is not bool:
        raise ValueError('protection_limits is an explicit yes/no choice')
    target_uuid = uuid_text(target_uuid)
    if target_uuid in RESERVED_UUIDS:
        raise ValueError('Target UUID belongs to a reserved/source controller')
    source, source_bytes, source_manifest = snapshot(source_raw)
    target, before, before_manifest = snapshot(target_raw)
    identity_guard(source['identity'], SOURCE_UUID)
    identity_guard(target['identity'], target_uuid)
    capture_guard(source)
    capture_guard(target)
    if set(REVIEWED_TUNE) != set(TRIAL_FIELDS):
        raise ValueError('Named operating-tune scope changed')
    source_values = source['motor_configuration']['values']
    if any(source_values.get(k) != v for k, v in REVIEWED_TUNE.items()):
        raise ValueError('Source does not contain the reviewed twelve-field tune including motor braking -5 A')
    if source_values['l_in_current_min'] != -12 or any(source_values[k] != 1 for k in LIMIT_MATCH_FIELDS[:2]):
        raise ValueError('Source battery-regeneration/scales are not the reviewed baseline')
    if set(PROTECTION_LIMITS) & set(TRIAL_FIELDS):
        raise ValueError('Protection limits overlap the operating-tune scope')
    if protection_limits and any(source_values.get(k) != v for k, v in PROTECTION_LIMITS.items()):
        raise ValueError('Source does not hold the reviewed protection limits')
    fields = tuple(TRIAL_FIELDS) + (tuple(PROTECTION_LIMITS) if protection_limits else ())
    compare_decoded(source, target)
    proposed_motor, spans = patch_fields(source_bytes['motor_configuration'], before['motor_configuration'], fields)
    proposed_bytes = dict(before, motor_configuration=proposed_motor)
    proposed = decode_payloads(proposed_bytes)
    target_audit = compare_decoded(target, proposed)
    source_audit = compare_decoded(source, proposed)
    patches, remaining, blockers = [], [], []
    for field in fields:
        start, end = spans[field]
        patches.append({'field': field, 'before': target['motor_configuration']['values'][field],
                        'proposed': proposed['motor_configuration']['values'][field],
                        'offset_start': start, 'offset_end_exclusive': end,
                        'before_hex': before['motor_configuration'][start:end].hex(),
                        'proposed_hex': proposed_motor[start:end].hex()})
    changed = 0
    for group, audit in target_audit.items():
        for row in audit['fields']:
            allowed = group == 'motor_configuration' and row['field'] in fields
            row['action'] = 'copy_reviewed_source_bytes' if allowed else 'preserve_target_bytes'
            if row['status'] == 'different':
                if not allowed:
                    raise ValueError('Proposed configuration changed outside the fixed scope')
                changed += 1
    for group, audit in source_audit.items():
        for row in audit['fields']:
            if row['status'] == 'different':
                item = {'configuration': group, 'field': row['field'], 'source': row['reference'],
                        'retained_target': row['candidate'], 'needs_review': True,
                        'category': 'target_specific_preserved' if target_specific(group, row['field']) else 'operating_difference',
                        'must_resolve_before_commissioning': not target_specific(group, row['field'])}
                remaining.append(item)
                if item['must_resolve_before_commissioning']:
                    blockers.append(item)
    adapted, blob = filter_artifact(target_uuid)
    plan = {
        'format': 1, 'operation': 'offline_prepare_only', 'apply_supported': False,
        'status': 'prepared_not_applied_not_commissioned', 'kart_id': kart_id,
        'generated_at_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'source': {'identity': source['identity'], 'provenance': source['provenance']},
        'target': {'identity': target['identity'], 'provenance': target['provenance']},
        'source_persistence_verification': 'not established by runtime captures; review separate save/cold-boot evidence',
        'expected_before_sha256': {k: sha256(v) for k, v in before.items()},
        'allowlisted_motor_fields': list(fields), 'patches': patches,
        'protection_limits': {
            'copied': protection_limits, 'fields': dict(PROTECTION_LIMITS) if protection_limits else {},
            'authority': ('owner decision 2026-11-13: also set these five protection limits to the reviewed kart-3 values'
                          if protection_limits else 'not requested; target protection limits preserved')},
        'proposed_motor_response_sha256': sha256(proposed_motor),
        'proposed_motor_format': 'GET_MCCONF command-14 response payload, NOT a write command or serial frame',
        'summary': {'total_fields': 376, 'motor_fields': 189, 'app_fields': 187,
                    'changed_fields': changed, 'all_other_motor_bytes_preserved': True,
                    'all_application_bytes_preserved': True,
                    'remaining_source_differences': len(remaining),
                    'unresolved_operating_differences': len(blockers)},
        'target_vs_proposed_all_fields': target_audit,
        'source_vs_proposed_all_fields': source_audit,
        'remaining_differences': remaining,
        'commissioning_ready': False,
        'operating_differences_require_resolution': blockers,
        'filter': {'target_uuid': target_uuid, 'tested_core_sha256': FILTER_CORE_SHA,
                   'template_sha256': FILTER_SOURCE_SHA, 'source_sha256': sha256(adapted),
                   'code_blob_sha256': sha256(blob), 'code_blob_bytes': len(blob),
                   'code_blob_format': 'source + NUL + big-endian uint16 zero imports; no flash header or serial frame',
                   'header_flags_if_separately_installed': 0,
                   'crc16_flags_and_blob': binascii.crc_hqx(b'\0\0' + blob, 0),
                   'only_adaptation': 'startup UUID literal; tested core unchanged',
                   'native_app_preconditions': FILTER_PRECONDITIONS,
                   'kart3_installers_compatible': False},
        'scope_notes': [
            'This copies exactly twelve named operating settings, not the complete source tune.'
            + (' By explicit owner decision it also copies five protection limits: ' + ', '.join(PROTECTION_LIMITS) + '.'
               if protection_limits else ''),
            'Every remaining motor/app difference is listed and requires review. Resolve ordinary operating-limit differences before commissioning; never silently copy calibration to make a full match.',
            ('Target current scales are preserved and must be reviewed against source 1.0 / 1.0; battery regeneration is copied with the protection limits.'
             if protection_limits else
             'In particular, target battery-regeneration l_in_current_min and current scales are preserved and must be reviewed against source -12 A / 1.0 / 1.0.'),
            'Hall/motor parameters, controller measurement offsets, pedal endpoints, drivetrain metadata and all identities remain target-specific bytes. Kart ID is not the VESC controller_id.',
            'These dated runtime captures do not verify saved flash, present stationary state, hardware ratings or physical calibration. Complete backups and fresh matching readbacks are required before a separately reviewed write.',
            'Existing kart-3 apply_tune/install_rx_filter/RAM lifecycle helpers remain pinned to kart 3 and must not be used or have pins bypassed for this plan.',
            'Native ADC precedes Lisp startup; watchdog startup may skip Lisp; failed worker can hold direction. Keep pedal released until applied direction/live worker are verified. Repair the switch circuit independently.',
            'No serial, network, motor, configuration, flash or lifecycle action is available in this tool.',
        ],
    }
    return plan, {'source': source_bytes, 'before': before, 'source_manifest': source_manifest,
                  'before_manifest': before_manifest, 'proposed_motor': proposed_motor,
                  'filter_source': adapted, 'filter_blob': blob}


def render(plan):
    lines = [f'# Kart {plan["kart_id"]} replication — OFFLINE PREPARATION ONLY', '',
             '**Nothing applied. Not a complete tune match or commissioned vehicle.**', '',
             '| Field | Target capture | Proposed |', '| --- | ---: | ---: |']
    lines += ['| ' + p['field'] + ' | ' + cell(p['before']) + ' | ' + cell(p['proposed']) + ' |' for p in plan['patches']]
    lines += ['', '## Remaining source differences', '',
              '| Configuration / field | Source | Preserved target | Review category |',
              '| --- | ---: | ---: | --- |']
    lines += ['| ' + p['configuration'] + ' / ' + p['field'] + ' | ' + cell(p['source']) + ' | ' + cell(p['retained_target']) + ' | ' + p['category'] + ' |' for p in plan['remaining_differences']]
    lines += ['', '## Boundaries', ''] + ['- ' + s for s in plan['scope_notes']]
    return '\n'.join(lines) + '\n'


def write_plan(plan, artifacts, output):
    output = Path(output)
    encoded = json.dumps(plan, indent=2, allow_nan=False) + '\n'
    for side in ('source', 'target'):
        directory = Path(plan[side]['provenance']['manifest_path']).parent.resolve()
        if output.resolve() == directory or directory in output.resolve().parents:
            raise ValueError('Output must be outside both immutable capture directories')
    if output.is_symlink():
        raise FileExistsError('Output must be new, not a symlink')
    output.mkdir(parents=True, exist_ok=False)
    for side in ('source', 'before'):
        dest = output / side
        dest.mkdir()
        for name, data in artifacts[side].items():
            (dest / (name + '.bin')).write_bytes(data)
        (dest / 'manifest.json').write_bytes(artifacts[side + '_manifest'])
    (output / 'proposed_motor_response.bin').write_bytes(artifacts['proposed_motor'])
    (output / 'rx-filter-autostart.lisp').write_bytes(artifacts['filter_source'])
    (output / 'rx-filter-codeblob.bin').write_bytes(artifacts['filter_blob'])
    (output / 'plan.json').write_text(encoded)
    (output / 'README.md').write_text(render(plan))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-kart3', type=Path, required=True, help='Complete reviewed kart-3 runtime capture after -5 A correction')
    parser.add_argument('--target', type=Path, required=True, help='New kart-4/5 complete runtime capture')
    parser.add_argument('--kart-id', type=int, choices=(4, 5), required=True)
    parser.add_argument('--target-uuid', required=True, help='Actual UUID independently matched to the physically labeled target')
    parser.add_argument('--out', type=Path, required=True, help='New offline output directory')
    parser.add_argument('--match-protection-limits', action='store_true',
                        help='Also copy the five owner-approved protection limits (regen, absolute current, '
                             'input-voltage trips, fault stop time) from kart 3; an explicit per-kart choice')
    args = parser.parse_args()
    plan, artifacts = prepare(args.source_kart3, args.target, kart_id=args.kart_id, target_uuid=args.target_uuid,
                              protection_limits=args.match_protection_limits)
    write_plan(plan, artifacts, args.out)
    print(f'OFFLINE ONLY: {plan["summary"]["changed_fields"]} proposed field changes; '
          f'{plan["summary"]["unresolved_operating_differences"]} remaining operating differences require review. Nothing applied.')


if __name__ == '__main__':
    main()
