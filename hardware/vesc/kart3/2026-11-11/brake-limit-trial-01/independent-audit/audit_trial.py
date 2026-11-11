#!/usr/bin/env python3
"""Recompute the temporary -5 A trial evidence offline. Never opens a port.

Usage: python3 -B audit_trial.py --repo /path/to/project --out /new/output
Inputs are recorded raw payloads, JSONL samples, and capture manifests only.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import struct
import sys

SESSION = Path('hardware/vesc/kart3/2026-11-11/brake-limit-trial-01')


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True, help='New directory; refuses overwrite')
    args = parser.parse_args()
    repo = args.repo.resolve(strict=True)
    base = repo / SESSION
    output = args.out.resolve()
    sys.path.insert(0, str(repo / 'tools/vesc'))
    from decode import decode_configuration, decode_telemetry, DEFAULT_SCHEMA

    def artifact(path):
        raw = path.read_bytes()
        return {'file': str(path.relative_to(repo)), 'bytes': len(raw), 'sha256': digest(raw)}

    inputs = []

    def read_json(path):
        inputs.append(artifact(path))
        return json.loads(path.read_text())

    sample_path = base / 'trace/samples.jsonl'
    inputs.append(artifact(sample_path))
    rows = [json.loads(line) for line in sample_path.read_text().splitlines()]
    assert rows and all(b['seconds'] > a['seconds'] for a, b in zip(rows, rows[1:]))
    manifest = read_json(base / 'trace/manifest.json')
    assert manifest['complete'] is True and manifest['rows'] == len(rows)
    recorder = base / 'host-tools/triggered_brake5_trace.py'
    inputs.append(artifact(recorder))
    assert digest(recorder.read_bytes()) == manifest['script_sha256']
    assert manifest['trigger'] == 'decodedADC1>.20, absERPM<=50, absIq<8 A for >=.20s; samples gaps>.35s reset'
    assert "abs(row['telemetry']['iq_a'])<8.0" in recorder.read_text()
    for row in rows:
        assert decode_telemetry(bytes.fromhex(row['values_hex'])) == row['telemetry']
        raw_adc = bytes.fromhex(row['adc_hex'])
        assert len(raw_adc) == 17 and raw_adc[0] == 32
        adc = dict(zip(('decoded1', 'voltage1', 'decoded2', 'voltage2'),
                       (value / 1e6 for value in struct.unpack('>iiii', raw_adc[1:]))))
        assert adc == row['adc']

    settings = {}
    for name in ('apply', 'trace', 'restore-zero'):
        entry = {}
        for kind, command, schema, count in (
                ('motor', 14, 'parameters_mcconf.xml', 189),
                ('app', 17, 'parameters_appconf.xml', 187)):
            paths = [base / name / (kind + '_' + phase + '.bin') for phase in ('before', 'after')]
            inputs.extend(artifact(path) for path in paths)
            raw = [path.read_bytes() for path in paths]
            values = [decode_configuration(data, DEFAULT_SCHEMA / schema, command)['values'] for data in raw]
            assert all(len(value) == count for value in values)
            changes = {key: {'before': values[0][key], 'after': values[1][key]}
                       for key in values[0] if values[0][key] != values[1][key]}
            entry[kind] = {'field_count': count, 'changed': changes, 'byte_identical': raw[0] == raw[1]}
            if name == 'trace' and kind == 'app':
                native_hyst = values[0]['app_adc_conf.hyst']
        settings[name] = entry
    assert settings['apply']['motor']['changed'] == {'l_current_min': {'before': 0.0, 'after': -5.0}}
    assert settings['restore-zero']['motor']['changed'] == {'l_current_min': {'before': -5.0, 'after': 0.0}}
    assert all(not value['app']['changed'] for value in settings.values())
    assert settings['trace']['motor']['byte_identical'] and settings['trace']['app']['byte_identical']

    # A window is a contiguous run of sampled pedal values above the threshold.
    # It is not a claim that the wheels started from rest at each window.
    windows = []
    start = None
    for index, row in enumerate(rows):
        if row['adc']['decoded1'] > 0.15:
            if start is None:
                start = index
        elif start is not None:
            windows.append((start, index - 1))
            start = None
    if start is not None:
        windows.append((start, len(rows) - 1))
    window_details = []
    for start, end in windows:
        subset = rows[start:end + 1]
        peak = max(abs(row['telemetry']['erpm']) for row in subset)
        window_details.append({'first_row_zero_based': start, 'last_row_zero_based': end,
            'start_seconds': subset[0]['seconds'], 'end_seconds': subset[-1]['seconds'],
            'sample_count': len(subset), 'peak_absolute_erpm': peak,
            'rotation_observed_above_50_erpm': peak > 50})
    threshold_disagreements = [i for i, row in enumerate(rows)
        if (row['adc']['decoded1'] > 0.15) != (row['adc']['decoded1'] > native_hyst)]
    assert not threshold_disagreements

    # Reproduce the recorder's sustained diagnostic trigger, without importing it.
    qualifying = []
    sustained = []
    since = last = None
    for index, row in enumerate(rows):
        now = row['seconds']
        if last is not None and (now < last or now - last > 0.35):
            since = None
        last = now
        candidate = (row['adc']['decoded1'] > 0.20 and abs(row['telemetry']['erpm']) <= 50
                     and abs(row['telemetry']['iq_a']) < 8.0)
        if not candidate:
            since = None
            continue
        qualifying.append(index)
        if since is None:
            since = now
        if now - since >= 0.20:
            sustained.append(index)

    faults = Counter(row['telemetry']['fault_code'] for row in rows)
    timeout_count = sum(bool(row['telemetry']['timeout_active']) for row in rows)
    kill_count = sum(bool(row['telemetry']['kill_switch_active']) for row in rows)
    history = manifest['fault_history']['terminal_lines']
    assert len(windows) == 78 and all(item['rotation_observed_above_50_erpm'] for item in window_details)
    assert len(qualifying) == 17 and not sustained and len(manifest['snapshots']) == 0
    assert faults == {0: len(rows)} and timeout_count == kill_count == 0
    assert 'No faults registered since startup' in history

    peak_voltage_index = max(range(len(rows)), key=lambda i: rows[i]['telemetry']['input_voltage_v'])
    voltage_context = []
    for index in range(max(0, peak_voltage_index - 3), min(len(rows), peak_voltage_index + 4)):
        row = rows[index]
        voltage_context.append({
            'row_zero_based': index,
            'adc_timestamp_seconds_from_recording_start': row['seconds'],
            'values_timestamp_seconds_from_recording_start':
                row['seconds'] + row['values_at_monotonic'] - row['adc_at_monotonic'],
            'decoded_pedal': row['adc']['decoded1'], 'pedal_voltage_v': row['adc']['voltage1'],
            **{key: row['telemetry'][key] for key in (
                'input_voltage_v', 'battery_current_a', 'motor_current_a', 'iq_a', 'erpm', 'duty', 'fault_code')},
        })

    summary = {
        'scope': 'Independent offline audit of existing evidence; no serial or hardware access',
        'session': str(SESSION), 'sample_count': len(rows),
        'raw_adc_and_values_redecoded_and_equal_to_recorded_fields': True,
        'first_sample_seconds': rows[0]['seconds'], 'last_sample_seconds': rows[-1]['seconds'],
        'sample_span_seconds': rows[-1]['seconds'] - rows[0]['seconds'],
        'maximum_sample_gap_seconds': max(b['seconds'] - a['seconds'] for a, b in zip(rows, rows[1:])),
        'pedal_windows': {
            'definition': 'Contiguous sampled decodedADC1 > 0.15; not independent starts from full rest',
            'analysis_threshold': 0.15, 'native_app_hyst': native_hyst,
            'threshold_classification_disagreement_count': len(threshold_disagreements),
            'count': len(windows), 'above_threshold_sample_count': sum(item['sample_count'] for item in window_details),
            'windows_with_observed_absolute_erpm_above_50': sum(item['rotation_observed_above_50_erpm'] for item in window_details),
            'smallest_window_peak_absolute_erpm': min(item['peak_absolute_erpm'] for item in window_details),
            'windows': window_details,
        },
        'missed_start_trigger': {
            'instantaneous_condition': 'decodedADC1 > 0.20 and abs(ERPM) <= 50 and abs(Iq) < 8 A',
            'actual_archived_recorder_hash_matches_manifest': True,
            'sustained_condition': 'Condition maintained in sampled data for >=0.20 s; sample gaps >0.35 s reset qualification',
            'instantaneous_qualifying_sample_count': len(qualifying),
            'instantaneous_qualifying_rows_zero_based': qualifying,
            'sustained_qualifying_sample_count': len(sustained),
            'recorded_internal_diagnostic_snapshot_count': len(manifest['snapshots']),
            'limitation': 'Zero sustained triggers does not prove absence of every shorter hesitation or unsampled event.',
        },
        'faults': {'code_counts': dict(faults), 'timeout_active_samples': timeout_count,
                   'kill_switch_active_samples': kill_count, 'terminal_history_response': history},
        'bus_voltage_observation': {
            'minimum_v': min(row['telemetry']['input_voltage_v'] for row in rows),
            'maximum_v': rows[peak_voltage_index]['telemetry']['input_voltage_v'],
            'sample_count_above_84_v': sum(row['telemetry']['input_voltage_v'] > 84.0 for row in rows),
            'maximum_row_zero_based': peak_voltage_index,
            'peak_and_three_surrounding_rows_each_side': voltage_context,
            'capture_manifest_started_utc': manifest['started_utc'],
            'timestamp_scope': 'Exact elapsed sample timestamps are supplied. The manifest start precedes preflight and is not the recording-start UTC; no exact UTC peak time is inferred.',
            'interpretation_limit': 'The 84.4 V peak is an observed bus reading after a pedal release. Its same-record battery current is +2.96 A, while negative readings occur later. Current fields are telemetry averages; these samples do not establish a causal mechanism, continuous regenerative braking, or an overvoltage fault. Treat this as a charged-pack/regen validation item.',
        },
        'settings': settings,
        'trace_end': {'sample_erpm': rows[-1]['telemetry']['erpm'], 'filter_status_after': manifest['status_after'],
                      'caveat': 'Recording ended while the wheels were still coasting in reverse; later restore preflight is separate stop evidence.'},
        'measurement_limits': 'Operator-controlled wheels-up test at approximately 9 Hz. Contiguous pedal windows can occur while wheels are already rotating. Does not establish loaded/fleet reliability or permanence.',
        'input_artifacts': inputs,
        'decoder_provenance': {str(path.relative_to(repo)): digest(path.read_bytes()) for path in [
            repo / 'tools/vesc/decode.py', DEFAULT_SCHEMA / 'parameters_mcconf.xml', DEFAULT_SCHEMA / 'parameters_appconf.xml']},
        'audit_script_sha256': digest(Path(__file__).read_bytes()),
    }
    output.mkdir(parents=True, exist_ok=False)
    (output / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps({'samples': len(rows), 'pedal_windows': len(windows), 'all_windows_contain_rotation': True,
                      'fault_samples': 0, 'instantaneous_trigger_samples': len(qualifying),
                      'sustained_triggers': len(sustained), 'recorded_snapshots': len(manifest['snapshots']),
                      'threshold_classification_disagreements': 0, 'summary': str(output / 'summary.json')}))


if __name__ == '__main__':
    main()
