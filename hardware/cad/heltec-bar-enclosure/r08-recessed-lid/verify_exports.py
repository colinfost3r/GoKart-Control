"""Verify R08 deliverables; the owner-edited case is a known diagnostic failure."""
from pathlib import Path
from collections import Counter, defaultdict
import ast
import hashlib
import json
import math
import struct
import sys
import zipfile


def inspect_stl(path):
    data = path.read_bytes()
    count = struct.unpack_from('<I', data, 80)[0]
    assert len(data) == 84 + 50 * count, (path, 'length')
    edges, oriented = Counter(), Counter()
    vertex_faces = defaultdict(list)
    bounds = [[math.inf, -math.inf] for _ in range(3)]
    for i in range(count):
        values = struct.unpack_from('<12fH', data, 84 + 50 * i)
        vertices = [tuple(round(x, 6) for x in values[j:j + 3]) for j in (3, 6, 9)]
        assert all(math.isfinite(x) for v in vertices for x in v), (path, i, 'finite')
        u = [vertices[1][j] - vertices[0][j] for j in range(3)]
        v = [vertices[2][j] - vertices[0][j] for j in range(3)]
        cross = (u[1]*v[2]-u[2]*v[1], u[2]*v[0]-u[0]*v[2], u[0]*v[1]-u[1]*v[0])
        assert sum(x*x for x in cross) > 1e-18, (path, i, 'degenerate')
        for vertex in vertices:
            vertex_faces[vertex].append(i)
            for j, x in enumerate(vertex):
                bounds[j] = [min(bounds[j][0], x), max(bounds[j][1], x)]
        for a, b in zip(vertices, vertices[1:] + vertices[:1]):
            edges[tuple(sorted((a, b)))] += 1
            oriented[(a, b)] += 1
    bad = [{'vertices_mm': e, 'incidence': n} for e, n in edges.items() if n != 2]
    parent = list(range(count))
    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a
    for faces in vertex_faces.values():
        a = find(faces[0])
        for b in faces[1:]:
            parent[find(b)] = a
    return {
        'triangles': count,
        'closed_manifold': not bad,
        'nonmanifold_edges': bad,
        'consistent_winding': all(oriented[(b, a)] == n for (a, b), n in oriented.items()),
        'vertex_connected_components': len({find(i) for i in range(count)}),
        'bounds_mm': bounds,
        'extent_mm': [round(b-a, 6) for a, b in bounds],
    }


def main(folder):
    report = {
        'operation': 'offline_export_verification',
        'status': 'BLOCKED_CASE_AS_EDITED; lid_and_lower_collar_meshes_pass',
        'assembly_print_ready': False,
        'hardware_tested': False,
        'files': {},
    }
    for path in sorted(folder.rglob('*')):
        if path.suffix not in ('.stl', '.step', '.f3d', '.py'):
            continue
        data = path.read_bytes()
        key = path.relative_to(folder).as_posix()
        row = {'sha256': hashlib.sha256(data).hexdigest(), 'bytes': len(data)}
        if path.suffix == '.stl':
            row.update(inspect_stl(path))
            if key == 'diagnostics/case-as-edited-NOT-PRINT-READY.stl':
                expected = {
                    ((18.0, -12.0, -16.25), (18.0, -12.0, 0.0)),
                    ((18.0, -12.0, 0.0), (18.0, 12.0, 0.0)),
                    ((18.0, 12.0, -16.25), (18.0, 12.0, 0.0)),
                }
                actual = {tuple(tuple(v) for v in e['vertices_mm']) for e in row['nonmanifold_edges']}
                assert actual == expected and all(e['incidence'] == 4 for e in row['nonmanifold_edges']), 'Case diagnosis changed; inspect again'
                row.update(print_ready=False, classification='Known native zero-thickness clamp-ear attachment, retained unchanged; NOT a passing mesh')
            else:
                assert path.name in ('stepped-lid.stl', 'lower-collar.stl'), ('Unexpected STL', key)
                assert row['closed_manifold'], (path, 'open/nonmanifold')
                assert row['consistent_winding'], (path, 'winding')
                assert row['vertex_connected_components'] == 1, (path, 'components')
                row['mesh_checks_pass'] = True
        elif path.suffix == '.step':
            assert data.lstrip().startswith(b'ISO-10303-21;') and b'END-ISO-10303-21;' in data, (path, 'STEP envelope')
            row['step_envelope_valid'] = True
            row['geometry_roundtrip_checked'] = False
            if path.name == 'case-recessed-sill.step':
                row['print_ready'] = False
                row['limitation'] = 'Preserves nonmanifold owner clamp-ear attachment; format envelope only is valid'
        elif path.suffix == '.f3d':
            with zipfile.ZipFile(path) as archive:
                methods = sorted({i.compress_type for i in archive.infolist()})
            row.update(zip_directory_readable=True, compression_methods=methods, crc_check='Not performed: Python zipfile lacks Fusion compression method 93; no round-trip reopen claimed.')
        else:
            ast.parse(data.decode())
            row['python_syntax_valid'] = True
        report['files'][key] = row
    for key in ('stepped-lid.stl', 'lower-collar.stl', 'diagnostics/case-as-edited-NOT-PRINT-READY.stl'):
        assert key in report['files'], ('Missing mesh', key)
    (folder / 'export-verification.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'status': report['status'], 'files_checked': len(report['files']), 'assembly_print_ready': False}))


if __name__ == '__main__':
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).parent)
