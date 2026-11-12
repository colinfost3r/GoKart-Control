"""Export the owner-edited R07 result; does not regenerate the generated base."""
import adsk.core, adsk.fusion, pathlib, json


def run(_context: str):
    a = adsk.core.Application.get()
    d = adsk.fusion.Design.cast(a.activeProduct)
    r = d.rootComponent
    assert a.activeDocument.name == 'GoKart Heltec FDM Supports R07'
    folder = pathlib.Path(__file__).resolve().parent
    d.computeAll()
    owner = json.loads((folder / 'input/owner-edited-R07-timeline-667.json').read_text())
    provenance = json.loads((folder / 'owner-edit-provenance.json').read_text())
    assert d.timeline.count == provenance['final_timeline_count']
    for feature in owner['owner_features']:
        assert d.timeline.item(feature['timeline_index']).name == feature['name']
    parts = [o for o in r.occurrences if o.component.name.startswith('R07 ')]
    assert len(parts) == 3
    names = {
        'R07 Case with floor-backed GPS supports': 'case-upper-collar',
        'R07 OLED and antenna lid': 'lid-integral-antenna',
        'R07 Outboard lower collar': 'lower-collar',
    }
    case = next(o for o in parts if o.component.name.startswith('R07 Case'))
    assert abs(case.component.bRepBodies.item(0).volume - provenance['owner_case_volume_before_cm3']) < 1e-10
    comparisons = []
    for source in ['input/owner-layout.json', 'input/owner-edited-R07-timeline-667.json']:
        before = json.loads((folder / source).read_text())
        for old in before['components']:
            if old['name'].startswith(('REF Heltec', 'REF GPS accessory', 'REF 2inch', 'REF OLED')) or old['name'].strip() == 'new ant mount':
                o = next(o for o in r.occurrences if o.component.name == old['name'])
                error = max(abs(x-y) for x, y in zip(o.transform2.asArray(), old['transform']))
                assert error < 1e-8
                comparisons.append({'source': source, 'component': old['name'], 'max_matrix_difference': error, 'transform_cm': list(o.transform2.asArray())})
    out = []
    for o in parts:
        c = o.component
        b = c.bRepBodies.item(0)
        assert c.bRepBodies.count == 1 and b.isSolid and b.lumps.count == 1
        slug = names[c.name]
        opt = d.exportManager.createSTLExportOptions(c, str(folder / (slug + '.stl')))
        opt.unitType = adsk.fusion.DistanceUnits.MillimeterDistanceUnits
        opt.isBinaryFormat = True
        opt.sendToPrintUtility = False
        opt.meshRefinement = adsk.fusion.MeshRefinementSettings.MeshRefinementHigh
        assert d.exportManager.execute(opt)
        assert d.exportManager.execute(d.exportManager.createSTEPExportOptions(str(folder / (slug + '.step')), c))
        bb = o.bRepBodies.item(0).boundingBox
        out.append({'component': c.name, 'file': slug, 'connected_solids': b.lumps.count, 'volume_cm3': b.volume, 'assembly_bounds_mm': [[v*10 for v in bb.minPoint.asArray()], [v*10 for v in bb.maxPoint.asArray()]]})
    prior = json.loads((folder.parent / 'r06-internal-harness/model-audit.json').read_text())
    audit = {key: prior[key] for key in ['status', 'nominal_shell_mm', 'bar_mm', 'bore_mm', 'installation_screws', 'printed_parts', 'gps_socket', 'harness', 'antenna', 'OLED', 'known_fit_limits']}
    audit.update({
        'document': a.activeDocument.name,
        'timeline_count': d.timeline.count,
        'owner_input': 'Owner-edited R07 timeline 667 is authoritative; exact archive input/owner-edited-R07-timeline-667.f3d. Earlier R06 input is also retained.',
        'source_status': 'build_fdm_revision.py reproduces the generated base only. Final native includes all manual owner features plus the approved local lid-only relief.',
        'owner_features_retained': owner['owner_features'],
        'owner_edit_provenance': provenance,
        'owner_pose_comparison': comparisons,
        'parts': out,
        'clamp': {
            'overall_width_mm': 66, 'bolt_centers_mm': [[-26, 0], [26, 0]], 'bolt_pitch_mm': 52,
            'shaft_clearance_diameter_mm': 4.5,
            'socket_screw_nominal_mm': {'thread_diameter': 4, 'under_head_length': 30, 'head_diameter': 7, 'head_height': 4},
            'head_counterbore_mm': [8, 2],
            'nut_pocket_mm': {'across_flats': 7.3, 'height': 3.4, 'insertion_slot_width': 7.5},
            'driver_envelope_diameter_mm': 12, 'case_and_lid_side_clearance_mm': 2, 'split_gap_mm': 1.5,
            'original_holes': 'Filled before new outboard passages were cut',
        },
        'floor_supports': {
            'floor_z_mm': 2.5,
            'sample_columns_xy_mm': [[x, y] for x, y in [(-11.6, -40.9), (11.6, -40.9), (-11.375, -32.55), (11.375, -32.55), (-11.375, -27.1), (11.375, -27.1), (-14.7, -21), (14.7, -21)]],
            'generated_base_reference_only': {
                'forward_ledge_ramp_yz_mm': [[-26.4, 13], [-25.3, 14.1]],
                'front_ramp_abs_xz_mm': [[16, 7.7], [8.25, 15.45]],
                'front_ramp_y_extent_mm': [-22.2, -20.55], 'transition_angle_deg': 45,
            },
            'owner_changes': 'Extrude19 through Extrude24 add material around front supports/end clip and right rear capture. Refer to exact final native and owner snapshot; generated-base dimensions are not a complete final specification.',
            'end_clip': 'Owner-edited retention geometry preserved. Physical clip movement/flex is unvalidated and is not claimed unchanged.',
            'print_limit': 'Short capture lips/clip overhangs and external case/clamp overhangs still require slicer review',
        },
        'inherited_reference_fields': 'GPS, harness, antenna, OLED and fit-limit fields retain R06 design context. Hardware poses are verified unchanged; manual owner lid/support geometry is authoritative in the final native.',
        'feature_warnings': [],
    })
    for i in range(d.timeline.count):
        t = d.timeline.item(i)
        if t.errorOrWarningMessage:
            audit['feature_warnings'].append({'name': t.name, 'message': t.errorOrWarningMessage})
    (folder / 'model-audit.json').write_text(json.dumps(audit, indent=2) + '\n')
    for o in r.occurrences:
        if o.component.name.startswith('R07 '):
            o.isLightBulbOn = True
        if o.component.name.startswith(('REF R07 ', 'REF R06 ')):
            o.isLightBulbOn = False
    assert d.exportManager.execute(d.exportManager.createFusionArchiveExportOptions(str(folder / 'GoKart-Heltec-FDM-Supports-R07.f3d')))
    print('Exported owner-edited R07 native, three STEP, three millimetre STL and model audit.')
