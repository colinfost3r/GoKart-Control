#!/usr/bin/env python3
"""Prepare an offline, byte-preserving kart-3 motor tune trial. No device/apply mode."""
import argparse
import datetime
import hashlib
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET

from capture import READ_COMMANDS
from compare import load_capture, manifest_path, compare_decoded, cell
from decode import DEFAULT_SCHEMA, Reader, decode_configuration, decode_payloads

REFERENCE_IDENTITY = {'uuid':'2c004c000951343037353739', 'firmware':'6.00', 'hardware':'75_100_V2'}
TARGET_IDENTITY = {'uuid':'37004e000951343037353739', 'firmware':'6.02', 'hardware':'75_300_R2'}
REFERENCE_MOTOR_SHA256 = '80ca33b7e5e5b0bfc08d039337f20c1ecf7f04b8726e35e87d938d40af33f0b0'
MOTOR_SCHEMA_SHA256 = 'b7cc767487bac6fc7526e29b4f71f54db4da0b29b9110b5de23d67fff74255b0'
# Fixed proposed scope prepared from the owner's tune-matching request. No arbitrary field/value input, app patch or whole-config copy.
TRIAL_FIELDS = (
    'l_current_max', 'l_current_min', 'l_in_current_max', 'l_min_erpm', 'l_max_erpm',
    'l_max_duty', 'foc_fw_current_max', 'foc_fw_duty_start', 'foc_openloop_rpm',
    'foc_sl_erpm', 'cc_ramp_step_max', 'm_motor_temp_sens_type',
)
PERSISTENCE_WARNING = (
    'A later COMM_SET_MCCONF (13) operation persists the complete motor configuration '
    'through conf_general_store_mc_configuration before applying it. This is NOT a '
    'temporary store=0 profile write. This tool does not send or construct a serial write '
    'frame, and a runtime export is not a verified saved-flash backup.'
)
PROTOCOL_SOURCE = 'https://github.com/vedderb/bldc/blob/f7c2b34e1cff2234cae98be3abf0cd50e249558f/comm/commands.c'


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def require_identity(actual, expected):
    if any(actual.get(key) != value for key, value in expected.items()):
        raise ValueError('Controller identity/firmware/hardware does not match this fixed trial')


def require_stationary(telemetry):
    # Historical zero-speed evidence is necessary to prepare this trial, but cannot
    # establish the physical state during a later write; that requires a fresh read.
    for name in ('erpm', 'motor_current_a', 'battery_current_a', 'fault_code'):
        value = telemetry.get(name)
        if not isinstance(value, (int, float)) or not math.isfinite(value) or value != 0:
            raise ValueError(f'Captured telemetry is not zero-current/stationary/fault-free: {name}')
    if telemetry.get('timeout_active') or telemetry.get('kill_switch_active'):
        raise ValueError('Captured timeout/kill-switch state needs review')


def snapshot(directory):
    directory = Path(directory).resolve(strict=True)
    decoded = load_capture(directory)  # complete dated manifest, hashes, identity, both schemas
    payloads = {name:(directory/(name+'.bin')).read_bytes() for name in READ_COMMANDS.values()}
    for query in decoded['provenance']['queries']:
        if sha256(payloads[query['name']]) != query['sha256']:
            raise ValueError('Capture changed while preparing its snapshot')
    manifest_bytes = manifest_path(directory).read_bytes()
    if sha256(manifest_bytes) != decoded['provenance']['manifest_sha256']:
        raise ValueError('Manifest changed while preparing its snapshot')
    # The exact bytes used for offsets and patching must decode to the validated values.
    again = decode_payloads(payloads)
    if any(again[k] != decoded[k] for k in again):
        raise ValueError('Capture decoding changed during snapshot')
    return decoded, payloads, manifest_bytes


def motor_spans(payload):
    schema = DEFAULT_SCHEMA/'parameters_mcconf.xml'
    if sha256(schema.read_bytes()) != MOTOR_SCHEMA_SHA256:
        raise ValueError('Pinned motor schema bytes changed')
    decoded = decode_configuration(payload, schema, 14)
    if len(decoded['values']) != 189 or decoded['signature_hex'] != '2e43a161':
        raise ValueError('Unsupported motor configuration schema')
    root = ET.parse(schema).getroot()
    params = {p.tag:p for p in root.find('Params')}
    reader, spans = Reader(payload, 5), {}
    for item in root.find('SerOrder'):
        name, param = item.text, params[item.text]
        start = reader.pos
        kind, tx = int(param.findtext('type','0')), int(param.findtext('vTx','0'))
        if kind in (4,5,6):
            reader.read('B')
        elif kind == 2:
            reader.read({1:'B',2:'b',3:'H',4:'h',5:'I',6:'i'}[tx])
        elif kind == 1:
            reader.read('H' if tx == 7 else 'I')
        elif kind == 3:
            reader.string()
        else:
            raise ValueError(f'Unsupported motor field {name}')
        spans[name] = (start, reader.pos)
    if reader.pos != len(payload) or set(spans) != set(decoded['values']):
        raise ValueError('Motor byte spans do not cover the exact decoded field set')
    return spans


def patch_motor(reference, before):
    source_spans, target_spans = motor_spans(reference), motor_spans(before)
    if source_spans != target_spans:
        raise ValueError('Reference and target motor serialization spans differ')
    proposed, permitted = bytearray(before), set()
    for name in TRIAL_FIELDS:
        start,end = target_spans[name]
        proposed[start:end] = reference[start:end]
        permitted.update(range(start,end))
    if len(proposed) != len(before) or any(proposed[i] != before[i] for i in range(len(before)) if i not in permitted):
        raise ValueError('Trial changed an unapproved motor byte')
    decode_configuration(proposed, DEFAULT_SCHEMA/'parameters_mcconf.xml', 14)
    return bytes(proposed), target_spans


def prepare(reference_raw, current_raw):
    reference, source, source_manifest = snapshot(reference_raw)
    current, before, before_manifest = snapshot(current_raw)
    require_identity(reference['identity'], REFERENCE_IDENTITY)
    require_identity(current['identity'], TARGET_IDENTITY)
    if sha256(source['motor_configuration']) != REFERENCE_MOTOR_SHA256:
        raise ValueError('Reference motor payload is not the exact dated November 5 baseline')
    require_stationary(current['telemetry'])
    # Includes both complete known field sets, even though no app byte is patched.
    compare_decoded(reference, current)
    proposed_motor, spans = patch_motor(source['motor_configuration'], before['motor_configuration'])
    proposed_payloads = dict(before)
    proposed_payloads['motor_configuration'] = proposed_motor
    proposed = decode_payloads(proposed_payloads)
    audit = compare_decoded(current, proposed)
    actual_changed = set()
    for group, data in audit.items():
        for row in data['fields']:
            allowed = group == 'motor_configuration' and row['field'] in TRIAL_FIELDS
            row['trial_action'] = 'copy_exact_reference_bytes' if allowed else 'retain_exact_current_bytes'
            if row['status'] == 'different':
                if not allowed:
                    raise ValueError('Proposed values changed outside the fixed motor trial')
                actual_changed.add(row['field'])
    assert proposed_payloads['app_configuration'] == before['app_configuration']
    patches = []
    for name in TRIAL_FIELDS:
        start,end = spans[name]
        patches.append({'field':name, 'before':current['motor_configuration']['values'][name],
                        'proposed':proposed['motor_configuration']['values'][name],
                        'reference':reference['motor_configuration']['values'][name],
                        'payload_offset_start':start, 'payload_offset_end_exclusive':end,
                        'before_hex':before['motor_configuration'][start:end].hex(),
                        'proposed_hex':proposed_motor[start:end].hex(),
                        'changed':name in actual_changed})
    plan = {
        'trial_format':1, 'operation':'offline_prepare_only', 'apply_supported':False,
        'generated_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'status':'review_trial_not_applied_not_safety_certification',
        'reference':{'identity':reference['identity'],'provenance':reference['provenance']},
        'current':{'identity':current['identity'],'provenance':current['provenance']},
        'expected_target_identity':TARGET_IDENTITY,
        'expected_before_sha256':{name:sha256(data) for name,data in before.items()},
        'proposed_motor_response_sha256':sha256(proposed_motor),
        'proposed_motor_file':'proposed_motor_response.bin',
        'proposed_motor_format':'GET_MCCONF-shaped response payload (command 14), NOT a serial frame or SET_MCCONF command',
        'allowlisted_motor_fields':list(TRIAL_FIELDS), 'patches':patches,
        'summary':{'motor_fields':189,'app_fields':187,'total_fields':376,
                   'allowlisted_fields':12,'actually_changed_fields':len(actual_changed),
                   'retained_value_fields':376-len(actual_changed),'application_bytes_unchanged':True,
                   'all_nonallowlisted_motor_bytes_unchanged':True},
        'field_audit':audit, 'persistence_warning':PERSISTENCE_WARNING,
        'protocol_source':PROTOCOL_SOURCE,
        'notes':[
            "Proposed trial prepared from the owner's tune-matching request; the owner did not individually select these twelve values. In particular, 15 to 95 A field weakening is a 6.33x increase; historical use does not establish physical ratings or thermal headroom.",
            'All application bytes stay unchanged, including ADC endpoints, reverse/input selection, CAN identity and every other app setting. This trial does not diagnose or fix the reported reverse-switch issue (throttle on ADC1, reverse switch on TX).',
            'Retain Hall mapping, motor R/L/flux, gains, offsets, position calibration, hardware phase filters, drivetrain metadata, battery regen -12 A, speed-PID braking 0, absolute overcurrent 220 A and minimum VIN 60 V.',
            'Changing the unwired motor-temperature sensor selection to Disabled does not create motor-temperature protection. A zero motor-braking allowance does not prove every regenerative path is disabled.',
            'The baseline drivetrain metadata is known-questionable and uses a Heltec 2.48 compensation. No poles/gearing/wheel/speedcal change is part of this trial.',
            'cc_ramp_step_max is described for DC/BLDC; both captured motors use FOC. Copying it is not evidence of improved FOC acceleration.',
            'The before snapshot remains dated runtime evidence. Preparing files does not establish present stationary state, current settings, saved-flash backup or successful application.',
        ],
        'future_apply_requirements':[
            'Separate reviewed application procedure; no apply/device option is implemented here.',
            'Verify intended USB device and exact fresh target UUID, hardware and firmware, with owner present, wheels lifted, pedals released and physical cutoff available.',
            'Read all four fresh payloads immediately before writing; require complete motor/app bytes exactly equal to expected_before and stationary zero-current, zero-ERPM, fault-free telemetry. Reject any mismatch, do not regenerate silently.',
            'If subsequently implemented and reviewed: at most one persistent full MCCONF write, no retry after timeout/partial send/missing ACK, no reset, motor detection or motor command; never write APPCONF.',
            'Require exact write ACK and a new complete four-payload readback; all 376 fields and preserved raw bytes must match. Record timestamped before/after manifests and classify missing ACK/readback or unexpected changes as ambiguous rather than success.',
        ],
    }
    return plan, {'reference':source, 'before':before, 'reference_manifest':source_manifest,
                  'before_manifest':before_manifest, 'proposed_motor':proposed_motor}


def render_plan(plan):
    lines=['# Kart 3 motor tune trial — PREPARED ONLY', '',
           "**No settings applied. This is a proposed trial prepared from the owner's tune-matching request, not a safety certification.**', '",
           plan['persistence_warning'], '',
           'All 187 application settings and all nonallowlisted motor bytes remain unchanged. '
           'The reported reverse-switch issue is not changed by this trial.', '',
           '| Motor field | Current snapshot | Proposed trial |', '| --- | ---: | ---: |']
    for row in plan['patches']:
        lines.append('| '+row['field']+' | '+cell(row['before'])+' | '+cell(row['proposed'])+' |')
    lines += ['', '## Limits and preservation', '']+['- '+note for note in plan['notes']]
    lines += ['', '## Before any application', '']+['- '+note for note in plan['future_apply_requirements']]
    lines += ['', 'The full 376-field audit, exact byte spans and expected hashes are in `trial.json`. '
              '`proposed_motor_response.bin` is a response-shaped analysis artifact, not a serial write frame. '
              '`before/` and `reference/` contain unchanged copies of the original dated input evidence.', '']
    return '\n'.join(lines)


def write_trial(plan, artifacts, out):
    encoded=json.dumps(plan,indent=2,allow_nan=False)+'\n'
    markdown=render_plan(plan)
    out=Path(out)
    # Avoid placing derived trial output within either immutable source capture.
    resolved=out.resolve()
    for side in ('reference','current'):
        source=Path(plan[side]['provenance']['manifest_path']).parent.resolve()
        if resolved==source or source in resolved.parents:
            raise ValueError('Trial output must be outside the immutable source capture folders')
    out.mkdir(parents=True,exist_ok=False)
    for side in ('reference','before'):
        directory=out/side;directory.mkdir()
        for name,data in artifacts[side].items():
            (directory/(name+'.bin')).write_bytes(data)
        (directory/'manifest.json').write_bytes(artifacts[side+'_manifest'])
    (out/'proposed_motor_response.bin').write_bytes(artifacts['proposed_motor'])
    (out/'trial.json').write_text(encoded)
    (out/'README.md').write_text(markdown)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('reference_raw',type=Path,help='Dated Nov 5 baseline raw directory')
    parser.add_argument('current_raw',type=Path,help='Complete explicit kart 3 raw capture directory')
    parser.add_argument('--out',type=Path,required=True,help='New offline trial directory; existing paths rejected')
    args=parser.parse_args()
    if args.out.exists() or args.out.is_symlink():
        raise FileExistsError(f'Output must be new: {args.out}')
    plan,artifacts=prepare(args.reference_raw,args.current_raw)
    write_trial(plan,artifacts,args.out)
    print(f"Prepared {plan['summary']['actually_changed_fields']} motor-field changes; "
          'all application bytes retained. OFFLINE ONLY: no settings applied; no device/apply mode.')


if __name__=='__main__':
    main()
