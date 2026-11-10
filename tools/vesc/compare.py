#!/usr/bin/env python3
"""Compare every setting in two complete VESC runtime captures; offline, never apply."""
import argparse
import datetime
import hashlib
import html
import json
from pathlib import Path
import xml.etree.ElementTree as ET

from capture import READ_COMMANDS
from decode import DEFAULT_SCHEMA, decode_payloads

SCOPE = 'current_runtime_not_verified_saved_flash'
CONFIGURATIONS = {
    'motor_configuration': ('parameters_mcconf.xml', 189, '2e43a161'),
    'app_configuration': ('parameters_appconf.xml', 187, '1d003a2c'),
}
NOTES = [
    'This is an offline comparison of dated, sequential runtime reads, not current live state, '
    'an atomic snapshot, a saved-flash backup, or a tuning/import preset.',
    'Equal/different means exact decoded value equality; no tolerance, preferred value, '
    'copy decision or automatic change recommendation is applied.',
    'The November 5, 2026 baseline is historical runtime evidence; it does not establish '
    "kart 2's current tune. The candidate capture is dated separately below; refresh both reads before applying a tune.",
    'The project handoff dated November 10 reports kart 2 drivetrain values wrong by about '
    '2.5x and a Heltec speed-calibration factor of 2.48 compensating for them. Do not blindly '
    'copy si_motor_poles, si_gear_ratio or si_wheel_diameter, or set speedcal to 1.0 without '
    'physical measurement and speed validation. Heltec speedcal is not in these VESC captures.',
    'Matching motor/battery/BMS/gearing/wheel models does not make controller/motor '
    'calibration, pedal endpoints, identities or protection settings interchangeable.',
    'Motor-temperature sensors on these karts are not wired; a raw motor-temperature '
    'value is not a valid measured motor temperature. ESC temperature is separate.',
    'Payload hashes are checked against the supplied manifests. Transport CRC verification '
    'is a capture-time manifest claim; raw payload files omit transport frames.',
]


def timestamp(value, name):
    if not isinstance(value, str):
        raise ValueError(f'{name}: missing dated capture timestamp')
    try:
        parsed = datetime.datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError as error:
        raise ValueError(f'{name}: invalid capture timestamp') from error
    if parsed.tzinfo is None:
        raise ValueError(f'{name}: capture timestamp needs a timezone')
    return value


def manifest_path(directory, explicit=None):
    if explicit is not None:
        return Path(explicit).resolve(strict=True)
    options = [directory/'manifest.json']
    # The immutable original baseline predates the CLI and stores its manifest
    # next to raw/. Other arbitrary parent directories are never searched.
    if directory.name == 'raw':
        options.append(directory.parent/'manifest.json')
    found = [p for p in options if p.is_file()]
    if len(found) != 1:
        raise ValueError(f'{directory}: expected one manifest; give an explicit manifest path')
    return found[0]


def load_capture(directory, explicit_manifest=None):
    directory = Path(directory).resolve(strict=True)
    path = manifest_path(directory, explicit_manifest)
    manifest_bytes = path.read_bytes()
    manifest = json.loads(manifest_bytes)
    if not isinstance(manifest, dict) or manifest.get('capture_complete') is not True:
        raise ValueError(f'{path}: capture is incomplete')
    if manifest.get('scope') != SCOPE:
        raise ValueError(f'{path}: unsupported or missing runtime capture scope')
    queries = manifest.get('queries')
    if not isinstance(queries, list) or len(queries) != len(READ_COMMANDS):
        raise ValueError(f'{path}: expected exactly four read-query records')
    by_name = {}
    for query in queries:
        if not isinstance(query, dict):
            raise ValueError(f'{path}: invalid query record')
        name, command = query.get('name'), query.get('command')
        if (not isinstance(name, str) or type(command) is not int or
                READ_COMMANDS.get(command) != name or name in by_name):
            raise ValueError(f'{path}: unexpected or duplicate read-query record')
        by_name[name] = query
    payloads, records = {}, []
    for command, name in READ_COMMANDS.items():
        query = by_name[name]
        payload = (directory/(name+'.bin')).read_bytes()
        digest = hashlib.sha256(payload).hexdigest()
        if len(payload) != query.get('payload_bytes') or digest != query.get('sha256'):
            raise ValueError(f'{directory}/{name}.bin: manifest size/hash mismatch')
        if not (query.get('crc_verified') is True or query.get('crc_verified_on_receipt') is True):
            raise ValueError(f'{name}: manifest does not claim CRC verification on receipt')
        captured_at = timestamp(query.get('captured_at_utc', query.get('captured_at')), name)
        payloads[name] = payload
        records.append({'name': name, 'command': command, 'payload_bytes': len(payload),
                        'sha256': digest, 'captured_at': captured_at,
                        'timestamp_basis': query.get('timestamp_basis', 'capture_query_clock'),
                        'transport_crc_claimed_on_receipt': True})
    decoded = decode_payloads(payloads)
    claimed_identity = manifest.get('identity')
    if claimed_identity is not None:
        if not isinstance(claimed_identity, dict) or any(
                claimed_identity.get(k) != decoded['identity'][k] for k in ('firmware','hardware','uuid')):
            raise ValueError(f'{path}: manifest identity does not match firmware payload')
    provenance = {k: manifest[k] for k in ('capture_date','timezone','started_at_utc',
                  'finished_at_utc','transport','scope','controller_assignment','procedure',
                  'motor_temperature_wiring') if k in manifest}
    provenance.update({'source_directory': str(directory), 'manifest_path': str(path),
                       'manifest_sha256': hashlib.sha256(manifest_bytes).hexdigest(),
                       'payload_hashes_verified': True,
                       'manifest_identity_verified': True if claimed_identity is not None else None,
                       'queries': records})
    return {'provenance': provenance, **decoded}


def compare_decoded(reference, candidate):
    """Compare validated data, rejecting any field-set/signature disagreement."""
    result = {}
    for name, (schema_file, count, signature) in CONFIGURATIONS.items():
        root = ET.parse(DEFAULT_SCHEMA/schema_file).getroot()
        order = [x.text for x in root.find('SerOrder')]
        if len(order) != count or len(set(order)) != count:
            raise ValueError(f'{name}: pinned schema field set changed')
        left, right = reference[name], candidate[name]
        for side in (left, right):
            if (side.get('signature_verified') is not True or side.get('signature_hex') != signature or
                    side.get('schema_version') != '6.00' or set(side['values']) != set(order)):
                raise ValueError(f'{name}: incompatible schema or field-set mismatch')
        rows = []
        for field in order:
            row = {'field': field, 'reference': left['values'][field],
                   'candidate': right['values'][field]}
            row['status'] = 'equal' if row['reference'] == row['candidate'] else 'different'
            for key in ('enum_labels', 'bitfield_labels', 'bitfield_unknown_bits'):
                if field in left.get(key, {}) or field in right.get(key, {}):
                    row[key] = {'reference': left.get(key, {}).get(field),
                                'candidate': right.get(key, {}).get(field)}
            rows.append(row)
        different = sum(row['status'] == 'different' for row in rows)
        result[name] = {'signature_hex': signature, 'field_count': count,
                        'equal_count': count-different, 'different_count': different, 'fields': rows}
    return result


def build_report(reference_path, candidate_path, reference_manifest=None, candidate_manifest=None):
    reference = load_capture(reference_path, reference_manifest)
    candidate = load_capture(candidate_path, candidate_manifest)
    settings = compare_decoded(reference, candidate)
    different = sum(x['different_count'] for x in settings.values())
    # Keep all identity and telemetry details with their own dated source, separate
    # from configuration equality. No inferred current-kart attribution is added.
    return {'report_format': 1,
            'generated_at_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'operation': 'offline_compare_only', 'scope': SCOPE, 'notes': NOTES,
            'reference': {k: reference[k] for k in ('provenance','identity','telemetry')},
            'candidate': {k: candidate[k] for k in ('provenance','identity','telemetry')},
            'summary': {'field_count': 376, 'equal_count': 376-different,
                        'different_count': different},
            'configurations': settings}


def cell(value):
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, allow_nan=False)
    return html.escape(text, quote=False).replace('|', '&#124;').replace('\n', '<br>').replace('\r', '')


def display_value(row, side):
    result = cell(row[side])
    if side in row.get('enum_labels', {}) and row['enum_labels'][side] is not None:
        result += ' ('+cell(row['enum_labels'][side])+')'
    if side in row.get('bitfield_labels', {}) and row['bitfield_labels'][side] is not None:
        result += '; bits: '+cell(row['bitfield_labels'][side])
    if row.get('bitfield_unknown_bits', {}).get(side):
        result += '; unnamed bits: '+cell(row['bitfield_unknown_bits'][side])
    return result


def render_markdown(report):
    summary = report['summary']
    lines = ['# VESC runtime settings comparison', '',
             f"{summary['field_count']} fields: {summary['equal_count']} equal, "
             f"{summary['different_count']} different. No settings applied or recommended.", '',
             'Generated: '+report['generated_at_utc'], '']
    lines += ['- '+note for note in report['notes']]
    lines += ['', '## Captured controllers', '', '| Item | Reference | Candidate |',
              '| --- | --- | --- |']
    for key in ('uuid','firmware','hardware','firmware_name'):
        lines.append('| '+cell(key)+' | '+cell(report['reference']['identity'].get(key))+
                     ' | '+cell(report['candidate']['identity'].get(key))+' |')
    for side in ('reference','candidate'):
        source = report[side]['provenance']
        lines += ['', '### '+side.title()+' provenance', '',
                  '- Raw directory: '+cell(source['source_directory']),
                  '- Manifest: '+cell(source['manifest_path']),
                  '- Manifest SHA-256: '+source['manifest_sha256'],
                  '- Scope: '+cell(source['scope']),
                  '- Transport: '+cell(source.get('transport','unspecified')),
                  '- Manifest controller assignment: '+cell(source.get('controller_assignment','not recorded')),
                  '- Recorded procedure: '+cell(source.get('procedure','not recorded')),
                  '', '| Payload | Captured at | Timestamp basis | Bytes | SHA-256 |',
                  '| --- | --- | --- | --- | --- |']
        for query in source['queries']:
            lines.append('| '+' | '.join(cell(query[k]) for k in
                         ('name','captured_at','timestamp_basis','payload_bytes','sha256'))+' |')
    for name, configuration in report['configurations'].items():
        lines += ['', '## '+name.replace('_',' ').title(), '',
                  f"Signature `{configuration['signature_hex']}`; {configuration['field_count']} fields, "
                  f"{configuration['equal_count']} equal, {configuration['different_count']} different.", '',
                  '| Field | Reference | Candidate | Result |', '| --- | --- | --- | --- |']
        for row in configuration['fields']:
            lines.append('| '+cell(row['field'])+' | '+display_value(row,'reference')+' | '+
                         display_value(row,'candidate')+' | '+row['status']+' |')
    lines += ['', 'Full identity and telemetry payload decodes are retained in '
              '`comparison.json`; telemetry is not included in the 376-setting equality count.', '']
    return '\n'.join(lines)


def write_report(report, out):
    # Fully serialize before creating any output; bad input never leaves a report.
    encoded = json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False)+'\n'
    markdown = render_markdown(report)
    out = Path(out)
    out.mkdir(parents=True, exist_ok=False)
    (out/'comparison.json').write_text(encoded)
    (out/'comparison.md').write_text(markdown)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('reference_raw', type=Path, help='Explicit reference raw-capture directory')
    parser.add_argument('candidate_raw', type=Path, help='Explicit candidate raw-capture directory')
    parser.add_argument('--reference-manifest', type=Path, help='Explicit manifest if not next to raw payloads')
    parser.add_argument('--candidate-manifest', type=Path, help='Explicit manifest if not next to raw payloads')
    parser.add_argument('--out', type=Path, required=True, help='New report directory; existing paths rejected')
    args = parser.parse_args()
    if args.out.exists() or args.out.is_symlink():
        raise FileExistsError(f'Output must be new: {args.out}')
    report = build_report(args.reference_raw, args.candidate_raw,
                          args.reference_manifest, args.candidate_manifest)
    write_report(report, args.out)
    summary = report['summary']
    print(f"Compared {summary['field_count']} settings: {summary['equal_count']} equal, "
          f"{summary['different_count']} different. Offline only; no settings applied.")


if __name__ == '__main__':
    main()
