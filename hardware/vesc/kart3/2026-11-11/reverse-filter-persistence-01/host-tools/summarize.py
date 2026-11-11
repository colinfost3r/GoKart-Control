#!/usr/bin/env python3
"""Offline audit only. Reads recorded configuration/serial evidence; no ports."""
import binascii
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys
import tarfile

ROOT = Path('/Users/cofo/Projects/50 Day/GoKart Control/.worktrees/m5-v1.5')
BASE = ROOT / 'hardware/vesc/kart3/2026-11-11/reverse-filter-persistence-01'
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'tools/vesc'))
from decode import decode_configuration, DEFAULT_SCHEMA
from capture import PacketParser

COMMIT = 'f7c2b34e1cff2234cae98be3abf0cd50e249558f'
OFFSETS = ['foc_offsets_current__' + str(i) for i in range(3)] + ['foc_offsets_voltage__' + str(i) for i in range(3)]
SESSIONS = ['install', 'coldboot-forward', 'coldboot-reverse', 'coldboot-reverse-confirm', 'final-forward']

def sha(data):
    return hashlib.sha256(data).hexdigest()

def artifact(path):
    raw = path.read_bytes()
    return {'file': str(path.relative_to(BASE)), 'bytes': len(raw), 'sha256': sha(raw)}

def frame(payload):
    header = bytes((2, len(payload))) if len(payload) < 256 else bytes((3,)) + len(payload).to_bytes(2, 'big')
    return header + payload + binascii.crc_hqx(payload, 0).to_bytes(2, 'big') + b'\3'

def tx_audit(path):
    raw = path.read_bytes()
    parser = PacketParser()
    packets = parser.feed(raw)
    assert not parser.buffer and b''.join(frame(p) for p in packets) == raw
    result = artifact(path)
    result['packet_counts_by_command'] = dict(sorted(Counter(p[0] for p in packets).items()))
    result['repl_expressions'] = sorted(set(p[1:].rstrip(b'\0').decode('ascii') for p in packets if p[0] == 138))
    result['all_frames_crc_valid_no_unparsed_bytes'] = True
    result['tune_write_or_activation_commands_present'] = sorted(set(p[0] for p in packets) & {13, 16, 133})
    return result

def values(session, when, kind):
    command, schema, expected_count = (14, 'parameters_mcconf.xml', 189) if kind == 'motor' else (17, 'parameters_appconf.xml', 187)
    path = BASE / session / (kind + '_' + when + '.bin')
    decoded = decode_configuration(path.read_bytes(), DEFAULT_SCHEMA / schema, command)
    assert len(decoded['values']) == expected_count
    return decoded['values']

def compare(left_session, left_phase, right_session, right_phase):
    comparisons = {}
    for kind in ('motor', 'app'):
        left = values(left_session, left_phase, kind)
        right = values(right_session, right_phase, kind)
        assert left.keys() == right.keys()
        changed = {name: {'before': value, 'after': right[name]} for name, value in left.items() if value != right[name]}
        comparisons[kind] = {'field_count': len(left), 'equal_count': len(left) - len(changed), 'changed': changed,
                             'before': artifact(BASE / left_session / (kind + '_' + left_phase + '.bin')),
                             'after': artifact(BASE / right_session / (kind + '_' + right_phase + '.bin')),
                             'byte_identical': (BASE / left_session / (kind + '_' + left_phase + '.bin')).read_bytes() == (BASE / right_session / (kind + '_' + right_phase + '.bin')).read_bytes()}
    return comparisons

result = {'scope': 'Independent offline interpretation of recorded evidence; no hardware I/O by this audit',
          'evidence_root_repository_relative': str(BASE.relative_to(ROOT)), 'source_commit': COMMIT,
          'total_fields_per_capture': 376, 'motor_fields': 189, 'app_fields': 187,
          'boot_measurement_offset_fields': OFFSETS, 'sessions': {}, 'cross_boot_comparisons': {},
          'all_field_values_by_session': {}, 'source_verification': []}

for name in SESSIONS:
    manifest_path = BASE / name / 'manifest.json'
    manifest = json.loads(manifest_path.read_text())
    comparison = compare(name, 'before', name, 'after')
    assert all(v['byte_identical'] for v in comparison.values())
    entry = {'manifest': artifact(manifest_path), 'complete': manifest['complete'],
             'within_session': comparison, 'status': manifest.get('status_before'),
             'context_snapshot': manifest.get('contexts_before'),
             'transmitted_packets': tx_audit(BASE / name / 'tx-attempts.bin')}
    assert not entry['transmitted_packets']['tune_write_or_activation_commands_present']
    result['sessions'][name] = entry
    result['all_field_values_by_session'][name] = {kind: values(name, 'after', kind) for kind in ('motor', 'app')}

for right in SESSIONS[1:]:
    comparison = compare('install', 'after', right, 'after')
    assert not comparison['app']['changed']
    assert set(comparison['motor']['changed']) <= set(OFFSETS)
    assert values(right, 'after', 'motor')['foc_offsets_cal_on_boot'] == 1
    result['cross_boot_comparisons']['install_to_' + right] = comparison
result['cross_boot_comparisons']['forward_boot_to_reverse_boot'] = compare('coldboot-forward', 'after', 'coldboot-reverse', 'after')

archive = Path('/tmp/gokart-bldc-602.tar.gz')
result['source_archive'] = {'sha256': sha(archive.read_bytes()), 'commit': COMMIT}
sources = [('motor/mcpwm_foc.c', Path('/tmp/gokart-rx-session-20261111/mcpwm_foc.c'), [463, 532, 2415, 2424]),
           ('motor/mc_interface.c', Path('/tmp/gokart-rx-session-20261111/mc_interface.c'), [298]),
           ('comm/commands.c', Path('/tmp/gokart-602-commands.c'), [573, 578])]
with tarfile.open(archive, 'r:gz') as source_tar:
    for relative, local, line_refs in sources:
        raw = source_tar.extractfile('bldc-' + COMMIT + '/' + relative).read()
        assert raw == local.read_bytes(), relative
        result['source_verification'].append({'repository_path': relative, 'sha256': sha(raw),
            'local_reviewed_copy_matches_pinned_archive': True, 'relevant_lines': line_refs,
            'url': 'https://github.com/vedderb/bldc/blob/' + COMMIT + '/' + relative})

final_manifest = json.loads((BASE / 'final-contexts/manifest.json').read_text())
text_rows = [json.loads(line) for line in (BASE / 'final-contexts/packets.jsonl').read_text().splitlines()]
final_text = [row['text'] for row in text_rows if 'text' in row]
assert 'ContextID: 1507' in final_text and 'Stack SP max: 44' in final_text
result['final_context_proof'] = {'manifest': artifact(BASE / 'final-contexts/manifest.json'),
    'packets': artifact(BASE / 'final-contexts/packets.jsonl'), 'complete': final_manifest['complete'],
    'reported_context_id': 1507, 'reported_queue': 'Sleeping contexts', 'reported_stack_sp_max': 44,
    'complete_printed_text': final_text,
    'limitation': 'A point-in-time queue snapshot. Earlier absent PID listings do not prove worker absence; :ctxs omits the currently executing context.'}

installed = (BASE / 'install/code-readback.bin').read_bytes()
stored = (BASE / 'stored-after-coldboots/lisp_code.bin').read_bytes()
assert installed == stored and len(stored) == 3984
assert sha(stored) == 'a2461adda272a014506cc76f0bdbf2240c85dff39842c6dac8655b4e0be34801'
result['stored_payload_after_coldboots'] = {**artifact(BASE / 'stored-after-coldboots/lisp_code.bin'),
    'manifest': artifact(BASE / 'stored-after-coldboots/manifest.json'), 'byte_identical_to_install_readback': True,
    'scope': 'Code blob including NUL and zero import count; excludes eight-byte flash header. Header flags are not independently readable through command 130.'}
result['interpretation'] = {'all_settings_byte_identical_during_install': True,
    'all_settings_byte_identical_within_each_status_capture': True,
    'all_settings_byte_identical_across_coldboots': False,
    'all_187_app_fields_preserved_across_boots': True,
    'all_183_nonmeasurement_offset_motor_fields_preserved_across_boots': True,
    'hall_and_pedal_calibration_preserved': True,
    'measurement_offsets_restored_by_audit': False,
    'explanation': 'With foc_offsets_cal_on_boot=1, native 6.02 initialization calls mcpwm_foc_dc_cal(false), which updates current and phase-voltage measurement offsets in the runtime motor configuration. GET_MCCONF serializes that runtime structure. The observed changes are confined to exactly these native-calibrated fields, consistent with automatic boot calibration, not a tune rewrite.',
    'limits': 'No instrumented function-call trace proves calibration execution. This is source-backed interpretation of matching field changes and the enabled flag. These stationary boot checks do not replace post-install driving tests.'}
for schema in ('parameters_mcconf.xml', 'parameters_appconf.xml'):
    result.setdefault('decoder_provenance', {})[schema] = sha((DEFAULT_SCHEMA / schema).read_bytes())
result['decoder_provenance']['decode_py_sha256'] = sha((ROOT / 'tools/vesc/decode.py').read_bytes())
(OUT / 'summary.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps({'summary': str(OUT / 'summary.json'), 'sessions': len(SESSIONS),
                  'install_to_forward_changed_fields': len(result['cross_boot_comparisons']['install_to_coldboot-forward']['motor']['changed']),
                  'install_to_reverse_changed_fields': len(result['cross_boot_comparisons']['install_to_coldboot-reverse']['motor']['changed']),
                  'all_other_motor_and_app_fields_preserved': True, 'stored_bytes': len(stored)}))
